"""A `doers.Backend` for this folder's `ClaudeAgentOptions`.

Issue #2: this folder's `doers.py` `build(spec)` now accepts an already-built
`Backend` and passes it through unchanged, so a runtime port can plug in its
own doer. `Backend` and `DoerResult` are copied here rather than imported —
one more standalone folder, not a ninth shared file.

Reads `ResultMessage` instead of joining the event stream. Overlay `**extra`
onto a copy of the options so a judge schema can land without leaking into
the next turn. Union untracked files into the diff so a fixer that adds a
file is visible to the second line of defense. Bound the query so one hang
does not starve later attempts.

The SDK is optional and not installed in this environment, so the import
stays lazy (same style `roles.py` already uses for `AgentDefinition` et al.).
Nothing here is exercised without it: `python loop.py --table-only` never
touches this module's `run()`.

#571, copying sol2's #568 fix. `collect()` returns the moment a
`ResultMessage` arrives, success, an error, or a controlled stop (max turns
or cost budget) alike, instead of continuing to ask the generator for
whatever comes next. A `ResultMessage` is the SDK's one terminal record for
a query; nothing legitimate follows it. A query that ends on
`error_max_budget_usd` in under a minute and then sits open, quiet, used to
turn a one-minute, evidenced "cost budget spent" into a 900-second "query
timeout", discarding the real reason; a successful query followed by a
quiet stream lost its answer the same way. A stream with no terminal
`ResultMessage` at all is unaffected: nothing here short-circuits that
wait, and `asyncio.wait_for`'s own ceiling is still what ends it. A
partial, non-terminal event is never a `ResultMessage`, so it still cannot
end the stream early.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from write_scope import WriteScope

_TURN_STOP = {"error_max_turns", "error_max_turns_assistant"}
_COST_STOP = {"error_max_budget_usd", "error_max_budget"}


def _timeout_env(name: str, default: int) -> int:
    """Read an integer timeout from the environment, never raising at import.

    #541. A bad value here used to raise `ValueError` at import time and take
    the whole module down with it. A logged fallback keeps the process alive,
    the same way a missing dependency reports as a result, not a traceback.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(
            f"[sol4] {name}={raw!r} is not an integer; using the default {default}s",
            file=sys.stderr,
            flush=True,
        )
        return default


# #541, matching #301 (sol3) and #539 (sol2). A ceiling nobody can reach is
# the bug, not a safety net. Read at import so a test can still patch the
# module attribute directly.
QUERY_TIMEOUT_SECONDS = _timeout_env("SOL4_QUERY_TIMEOUT_SECONDS", 900)


@dataclass
class DoerResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    # #541. `None` means the backend never answered a turn (a timed-out
    # query, a raised exception), which is not the same as an answered turn
    # that cost nothing. The default stays 0.0: an offline classroom backend
    # really did answer, for free.
    usd: float | None = 0.0
    ok: bool = True
    structured: dict | None = None
    stop_reason: str | None = None
    raw_output: str = ""


def _from_result(result) -> tuple[str, float | None, dict | None, bool | None, str | None]:
    """Pull data from the SDK's final ``ResultMessage`` only.

    `str(message)` flattened cost, text, and events into a log line. The cost
    was the expensive loss: `fixer.py` calls `boss.spend(result.usd)` and
    `gates.decide` has a live `usd_left <= 0` branch, so a `usd` pinned at zero
    meant the money gate could never fire.

    ``usd`` is ``None`` when the message carries no cost field at all, never
    a bare 0.0, so a caller can tell "the SDK said zero" from "the SDK never
    told us" (#541, matching #539's fix in sol2).
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
    return f"## {type(message).__name__}\n\n{message!r}\n"


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    """Tracked diffs plus untracked files.

    The fixer usually edits existing files under `app/**`. A brand new file is
    still a write, and `git diff --name-only` never sees it.
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


class AgentSdkBackend(Backend):
    """Runs the code_implementer role through `claude_agent_sdk.query`.

    `options` is what this folder's `build(contract)` already returns.
    """

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        # #541. Defined before the try, so a raise anywhere below (setup, a
        # dropped connection mid-stream, or a bug after the query returned)
        # still leaves the outer `except` able to say what this turn had
        # spent, instead of falling back to a bare 0.0 that looks free.
        progress: dict[str, float | None] = {"usd": None}
        raw_events: list[str] = []
        try:
            from claude_agent_sdk import ResultMessage, query  # noqa: PLC0415

            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            options = self.options
            fields = (
                {item.name for item in dataclasses.fields(options)}
                if dataclasses.is_dataclass(options)
                else set()
            )
            overlay = {
                key: value
                for key, value in extra.items()
                if value is not None and (not fields or key in fields)
            }
            if overlay and dataclasses.is_dataclass(options):
                options = dataclasses.replace(options, **overlay)

            async def collect() -> tuple[str, float | None, dict | None, bool, str | None]:
                result_text = ""
                usd = None
                structured = None
                ok = True
                reason = None
                async for message in query(prompt=prompt, options=options):
                    raw_events.append(_raw_event(message))
                    if not isinstance(message, (ResultMessage, str)):
                        continue
                    text, cost, parsed, error, stop = _from_result(message)
                    if text:
                        result_text = text
                    if cost is not None:
                        # `total_cost_usd` is cumulative, so a later message
                        # should never report less than an earlier one; the
                        # `max` guards against a stray 0.0 overwriting a real
                        # cost already seen.
                        usd = cost if usd is None else max(usd, cost)
                        progress["usd"] = usd
                    if parsed is not None:
                        structured = parsed
                    if error is True:
                        ok = False
                    if stop:
                        reason = stop
                        ok = False
                    if isinstance(message, ResultMessage):
                        # #571. A `ResultMessage` is the SDK's one terminal
                        # record for this query: success, an error, or a
                        # controlled ceiling (max turns or cost budget)
                        # alike. Stop asking the generator for anything
                        # past it rather than trust the stream to close on
                        # its own, which can take the rest of the timeout
                        # window. A bare `str` is accepted above for its
                        # text but is never terminal, so it cannot end the
                        # stream early.
                        break
                return result_text, usd, structured, ok, reason

            started = time.monotonic()
            try:
                output, usd, structured, ok, reason = asyncio.run(
                    asyncio.wait_for(collect(), timeout=QUERY_TIMEOUT_SECONDS)
                )
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - started
                spent = progress["usd"]
                return DoerResult(
                    ok=False,
                    usd=spent,
                    output=(
                        f"agent sdk query timed out after {QUERY_TIMEOUT_SECONDS} seconds "
                        f"(elapsed={elapsed:.0f}s, events={len(raw_events)}, "
                        f"usd={'unknown' if spent is None else format(spent, '.4f')}). "
                        f"Raise SOL4_QUERY_TIMEOUT_SECONDS or shrink the prompt."
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
        except Exception as exc:
            # #541. `progress["usd"]` survives a raise anywhere in the try
            # block above, including one after the query itself answered, so
            # a backend that spent money before failing still reports it.
            return DoerResult(
                ok=False,
                usd=progress["usd"],
                output=f"agent sdk backend failed: {exc}",
                raw_output="\n".join(raw_events),
            )
