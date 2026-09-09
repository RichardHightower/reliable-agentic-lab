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

#568. `collect()` returns the moment a `ResultMessage` names a controlled
stop (max turns or cost budget), instead of continuing to ask the generator
for whatever comes next. The round-4 raw logs show a query that ended on
`error_max_budget_usd` in under a minute and then sat open, quiet, until the
900 second ceiling: the terminal record was already in hand, and the only
thing `collect()` was still waiting on was the stream closing itself, which
this port has no control over. Waiting past a controlled stop turns a
one-minute, evidenced "cost budget spent" into a 900-second "query timeout",
discarding the real reason. A stream with no terminal result at all is
unaffected: nothing here short-circuits the wait for that case, and
`asyncio.wait_for`'s own ceiling is still what ends it.

Write tracking unions the untracked listing into the diff. `git diff
--name-only` sees tracked changes only, and this loop's whole job is creating
files that git has never heard of. A brand new `tests/test_due_date.py` was
invisible to the second line of defense, which is the worst possible place for
that blind spot.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import subprocess
import sys
import time
from pathlib import Path

import steps
from doers import Backend, DoerResult
from write_scope import WriteScope

_TURN_STOP = {"error_max_turns", "error_max_turns_assistant"}
_COST_STOP = {"error_max_budget_usd", "error_max_budget"}


def _timeout_env(name: str, default: int) -> int:
    """Read a positive-integer timeout from the environment, never raising
    at import.

    #553, matching the `_timeout_env()` shape sol1 and sol4 landed for
    #541. A bad value here used to raise `ValueError` at import time and
    take the whole module down with it. A logged fallback keeps the process
    alive, the same way a missing dependency reports as a result, not a
    traceback.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value is None or value <= 0:
        print(
            f"[sol2] {name}={raw!r} is not a positive integer; using the default {default}s",
            file=sys.stderr,
            flush=True,
        )
        return default
    return value


# #539. A live T001 test-implementer turn ran past 180 seconds and the SDK
# never got the chance to say what it had spent. sol3 hit the identical
# defect (#301): a ceiling nobody can reach is the bug, not a safety net.
# Read at import so a test can still patch the module attribute directly.
QUERY_TIMEOUT_SECONDS = _timeout_env("SOL2_QUERY_TIMEOUT_SECONDS", 900)


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


def _from_result(result) -> tuple[str, float | None, dict | None, bool | None, str | None]:
    """Pull data from the SDK's final ``ResultMessage`` only.

    ``usd`` is ``None`` when the message carries no cost field at all, never
    a bare 0.0, so a caller can tell "the SDK said zero" from "the SDK never
    told us" (#539).
    """
    if isinstance(result, str):
        return result, None, None, None, None
    text = getattr(result, "result", None) or ""
    raw_cost = getattr(result, "total_cost_usd", None)
    usd = None if raw_cost is None else float(raw_cost)
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
        # #539. Defined before the try, so a raise anywhere below (setup, a
        # dropped connection mid-stream, or a bug after the query returned)
        # still leaves the outer `except` able to say what this turn had
        # spent, instead of falling back to a bare 0.0 that looks free.
        progress: dict[str, float | None] = {"usd": None}
        raw_events: list[str] = []
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

            started = time.monotonic()

            async def collect() -> tuple[str, float | None, dict | None, bool, str | None]:
                result_text = ""
                usd = None
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
                        if cost is not None:
                            # #539, follow-up 6. `total_cost_usd` is
                            # cumulative, so a later message should never
                            # report less than an earlier one; `max` is the
                            # guard against a stray 0.0 overwriting a real
                            # cost already seen, the same shape as the
                            # `_bookkeep` guard in `e2e_t001.py`.
                            usd = cost if usd is None else max(usd, cost)
                            progress["usd"] = usd
                        if parsed is not None:
                            structured = parsed
                        if error is True:
                            ok = False
                        if stop:
                            # #568. This is the terminal ResultMessage: the
                            # SDK named a controlled ceiling (max turns or
                            # cost budget). Stop asking the generator for
                            # anything past it rather than trust it to close
                            # on its own, which round 4 shows can take the
                            # rest of the timeout window.
                            reason = stop
                            ok = False
                            break
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
                elapsed = time.monotonic() - started
                spent = progress["usd"]
                return DoerResult(
                    ok=False,
                    usd=spent,
                    output=(
                        f"agent sdk query timed out after {self.timeout_seconds:.0f} seconds "
                        f"(elapsed={elapsed:.0f}s, events={len(raw_events)}, "
                        f"usd={'unknown' if spent is None else format(spent, '.4f')}). "
                        f"Raise SOL2_QUERY_TIMEOUT_SECONDS or shrink the prompt."
                    ),
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
            # #539. `progress["usd"]` survives a raise anywhere in the try
            # block above, including one after the query itself answered, so
            # a backend that spent money before failing still reports it.
            return DoerResult(
                ok=False,
                usd=progress["usd"],
                output=f"agent sdk backend failed: {exc}",
                raw_output="\n".join(raw_events),
            )

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
        planner: AgentSdkBackend | None = None,
    ):
        self.test = test
        self.code = code
        self.judge_backend = judge
        self.planner = planner

    def _for(self, allow: list[str]) -> AgentSdkBackend:
        # A9 (#437 #422). The planner's write scope is `steps.jsonl`, the same
        # scope `contract.py` declares for the role. Route on it before the
        # test/code branches, so an unconfigured planner fails closed rather
        # than falling through to "no backend for this scope".
        if any(pattern == steps.STEPS_FILE for pattern in allow):
            if self.planner is None:
                raise ValueError("no Agent SDK planner backend is configured")
            return self.planner
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

    def plan(self, *, repo: Path, prompt: str) -> DoerResult:
        """Route to the planner graph and run it with the planner's own scope."""
        return self._for([steps.STEPS_FILE]).run(
            repo=repo, prompt=prompt, allow=[steps.STEPS_FILE]
        )

