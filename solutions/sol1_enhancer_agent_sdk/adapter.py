"""A `doers.Backend` for this folder's `ClaudeAgentOptions`.

The SDK streams tool events beside final results. A doer candidate must be one
ticket-shaped block: prefer the parent's final ``ResultMessage.result`` when
it is a ticket, otherwise use the last ticket-shaped message from the named
subagent. Joining every event is how Grep output became an issue body.

`usd` is filled from `total_cost_usd`. The field existed and was always 0.
`structured` is filled from `structured_output` when the judge query set
`output_format`. `stop_reason` is set when the SDK ended the query on
max turns or max budget, so Python can escalate rather than retry.

#571, copying sol2's #568 fix. `collect()` returns the moment a
`ResultMessage` arrives, success, an error, or a controlled stop (max turns
or cost budget) alike, instead of continuing to ask the generator for
whatever comes next. A query that ends on `error_max_budget_usd` in under a
minute and then sits open, quiet, used to run until `QUERY_TIMEOUT_SECONDS`
turned a one-minute, evidenced "cost budget spent" into a 900-second "query
timeout", discarding the real reason; a successful query followed by a
quiet stream lost its answer the same way. A stream with no terminal
`ResultMessage` at all is unaffected: nothing here short-circuits that
wait, and `asyncio.wait_for`'s own ceiling is still what ends it. A partial,
non-terminal event (a stream event, a subagent message) is never a
`ResultMessage` and so can never end the stream early either.

#578. Not every `ResultMessage` is the run's last one, though. The
installed `claude_agent_sdk`'s own `Query._read_messages` (upstream #1088)
holds a result frame back from closing the run while a delegated `Task` it
spawned is still running, and lets a later result frame close it once that
work drains. `collect()` mirrors that bookkeeping so a `Task` still in
flight cannot truncate the run at its first, mid-flight result.
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

# #578. Matches the installed SDK's own `DEFERRING_TASK_TYPES` and
# `TERMINAL_TASK_STATUSES` (see `Query._track_task_lifecycle`, upstream
# #1088): only a delegated `Task` of one of these types can hold a result
# frame back from ending the run, and only these statuses count as it
# having finished.
_DEFERRING_TASK_TYPES = frozenset({"local_agent", "local_workflow"})
_TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "stopped", "killed"})


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
            f"[sol1] {name}={raw!r} is not an integer; using the default {default}s",
            file=sys.stderr,
            flush=True,
        )
        return default


# #541, matching #301 (sol3) and #539 (sol2). A ceiling nobody can reach is
# the bug, not a safety net. Read at import so a test can still patch the
# module attribute directly.
QUERY_TIMEOUT_SECONDS = _timeout_env("SOL1_QUERY_TIMEOUT_SECONDS", 900)


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


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    """Tracked diffs plus untracked files.

    `git diff --name-only` misses a new candidate file that was never added.
    The doer in this port does not write, Python does, but the second line of
    defense still has to see a file the first line missed.
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
    names = set()
    for stdout in (diff.stdout, extra.stdout):
        names.update(line for line in stdout.splitlines() if line)
    return names


def _from_result(result) -> tuple[str, float | None, dict | None, bool | None, str | None]:
    """Pull data from the SDK's final ``ResultMessage`` only.

    Returns (text, usd, structured, error_or_None, stop_reason_or_None).
    ``usd`` is ``None`` when the message carries no cost field at all, never
    a bare 0.0, so a caller can tell "the SDK said zero" from "the SDK never
    told us" (#541, matching #539's fix in sol2).
    """
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


def _ticket_shaped(text: str) -> bool:
    """True only for the complete markdown ticket a doer is allowed to return."""
    return text.lstrip().startswith(("---", "# "))


def _text_blocks(message) -> list[str]:
    """Text blocks from one event, kept separate so they can never be joined."""
    return [
        str(block.text)
        for block in (getattr(message, "content", None) or [])
        if getattr(block, "text", None) is not None
    ]


