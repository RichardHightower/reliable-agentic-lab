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

import contextlib
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


def _content_text(content) -> str:
    """Flatten message content, which is a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def last_ai_text(result) -> str:
    """The last AI message, not the repr of the whole graph state.

    `str(result)` returns a dict repr with every message, every tool call, and
    every id in it. Handing that to a JSON parser or into another prompt is how
    a working loop starts failing on nothing you changed.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
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
    return ""


def last_usd(result) -> float:
    """What the run cost, summed from usage metadata.

    Missing metadata is zero, not a guess. A budget built on estimated costs is
    a budget that is wrong in whichever direction is least convenient.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    total = 0.0
    for message in messages:
        usage = (
            message.get("usage_metadata")
            if isinstance(message, dict)
            else getattr(message, "usage_metadata", None)
        ) or {}
        for key in ("total_cost", "total_cost_usd", "cost"):
            if key in usage:
                # A malformed cost is treated as unknown, which is zero.
                # Guessing here makes the budget wrong in whichever direction
                # is least convenient.
                with contextlib.suppress(TypeError, ValueError):
                    total += float(usage[key])
                break
    return total


def _changed_files(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


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
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep_agents backend failed: {exc}")
