"""A backend for this folder's `ClaudeAgentOptions`.

Reads `ResultMessage` instead of joining the event stream. The fake used in
tests yields strings, so those still work. The real SDK yields typed messages,
and concatenating every event is how Grep output became a candidate.

    usd            from `total_cost_usd`
    structured     from `structured_output`, when the turn set `output_format`
    stop_reason    when the SDK ended the query on max turns, max budget, or timeout
    raw_output     every event, as diagnostics, never as the answer

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
from pathlib import Path

from doers import Backend, DoerResult
from write_scope import WriteScope

_TURN_STOP = {"error_max_turns", "error_max_turns_assistant"}
_COST_STOP = {"error_max_budget_usd", "error_max_budget"}
QUERY_TIMEOUT_SECONDS = 180


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


def _from_result(result) -> tuple[str, float, dict | None, bool | None, str | None]:
    """Pull data from the SDK's final ``ResultMessage`` only."""
    if isinstance(result, str):
        return result, 0.0, None, None, None
    text = getattr(result, "result", None) or ""
    usd = float(getattr(result, "total_cost_usd", None) or 0.0)
    structured = getattr(result, "structured_output", None)
    if structured is not None and not isinstance(structured, dict):
        structured = None
    is_error = getattr(result, "is_error", None)
    subtype = getattr(result, "subtype", None) or ""
    reason = None
    if subtype in _TURN_STOP:
        reason = "max turns"
    elif subtype in _COST_STOP:
        reason = "cost budget spent"
    return str(text), usd, structured, is_error, reason


def _raw_event(message) -> str:
    """A local diagnostic record, intentionally never used as a candidate."""
    return f"## {type(message).__name__}\n\n{message!r}\n"


class AgentSdkBackend(Backend):
    """Runs a named subagent through `claude_agent_sdk.query`."""

    name = "agent_sdk"

    def __init__(self, options, *, timeout_seconds: float = QUERY_TIMEOUT_SECONDS):
        self.options = options
        self.timeout_seconds = timeout_seconds

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        try:
            from claude_agent_sdk import ResultError, ResultMessage, query  # noqa: PLC0415

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

            raw_events: list[str] = []

            async def collect() -> tuple[str, float, dict | None, bool, str | None]:
                result_text = ""
                usd = 0.0
                structured = None
                ok = True
                reason = None
                saw_result = False
                try:
                    async for message in query(prompt=prompt, options=options):
                        raw_events.append(_raw_event(message))
                        if not isinstance(message, (ResultMessage, str)):
                            continue
                        saw_result = saw_result or isinstance(message, ResultMessage)
                        text, cost, parsed, error, stop = _from_result(message)
                        if text:
                            result_text = text
                        if cost:
                            usd = cost
                        if parsed is not None:
                            structured = parsed
                        if error is True:
                            ok = False
                        if stop:
                            reason = stop
                            ok = False
                except ResultError:
                    # The SDK yields its terminal ResultMessage and then raises
                    # ResultError for the CLI's non-zero exit. Keep the terminal
                    # ceiling visible to the loop instead of erasing it.
                    if not saw_result:
                        raise
                return result_text, usd, structured, ok, reason

            try:
                output, usd, structured, ok, reason = asyncio.run(
                    asyncio.wait_for(collect(), timeout=self.timeout_seconds)
                )
            except asyncio.TimeoutError:
                return DoerResult(
                    ok=False,
                    output=f"agent sdk query timed out after {self.timeout_seconds} seconds",
                    stop_reason="query timeout",
                    raw_output="\n".join(raw_events),
                )
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(
                wrote=wrote,
                output=output,
                usd=usd,
                ok=ok,
                structured=structured,
                stop_reason=reason,
                raw_output="\n".join(raw_events),
            )
        except Exception as exc:  # graceful failure. Never claim a write it did not make.
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")

    def judge(self, *, repo: Path, prompt: str) -> DoerResult:
        """One judge turn. Structured output when the schema is available."""
        extra = {}
        try:
            from load_agents import JUDGE_SCHEMA  # noqa: PLC0415

            extra["output_format"] = JUDGE_SCHEMA
        except Exception:
            pass
        return self.run(repo=repo, prompt=prompt, allow=[], **extra)


class AgentSdkPhaseBackend(Backend):
    """One backend per phase. The driver never asks a test graph to write code."""

    name = "agent_sdk"

    def __init__(
        self,
        *,
        test: AgentSdkBackend,
        code: AgentSdkBackend,
        judge: AgentSdkBackend | None = None,
    ):
        self.test = test
        self.code = code
        self.judge_backend = judge

    def _for(self, allow: list[str]) -> AgentSdkBackend:
        if any(pattern.startswith("tests/") for pattern in allow):
            return self.test
        if any(pattern.startswith(("app/", "src/")) for pattern in allow):
            return self.code
        raise ValueError(f"no Agent SDK backend is configured for scope {allow!r}")

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        return self._for(allow).run(repo=repo, prompt=prompt, allow=allow, **extra)

    def judge(self, *, repo: Path, prompt: str) -> DoerResult:
        if self.judge_backend is None:
            return super().judge(repo=repo, prompt=prompt)
        return self.judge_backend.judge(repo=repo, prompt=prompt)

