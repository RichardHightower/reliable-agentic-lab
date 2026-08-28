"""A backend for this folder's `ClaudeAgentOptions`.

Reads `ResultMessage` instead of `str(message)`. The fake used in tests yields
strings, so those still work. The real SDK yields typed messages, and
`str(message)` is how a judge verdict gets lost in a dump of tool events, and
how `usd` stayed pinned at zero while the field sat on `DoerResult` looking
like it meant something.

    usd            from `total_cost_usd`
    structured     from `structured_output`, when the turn set `output_format`
    stop_reason    when the SDK ended the query on max turns or max budget

`stop_reason` matters more than a number in a log. The SDK ending a query is
not a turn that failed and can be retried. It is the ceiling, and a driver
escalates on it instead of spending the rest of the budget rediscovering it.

Write tracking unions the untracked listing into the diff. `git diff
--name-only` sees tracked changes only, and this loop's whole job is creating
files that git has never heard of. A brand new `tests/test_due_date.py` was
invisible to the second line of defense, which is the worst possible place for
that blind spot.
"""

from __future__ import annotations

import asyncio
import dataclasses
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from write_scope import WriteScope

_TURN_STOP = {"error_max_turns", "error_max_turns_assistant"}
_COST_STOP = {"error_max_budget_usd", "error_max_budget"}


@dataclass
class DoerResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    usd: float = 0.0
    ok: bool = True
    structured: dict | None = None
    stop_reason: str | None = None


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    """Tracked diffs plus untracked files.

    `git diff --name-only` misses a file that was never added, and a test
    implementer creates exactly those.
    """
    diff = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    extra = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    names: set[str] = set()
    for stdout in (diff.stdout, extra.stdout):
        names.update(line for line in stdout.splitlines() if line)
    return names


def _from_message(message) -> tuple[str, float, dict | None, bool | None, str | None]:
    """Pull text, cost, structured output, error flag, and stop reason.

    Returns (text, usd, structured, error_or_None, stop_reason_or_None).
    """
    if isinstance(message, str):
        return message, 0.0, None, None, None
    text = getattr(message, "result", None)
    if text is None:
        text = ""
    usd = float(getattr(message, "total_cost_usd", None) or 0.0)
    structured = getattr(message, "structured_output", None)
    if structured is not None and not isinstance(structured, dict):
        structured = None
    is_error = getattr(message, "is_error", None)
    subtype = getattr(message, "subtype", None) or ""
    reason = None
    if subtype in _TURN_STOP:
        reason = "max turns"
    elif subtype in _COST_STOP:
        reason = "cost budget spent"
    if text or usd or structured is not None or is_error is not None or reason:
        return str(text or ""), usd, structured, is_error, reason
    return str(message), 0.0, None, None, None


class AgentSdkBackend(Backend):
    """Runs a named subagent through `claude_agent_sdk.query`."""

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        try:
            from claude_agent_sdk import query  # noqa: PLC0415  (optional dependency)

            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            options = self.options
            fields = (
                {item.name for item in dataclasses.fields(options)}
                if dataclasses.is_dataclass(options)
                else set()
            )
            # Per-turn overrides land on a copy. Mutating the shared options
            # would leak one turn's `output_format` into every later turn.
            overlay = {
                key: value
                for key, value in extra.items()
                if value is not None and (not fields or key in fields)
            }
            if overlay and dataclasses.is_dataclass(options):
                options = dataclasses.replace(options, **overlay)

            async def collect() -> tuple[str, float, dict | None, bool, str | None]:
                chunks: list[str] = []
                usd = 0.0
                structured = None
                ok = True
                reason = None
                async for message in query(prompt=prompt, options=options):
                    text, cost, parsed, error, stop = _from_message(message)
                    if text:
                        chunks.append(text)
                    if cost:
                        usd = cost
                    if parsed is not None:
                        structured = parsed
                    if error is True:
                        ok = False
                    if stop:
                        reason = stop
                        ok = False
                return "\n".join(chunks), usd, structured, ok, reason

            output, usd, structured, ok, reason = asyncio.run(collect())
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(
                wrote=wrote,
                output=output,
                usd=usd,
                ok=ok,
                structured=structured,
                stop_reason=reason,
            )
        except Exception as exc:  # graceful failure. Never claim a write it did not make.
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")
