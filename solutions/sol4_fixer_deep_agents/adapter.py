"""A `doers.Backend` for this folder's Deep Agents agent.

Issue #2: this folder's `doers.py` `build(spec)` now accepts an already-built
`Backend` and passes it through unchanged, so a runtime port can plug in its
own doer. `Backend` and `DoerResult` are copied here rather than imported —
one more standalone folder, not a ninth shared file.

`deepagents` is already imported inside `roles.build_agent`, so there is
nothing extra to import lazily here. Nothing in this module is exercised by
`python loop.py --table-only`, which never calls `run()`.
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
    proc = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return set(proc.stdout.splitlines())


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
    """The last model reply, not `str(the whole graph state)`.

    `str(result)` is a repr of every message, every tool call, and every id in
    the run. Handing that to a JSON parser or into the next prompt is how a
    working loop starts failing on nothing anyone changed.

    The search runs backward for a message the runtime labeled as the model's.
    Taking `messages[-1]` outright returns a tool result as if the model had
    said it, whenever the graph ends on a tool call.
    """
    if isinstance(result, str):
        return result
    messages = _messages(result)
    if not messages:
        return str(result)
    for message in reversed(messages):
        role = getattr(message, "type", None) or (
            message.get("role") if isinstance(message, dict) else None
        )
        if role not in ("ai", "assistant"):
            continue
        content = (
            message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
        )
        text = _content_text(content).strip()
        if text:
            return text
    # Nothing named itself as the model's reply. The last message is the best
    # answer left, and returning "" here would look like a successful empty run.
    last = messages[-1]
    content = last.get("content") if isinstance(last, dict) else getattr(last, "content", last)
    return _content_text(content)


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
    """Runs the code_implementer role through a Deep Agents agent's `.invoke`.

    `agent` is what this folder's `build_agent(contract, loop=LOOP)` already
    returns.
    """

    name = "deep_agents"

    def __init__(self, agent):
        self.agent = agent

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            result = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=last_ai_text(result), usd=last_usd(result))
        except Exception as exc:  # graceful failure, mirrors CliBackend.run
            return DoerResult(ok=False, output=f"deep agents backend failed: {exc}")