def _track_task_lifecycle(message, inflight: set[str]) -> None:
    """Mirror the installed SDK's own task bookkeeping for one message.

    #578. `Query._track_task_lifecycle` (upstream #1088) holds a result
    frame back from closing the run while a delegated `Task` it spawned is
    still running: `task_started` marks one in flight, and a
    `task_notification` or a `task_updated` patch naming a terminal status
    clears it (`discard` keeps the pair idempotent, since not every
    terminal task emits both). Only `local_agent`/`local_workflow` task
    types are tracked, matching the SDK's own `DEFERRING_TASK_TYPES`; a
    background shell or a long-lived monitor never reaches a terminal
    status and would otherwise hold the run open forever.
    """
    task_id = getattr(message, "task_id", None)
    if not task_id:
        return
    subtype = getattr(message, "subtype", None)
    if subtype == "task_started":
        if getattr(message, "task_type", None) in _DEFERRING_TASK_TYPES:
            inflight.add(task_id)
    elif subtype == "task_notification":
        inflight.discard(task_id)
    elif subtype == "task_updated":
        if getattr(message, "status", None) in _TERMINAL_TASK_STATUSES:
            inflight.discard(task_id)


def _is_run_boundary(message, inflight: set[str]) -> bool:
    """Whether a terminal `ResultMessage` ends the run, not just a turn.

    #578. Mirrors `Query._read_messages` (upstream #1088): a result that
    arrives while a delegated task is still in flight only closes one turn,
    and a later result closes the run once it drains. `terminal_reason` is
    the CLI's own signal that the query loop ended, and is honored on its
    own even if this port's bookkeeping has not caught up.
    """
    return not inflight or bool(getattr(message, "terminal_reason", None))


def _raw_event(message) -> str:
    """A local diagnostic record, intentionally never used as a candidate."""
    return f"## {type(message).__name__}\n\n{message!r}\n"


class AgentSdkBackend(Backend):
    """Runs a named subagent through `claude_agent_sdk.query`."""

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
            from claude_agent_sdk import ResultMessage, query  # noqa: PLC0415  (optional dependency)

            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            options = self.options
            fields = (
                {item.name for item in dataclasses.fields(options)}
                if dataclasses.is_dataclass(options)
                else set()
            )
            return_subagent_text = bool(extra.pop("return_subagent_text", False))
            overlay = {
                key: value
                for key, value in extra.items()
                if value is not None and (not fields or key in fields)
            }
            if overlay and dataclasses.is_dataclass(options):
                options = dataclasses.replace(options, **overlay)

            async def collect() -> tuple[str, float | None, dict | None, bool, str | None, str]:
                result_text = ""
                subagent_tickets: list[str] = []
                usd = None
                structured = None
                ok = True
                reason = None
                inflight_tasks: set[str] = set()
                async for message in query(prompt=prompt, options=options):
                    raw_events.append(_raw_event(message))
                    _track_task_lifecycle(message, inflight_tasks)
                    if not isinstance(message, ResultMessage):
                        if return_subagent_text and getattr(message, "parent_tool_use_id", None):
                            subagent_tickets.extend(
                                text for text in _text_blocks(message) if _ticket_shaped(text)
                            )
                        continue
                    text, cost, parsed, error, stop = _from_result(message)
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
                    # #571. `message` is a `ResultMessage`: the SDK's one
                    # terminal record for this query, success, an error, or
                    # a controlled ceiling alike. Stop asking the generator
                    # for anything past it rather than trust the stream to
                    # close on its own, which can take the rest of the
                    # timeout window. A non-`ResultMessage` event above never
                    # reaches here (the `continue` at the top sends it back
                    # around), so a partial, non-terminal event cannot end
                    # the stream early. #578: a `ResultMessage` still only
                    # ends the run when `_is_run_boundary` agrees no
                    # delegated task is holding it open; a result that
                    # arrives mid-flight only closes this turn.
                    if _is_run_boundary(message, inflight_tasks):
                        break
                if return_subagent_text:
                    output = (
                        result_text
                        if _ticket_shaped(result_text)
                        else (subagent_tickets[-1] if subagent_tickets else result_text)
                    )
                else:
                    output = result_text
                return output, usd, structured, ok, reason, "\n".join(raw_events)

            started = time.monotonic()
            try:
                output, usd, structured, ok, reason, raw_output = asyncio.run(
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
                        f"Raise SOL1_QUERY_TIMEOUT_SECONDS or shrink the prompt."
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
                raw_output=raw_output,
            )
        except Exception as exc:  # graceful failure, the way CliBackend.run fails
            # #541. `progress["usd"]` survives a raise anywhere in the try
            # block above, including one after the query itself answered, so
            # a backend that spent money before failing still reports it.
            return DoerResult(
                ok=False,
                usd=progress["usd"],
                output=f"agent sdk backend failed: {exc}",
                raw_output="\n".join(raw_events),
            )
