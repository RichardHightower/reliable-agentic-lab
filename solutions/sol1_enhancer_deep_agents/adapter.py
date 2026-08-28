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


def last_ai_text(result) -> str:
    """The last model reply, not `str(the whole graph state)`.

    `create_deep_agent(...).invoke` returns a state dict whose `messages`
    list holds Human/AI/Tool messages. `enhancer.parse_judge` has to see
    the judge's JSON, not a repr of every message that produced it.

    Content may be a string or a list of blocks. Either way this returns
    the text the judge or the doer meant as its answer.
    """
    if isinstance(result, str):
        return result
    messages = None
    if isinstance(result, dict):
        messages = result.get("messages")
    else:
        messages = getattr(result, "messages", None)
        if messages is None and hasattr(result, "get"):
            messages = result.get("messages")
    if not messages:
        return str(result)
    last = messages[-1]
    content = last.get("content") if isinstance(last, dict) else getattr(last, "content", last)
    return _content_text(content)


def last_usd(result) -> float:
    """Sum any cost the invoke result carried. Zero when the runtime is silent.

    Deep Agents does not always put a dollar figure on graph state. When a
    message has `usage_metadata` with `total_cost` / `total_cost_usd` / `cost`,
    that is the number `check_stop` charges. Missing metadata is zero, not a
    guess.
    """
    if isinstance(result, dict) and result.get("usd") is not None:
        try:
            return float(result["usd"])
        except (TypeError, ValueError):
            pass
    messages = None
    if isinstance(result, dict):
        messages = result.get("messages")
    else:
        messages = getattr(result, "messages", None)
        if messages is None and hasattr(result, "get"):
            messages = result.get("messages")
    total = 0.0
    for msg in messages or []:
        usage = msg.get("usage_metadata") if isinstance(msg, dict) else getattr(msg, "usage_metadata", None)
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


def _content_text(content) -> str:
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
                if block.get("type") in (None, "text") and "text" in block:
                    parts.append(block["text"])
                elif "text" in block:
                    parts.append(block["text"])
            else:
                text = getattr(block, "text", None)
                parts.append(text if text is not None else str(block))
        return "".join(parts)
    text = getattr(content, "text", None)
    return text if text is not None else str(content)


class DeepAgentsBackend(Backend):
    """Runs the doer role through a Deep Agents agent's `.invoke`.

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
        # Graceful failure, mirrors CliBackend.run. A backend that raises
        # takes the loop down with it.
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep agents backend failed: {exc}")
