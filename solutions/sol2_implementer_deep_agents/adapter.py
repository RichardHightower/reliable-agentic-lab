"""A `doers.Backend` for this runtime port, copied flat into this folder.

`implementer.run()` in the reference loop takes any object shaped like
`Backend`: a `.name` and a `.run(*, repo, prompt, allow) -> DoerResult`. This
folder is standalone, so it does not import a shared engine for that shape, it
restates the two small pieces it needs and wraps the Deep Agents graph
behind them.

`deepagents` is not installed in this environment. The import stays inside
`build_agent()` (already true in `roles.py`), so `harness.py --table-only`
keeps working without it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from write_scope import WriteScope


@dataclass
class DoerResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    usd: float = 0.0
    ok: bool = True


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


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


def last_usd(result) -> float:
    """What the run cost, summed from usage metadata. Missing is zero.

    Zero, not a guess. A budget built on estimated costs is wrong in whichever
    direction is least convenient, and this number decides when the loop stops.

    `usage_metadata` is not always a dict. Testing `key in usage` on an object
    raises, and a backend that raises takes the loop down with it.
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
        for key in ("total_cost", "total_cost_usd", "cost"):
            if usage.get(key) is None:
                continue
            try:
                total += float(usage[key])
            except (TypeError, ValueError):
                continue
            break
    return total


class DeepAgentsBackend(Backend):
    """Runs one role's prompt through the Deep Agents graph this folder builds."""

    name = "deep_agents"

    def __init__(self, agent):
        self.agent = agent

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            before = _changed_files(repo)
            result = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = sorted(path for path in (after - before) if scope.permits(path))
            return DoerResult(wrote=wrote, output=last_ai_text(result), usd=last_usd(result))
        # Mirrors CliBackend.run: never raise, report it.
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep_agents backend failed: {exc}")
