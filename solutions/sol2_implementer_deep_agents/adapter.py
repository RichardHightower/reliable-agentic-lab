"""A `doers.Backend` for this runtime port, copied flat into this folder.

`implementer.run()` in this standalone folder takes a `doers.Backend`: a
`.name` and a `.run(*, repo, prompt, allow) -> DoerResult`. Import that local
contract so `doers.build()` recognizes this runtime adapter and passes it
through unchanged.

`deepagents` is not installed in this environment. The import stays inside
`build_agent()` (already true in `roles.py`), so `harness.py --table-only`
keeps working without it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from doers import Backend, DoerResult
from write_scope import WriteScope

# Sonnet-class list prices. LangChain never emits a cost field, so the money
# exit is dead unless we price the token counts ourselves. These numbers are
# the estimate the loop uses, not a bill.
INPUT_USD_PER_MTOK = 3.0
OUTPUT_USD_PER_MTOK = 15.0


def _changed_files(repo: Path) -> set[str]:
    """Every path this working tree changes, including untracked files.

    `git diff --name-only` only sees tracked edits. A Deep Agents write that
    creates a new test file is the common case, and that file would vanish
    from `DoerResult.wrote` if we asked diff.
    """
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    paths: set[str] = set()
    for line in out.stdout.splitlines():
        if len(line) > 3:
            paths.add(line[3:].strip().split(" -> ")[-1])
    return paths


def _messages(result):
    """The message list, however this runtime wrapped it.

    `.invoke` returns a state dict on the graph path and can return an object
    elsewhere. Reading only `result["messages"]` makes every non-dict result
    look empty, which reads as a silent success.
    """
    if isinstance(result, dict):
        return result.get("messages")
    messages = getattr(result, "messages", None)
    if messages is None and hasattr(result, "get"):
        messages = result.get("messages")
    return messages


def _role_of(message) -> str:
    return (
        getattr(message, "type", None)
        or (message.get("role") if isinstance(message, dict) else None)
        or ""
    )


def _content_of(message):
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", "")


def _content_text(content) -> str:
    """Flatten message content into the text the model meant to send.

    Content is a string, a list of blocks, or an object carrying `.text`. A
    block is a string, a dict, or an object. Every shape that holds text has to
    come back, because a dropped block does not raise. It returns a shorter
    answer that still parses, and the loop acts on half a reply.

    A dict block with no `type` key is the common case. Testing
    `block.get("type") == "text"` drops it.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if "text" in block:
                    parts.append(block["text"])
            else:
                text = getattr(block, "text", None)
                parts.append(text if text is not None else str(block))
        return "".join(parts)
    text = getattr(content, "text", None)
    return text if text is not None else str(content)


def last_ai_text(result) -> str:
    """The answer this run produced. Not an older one, not the state repr.

    Walk backward and take the first non-empty content from an assistant or a
    tool message. One line, and it is the only rule that survives all four
    shapes a graph actually returns.

    Three ways to get this wrong, and this repo has shipped two of them.

    `str(result)` is a repr of every message, every tool call, and every id.
    Handing that to a JSON parser is how a working loop starts failing on
    nothing anyone changed.

    `messages[-1]` reads whichever message happens to be last without asking
    what it is.

    Walking backward for the last non-empty *assistant* message returns an
    answer from BEFORE the last tool ran. A tool-calling assistant message
    carries `tool_calls` and empty content, so that walk steps over it onto an
    earlier turn. A stale verdict that parses is worse than no verdict, because
    nothing reports it.

    A ToolMessage exists only because an assistant asked for it. So "the model
    has not spoken since the tool ran" and "the tool holds the answer" are the
    same state, and a subagent with a `response_format` puts its structured
    result exactly there, JSON-serialized.
    """
    if isinstance(result, str):
        return result
    messages = _messages(result)
    if not messages:
        return str(result)
    for message in reversed(messages):
        if _role_of(message) not in ("ai", "assistant", "tool"):
            continue
        text = _content_text(_content_of(message)).strip()
        if text:
            return text
    # Nothing carried content. The last message is the best answer left, and
    # returning "" here would look like a successful empty run.
    return _content_text(_content_of(messages[-1]))


def _usage_usd(usage: dict) -> float:
    """One message's cost. Vendor dollars first, then priced tokens."""
    for key in ("total_cost", "total_cost_usd", "cost"):
        if usage.get(key) is None:
            continue
        try:
            return float(usage[key])
        except (TypeError, ValueError):
            continue
    try:
        inp = float(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        out = float(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        return 0.0
    if inp <= 0 and out <= 0:
        return 0.0
    return (inp * INPUT_USD_PER_MTOK + out * OUTPUT_USD_PER_MTOK) / 1_000_000


def last_usd(result) -> float:
    """What the run cost.

    LangChain `usage_metadata` has token counts, not dollars. When a cost key
    is present we trust it. When only tokens are present we price them at
    Sonnet-class rates so `usd_left` can actually drop. Missing is zero, not
    a guess of a different kind.
    """
    if isinstance(result, dict) and result.get("usd") is not None:
        try:
            return float(result["usd"])
        except (TypeError, ValueError):
            pass
    total = 0.0
    for message in _messages(result) or []:
        usage = (
            message.get("usage_metadata")
            if isinstance(message, dict)
            else getattr(message, "usage_metadata", None)
        )
        if not isinstance(usage, dict):
            continue
        total += _usage_usd(usage)
    return total


class DeepAgentsBackend(Backend):
    """Runs one role's prompt through the Deep Agents graph this folder builds."""

    name = "deep_agents"

    def __init__(
        self,
        agent=None,
        *,
        phase_agents=None,
        judge_agent=None,
        recursion_limit: int | None = None,
    ):
        if agent is None and not phase_agents:
            raise ValueError("provide an agent or one agent for each implementation phase")
        self.agent = agent
        self.phase_agents = phase_agents
        self.judge_agent = judge_agent
        self.recursion_limit = recursion_limit

    def _agent_for(self, allow: list[str]):
        """Choose the graph whose cast matches the driver's current phase."""
        if self.phase_agents is None:
            return self.agent
        if any(pattern.startswith("tests/") for pattern in allow):
            phase = "test"
        elif any(pattern.startswith(("app/", "src/")) for pattern in allow):
            phase = "code"
        else:
            raise ValueError(f"no Deep Agents graph is configured for scope {allow!r}")
        return self.phase_agents[phase]

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            before = _changed_files(repo)
            payload = {"messages": [{"role": "user", "content": prompt}]}
            agent = self._agent_for(allow)
            if self.recursion_limit:
                result = agent.invoke(payload, config={"recursion_limit": self.recursion_limit})
            else:
                result = agent.invoke(payload)
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = sorted(path for path in (after - before) if scope.permits(path))
            return DoerResult(wrote=wrote, output=last_ai_text(result), usd=last_usd(result))
        # Mirrors CliBackend.run: never raise, report it.
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep_agents backend failed: {exc}")

    def judge(self, *, repo: Path, prompt: str) -> DoerResult:
        """Run the judge-only graph. No write tools, JSON in, JSON out."""
        agent = self.judge_agent
        if agent is None:
            return super().judge(repo=repo, prompt=prompt)
        try:
            payload = {"messages": [{"role": "user", "content": prompt}]}
            if self.recursion_limit:
                result = agent.invoke(payload, config={"recursion_limit": self.recursion_limit})
            else:
                result = agent.invoke(payload)
            return DoerResult(output=last_ai_text(result), usd=last_usd(result))
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep_agents judge failed: {exc}")
