"""Reaching Perplexity and Context7, three ways, behind one name.

The repo already declares both servers in `.mcp.json`. This module reads that
file and tries three transports in order, because an attendee's laptop is not a
build server:

    1. MCP, through `langchain-mcp-adapters`. The boundary Module 3 teaches.
    2. The vendor's own interface. Perplexity has an OpenAI-shaped REST API.
       Context7 has the `ctx7` CLI. Both work when the MCP hop does not.
    3. Unavailable. The caller falls through to the recorded fixture.

Why MCP first when the direct call is simpler: the tool list is the wall. When
research arrives as an MCP tool, the thing that stops this loop from merging a
pull request is that no such tool was loaded. When it arrives as `httpx.post`
inside the process, the only thing stopping it is that nobody wrote the code
yet. The seminar's whole point is the first kind of stop.

Why the direct path exists at all: an MCP server is a subprocess or a network
hop, and both fail in a hotel conference room. A research loop that dies because
`npx` was slow taught nobody anything.

What this module never does: read a key out of `~/.claude.json`. Claude Code
stores one there, and quietly borrowing it would make this folder work on one
laptop and nowhere else. Put `PERPLEXITY_API_KEY` in this solution's `.env` or
one of its next three parent `.env` files; `research.py` loads those explicit
locations for both Task and direct Python entry points.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MCP_CONFIG = HERE / ".." / ".." / ".mcp.json"

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
CONTEXT7_URL = "https://mcp.context7.com/mcp"

# Perplexity charges per request plus tokens. This is the per-call figure the
# budget is charged, deliberately rounded up. A budget that under-counts is a
# budget that gets discovered on the invoice.
PERPLEXITY_COST_PER_CALL = 0.006
CONTEXT7_COST_PER_CALL = 0.0

HTTP_TIMEOUT = 60.0
CLI_TIMEOUT = 90

ENV_REF = re.compile(r"\$\{(\w+)\}")
URL_IN_TEXT = re.compile(r"https?://[^\s)\]<>\"']+")


class TransportUnavailable(RuntimeError):
    """This transport cannot run here. Not an error, a fact about the laptop."""


# -- .mcp.json ------------------------------------------------------------


def expand(value: str) -> str:
    """Resolve `${VAR}` from the environment, and to empty when it is unset.

    Empty is the honest answer. Leaving the literal `${PERPLEXITY_API_KEY}` in
    place makes the server start and then fail on the first call with a 401,
    which reads like a network problem and is not.
    """
    return ENV_REF.sub(lambda match: os.environ.get(match.group(1), ""), value)


def load_mcp_config(path: Path | str | None = None) -> dict:
    """The `mcpServers` map, with `${VAR}` resolved. Missing file is empty."""
    config_path = Path(path) if path else DEFAULT_MCP_CONFIG
    if not config_path.exists():
        return {}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    servers = {}
    for name, spec in (data.get("mcpServers") or {}).items():
        resolved = dict(spec)
        if "env" in resolved:
            resolved["env"] = {key: expand(val) for key, val in resolved["env"].items()}
        if "args" in resolved:
            resolved["args"] = [expand(arg) for arg in resolved["args"]]
        servers[name] = resolved
    return servers


def _adapter_spec(spec: dict) -> dict:
    """Translate one `.mcp.json` entry into what MultiServerMCPClient wants.

    Claude Code writes `{"type": "http", "url": ...}`. The LangChain adapter
    calls that transport `streamable_http`, and a stdio server needs no `type`
    key at all. One rename, in one place, rather than in every caller.
    """
    if spec.get("type") == "http" or ("url" in spec and "command" not in spec):
        return {"transport": "streamable_http", "url": spec["url"]}
    out = {"transport": "stdio", "command": spec["command"], "args": list(spec.get("args", []))}
    if spec.get("env"):
        out["env"] = spec["env"]
    return out


def mcp_tools(server: str, config: dict | None = None):
    """LangChain tools from one MCP server, or raise TransportUnavailable.

    Imported inside the function on purpose. `loop.py --table-only` and the whole
    test suite must run with no `langchain-mcp-adapters` installed.
    """
    servers = config if config is not None else load_mcp_config()
    if server not in servers:
        raise TransportUnavailable(f"{server} is not in .mcp.json")
    try:
        import asyncio  # noqa: PLC0415

        from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: PLC0415
    except ImportError as exc:
        raise TransportUnavailable(f"langchain-mcp-adapters is not installed: {exc}") from exc

    client = MultiServerMCPClient({server: _adapter_spec(servers[server])})
    try:
        return asyncio.run(client.get_tools(server_name=server))
    except Exception as exc:
        raise TransportUnavailable(f"{server} did not answer: {exc}") from exc


def _tool_text(value) -> str:
    """Flatten MCP content blocks instead of stringifying their Python repr."""
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_tool_text(block) for block in content)
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        if "content" in content:
            return _tool_text(content["content"])
    text = getattr(content, "text", None)
    return str(text if text is not None else content)


def _call_mcp_tool(tools, name_fragment: str, args: dict) -> str:
    import asyncio  # noqa: PLC0415

    for tool in tools:
        if name_fragment in getattr(tool, "name", ""):
            return _tool_text(asyncio.run(tool.ainvoke(args)))
    raise TransportUnavailable(f"no tool matching {name_fragment!r} on that server")


# -- answers --------------------------------------------------------------


@dataclass
class Answer:
    """One reply from the boundary. `transport` names which of the three ran."""

    text: str = ""
    citations: list[str] = field(default_factory=list)
    transport: str = ""
    usd: float = 0.0

    @property
    def empty(self) -> bool:
        return not self.text.strip()


def citations_from(text: str, extra: list | None = None) -> list[str]:
    """Every URL the answer mentions, de-duplicated, in the order it said them.

    Perplexity returns a `citations` array on the REST path and inlines URLs in
    the MCP path. Scraping the text covers both, and a URL that appears in the
    prose is a URL the writer can cite.
    """
    found: list[str] = []
    for url in list(extra or []) + URL_IN_TEXT.findall(text):
        clean = str(url).rstrip(".,;")
        if clean not in found:
            found.append(clean)
    return found


# -- Perplexity -----------------------------------------------------------


def perplexity_available() -> bool:
    return bool(os.environ.get("PERPLEXITY_API_KEY"))


def ask_perplexity_mcp(question: str, config: dict | None = None) -> Answer:
    tools = mcp_tools("perplexity-ask", config)
    text = _call_mcp_tool(
        tools,
        "perplexity_ask",
        {"messages": [{"role": "user", "content": question}]},
    )
    return Answer(
        text=text,
        citations=citations_from(text),
        transport="perplexity-mcp",
        usd=PERPLEXITY_COST_PER_CALL,
    )


def ask_perplexity_rest(question: str) -> Answer:
    """The vendor's OpenAI-shaped endpoint. `httpx` ships with this repo."""
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise TransportUnavailable("PERPLEXITY_API_KEY is not set")
    try:
        import httpx  # noqa: PLC0415
    except ImportError as exc:
        raise TransportUnavailable(f"httpx is not installed: {exc}") from exc

    try:
        response = httpx.post(
            PERPLEXITY_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": PERPLEXITY_MODEL,
                "messages": [{"role": "user", "content": question}],
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise TransportUnavailable(f"perplexity REST failed: {exc}") from exc

    text = payload["choices"][0]["message"]["content"]
    return Answer(
        text=text,
        citations=citations_from(text, payload.get("citations")),
        transport="perplexity-rest",
        usd=PERPLEXITY_COST_PER_CALL,
    )


def ask_perplexity(question: str, config: dict | None = None) -> Answer:
    """MCP, then REST. The caller never learns which one answered."""
    if not perplexity_available():
        raise TransportUnavailable("PERPLEXITY_API_KEY is not set")
    try:
        return ask_perplexity_mcp(question, config)
    except TransportUnavailable:
        return ask_perplexity_rest(question)


# -- Context7 -------------------------------------------------------------


def ctx7_available() -> bool:
    return shutil.which("ctx7") is not None


def ask_context7_mcp(library: str, question: str, config: dict | None = None) -> Answer:
    tools = mcp_tools("context7", config)
    library_id = library
    if not library.startswith("/"):
        library_id = _call_mcp_tool(tools, "resolve-library-id", {"libraryName": library}).strip()
        match = re.search(r"/[\w.-]+/[\w.-]+", library_id)
        library_id = match.group(0) if match else library
    text = _call_mcp_tool(tools, "query-docs", {"libraryId": library_id, "query": question})
    return Answer(text=text, citations=[library_id], transport="context7-mcp")


def ask_context7_cli(library: str, question: str) -> Answer:
    """The `ctx7` CLI. Anonymous use is rate limited, so failure is expected."""
    if not ctx7_available():
        raise TransportUnavailable("ctx7 is not on PATH")
    library_id = library
    if not library.startswith("/"):
        found = _run(["ctx7", "library", library, question])
        match = re.search(r"/[\w.-]+/[\w.-]+", found)
        if not match:
            raise TransportUnavailable(f"ctx7 could not resolve {library!r}")
        library_id = match.group(0)
    text = _run(["ctx7", "docs", library_id, question, "--json"])
    return Answer(text=text, citations=[library_id], transport="context7-cli")


def _run(argv: list[str]) -> str:
    try:
        proc = subprocess.run(
            argv, text=True, capture_output=True, check=False, timeout=CLI_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TransportUnavailable(f"{argv[0]} failed: {exc}") from exc
    if proc.returncode != 0:
        raise TransportUnavailable(
            f"{argv[0]} exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        )
    return proc.stdout.strip()


def ask_context7(library: str, question: str, config: dict | None = None) -> Answer:
    try:
        return ask_context7_mcp(library, question, config)
    except TransportUnavailable:
        return ask_context7_cli(library, question)


def demo() -> None:
    assert expand("${NO_SUCH_VAR_HERE}") == ""
    os.environ["SOL3_DEMO_VAR"] = "filled"
    assert expand("a-${SOL3_DEMO_VAR}-b") == "a-filled-b"
    del os.environ["SOL3_DEMO_VAR"]

    assert _adapter_spec({"type": "http", "url": "https://x"}) == {
        "transport": "streamable_http",
        "url": "https://x",
    }
    assert _adapter_spec({"command": "npx", "args": ["-y", "s"], "env": {"K": "v"}}) == {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "s"],
        "env": {"K": "v"},
    }

    cites = citations_from("see https://a.example/x. and https://a.example/x again")
    assert cites == ["https://a.example/x"], cites

    assert Answer(text="   ").empty
    assert not Answer(text="hi").empty
    print("mcp_tools: all demo assertions passed")


if __name__ == "__main__":
    demo()
