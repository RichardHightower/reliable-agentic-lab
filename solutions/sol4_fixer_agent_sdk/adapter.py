"""A `doers.Backend` for this folder's `ClaudeAgentOptions`.

Issue #2: this folder's `doers.py` `build(spec)` now accepts an already-built
`Backend` and passes it through unchanged, so a runtime port can plug in its
own doer. `Backend` and `DoerResult` are copied here rather than imported —
one more standalone folder, not a ninth shared file.

The SDK is optional and not installed in this environment, so the import
stays lazy (same style `roles.py` already uses for `AgentDefinition` et al.).
Nothing here is exercised without it: `python loop.py --table-only` never
touches this module's `run()`.
"""

from __future__ import annotations

import asyncio
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
    stop_reason: str | None = None


def _from_message(message) -> tuple[str, float, bool | None, str | None]:
    """Pull text, cost, the error flag, and the stop reason off one message.

    `str(message)` flattened all four into a log line. The cost was the
    expensive loss: `fixer.py` calls `boss.spend(result.usd)` and
    `gates.decide` has a live `usd_left <= 0` branch, so a `usd` pinned at zero
    meant the money gate could never fire. An unattended fixer with no cost
    ceiling is the surprise bill `gates.py` says it exists to prevent.

    The fake used in tests yields strings, so those still work.
    """
    if isinstance(message, str):
        return message, 0.0, None, None
    text = getattr(message, "result", None) or ""
    usd = float(getattr(message, "total_cost_usd", None) or 0.0)
    is_error = getattr(message, "is_error", None)
    subtype = getattr(message, "subtype", None) or ""
    reason = None
    if subtype in _TURN_STOP:
        reason = "max turns"
    elif subtype in _COST_STOP:
        reason = "cost budget spent"
    if text or usd or is_error is not None or reason:
        return str(text), usd, is_error, reason
    return str(message), 0.0, None, None


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return set(proc.stdout.splitlines())


class AgentSdkBackend(Backend):
    """Runs the code_implementer role through `claude_agent_sdk.query`.

    `options` is what this folder's `build(contract)` already returns.
    """

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            from claude_agent_sdk import query  # noqa: PLC0415  (optional dependency)

            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)

            async def collect() -> tuple[str, float, bool, str | None]:
                chunks: list[str] = []
                usd = 0.0
                ok = True
                reason = None
                async for message in query(prompt=prompt, options=self.options):
                    text, cost, error, stop = _from_message(message)
                    if text:
                        chunks.append(text)
                    if cost:
                        usd = cost
                    if error is True:
                        ok = False
                    if stop:
                        reason = stop
                        ok = False
                return "\n".join(chunks), usd, ok, reason

            output, usd, ok, reason = asyncio.run(collect())
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=output, usd=usd, ok=ok, stop_reason=reason)
        except Exception as exc:
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")
