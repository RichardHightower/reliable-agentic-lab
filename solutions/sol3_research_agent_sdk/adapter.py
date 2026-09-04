"""A backend for this folder's `ClaudeAgentOptions`.

Reads `ResultMessage` instead of joining the event stream. Prefer
`structured_output` when a schema fired. Bound the query so one hang does
not starve later questions.

    usd            from `total_cost_usd`
    structured     from `structured_output`, when the turn set `output_format`
    stop_reason    when the SDK ended the query on max turns, max budget, or timeout
    raw_output     every event, as diagnostics, never as the answer

Write tracking walks the filesystem rather than asking git. sol1 tracks writes
with `git diff` because it points at a repo clone. A research run writes into a
plain work directory that was never `git init`ed, where every git command
returns empty and the second line of defense silently reports nothing.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from write_scope import WriteScope

_TURN_STOP = {"error_max_turns", "error_max_turns_assistant"}
_COST_STOP = {"error_max_budget_usd", "error_max_budget"}

# One outline query against a real 48-hit corpus took about 600 seconds. The old
# 180-second ceiling killed every live run before the first phase finished, so a
# default nobody can reach was itself the defect. Read at import so a test can
# still patch the module attribute.
QUERY_TIMEOUT_SECONDS = int(os.environ.get("SOL3_QUERY_TIMEOUT_SECONDS", "900"))

# How often a running query says it is still alive. A query that hangs emits no
# events, which is exactly when an operator needs a line on stderr.
HEARTBEAT_SECONDS = 15

# Directories a write check should never walk. `.cache` holds a clone of the
# diagram renderer, and walking it on every turn is thousands of stats for a
# tree the agent cannot write to anyway.
SKIP_DIRS = {".harness", ".cache", ".git", "__pycache__", "knowledge"}


@dataclass
class TurnResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    usd: float = 0.0
    ok: bool = True
    structured: dict | None = None
    stop_reason: str | None = None
    raw_output: str = ""
    # Telemetry. `cost_reported` separates "the turn cost nothing" from "the SDK
    # never told us", which a bare 0.0 hides.
    cost_reported: bool = False
    elapsed_s: float = 0.0
    prompt_chars: int = 0
    events: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class Backend:
    name = "backend"

    def run(self, *, root: Path, prompt: str, allow: list[str], **extra) -> TurnResult:
        raise NotImplementedError


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every file under `root`, by size and modification time.

    Comparing the pair catches an overwrite that keeps the same length, which a
    name-only listing misses.
    """
    root = Path(root)
    if not root.exists():
        return {}
    found: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        found[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return found


def _changed(before: dict, after: dict) -> list[str]:
    return sorted(name for name, value in after.items() if before.get(name) != value)


def _from_message(message) -> tuple[str, float | None, dict | None, bool | None, str | None]:
    """Pull text, cost, structured output, error flag, and stop reason.

    The cost is `None` when the SDK reported no cost field at all. A caller that
    logs 0.0 there cannot tell a free turn from a broken cost path.
    """
    if isinstance(message, str):
        return message, None, None, None, None
    text = getattr(message, "result", None)
    if text is None:
        text = ""
    raw_cost = getattr(message, "total_cost_usd", None)
    usd = None if raw_cost is None else float(raw_cost)
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
    return str(message), None, None, None, None


def _raw_event(message) -> str:
    return f"## {type(message).__name__}\n\n{message!r}\n"


def _tokens(message) -> tuple[int, int]:
    """Input and output token counts, when the SDK reports a usage block."""
    usage = getattr(message, "usage", None)
    if not isinstance(usage, dict):
        return 0, 0
    try:
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    except (TypeError, ValueError):
        return 0, 0


async def _heartbeat(progress: dict, role: str) -> None:
    """Say the query is still running, about every `HEARTBEAT_SECONDS`.

    This runs as its own task rather than inside the event loop body. A query
    that stalls waiting on the model produces no events, and a heartbeat driven
    by events would go quiet in the one case it exists for.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        print(
            f"[sol3] t+{time.monotonic() - progress['started']:.0f}s role={role} "
            f"events={progress['events']} last={progress['last']} "
            f"usd={progress['usd']:.2f}",
            file=sys.stderr,
            flush=True,
        )


class AgentSdkBackend(Backend):
    """Runs a named subagent through `claude_agent_sdk.query`."""

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, root: Path, prompt: str, allow: list[str], **extra) -> TurnResult:
        try:
            from claude_agent_sdk import ResultMessage, query  # noqa: PLC0415

            scope = WriteScope(allow=list(allow))
            before = _snapshot(root)
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
            # `role` rides in on `extra` and is filtered out of the options
            # overlay below, because it is not a field of the SDK options.
            role = str(extra.get("role") or "?")
            progress = {"started": time.monotonic(), "events": 0, "last": "-", "usd": 0.0}

            async def collect() -> tuple[str, float, bool, dict | None, bool, str | None, int, int]:
                result_text = ""
                usd = 0.0
                reported = False
                structured = None
                ok = True
                reason = None
                tokens_in = tokens_out = 0
                beat = asyncio.ensure_future(_heartbeat(progress, role))
                try:
                    async for message in query(prompt=prompt, options=options):
                        raw_events.append(_raw_event(message))
                        progress["events"] += 1
                        progress["last"] = type(message).__name__
                        got_in, got_out = _tokens(message)
                        tokens_in += got_in
                        tokens_out += got_out
                        if not isinstance(message, (ResultMessage, str)):
                            continue
                        text, cost, parsed, error, stop = _from_message(message)
                        if parsed is not None:
                            structured = parsed
                        if text:
                            result_text = text
                        if cost is not None:
                            usd = cost
                            reported = True
                            progress["usd"] = cost
                        if error is True:
                            ok = False
                        if stop:
                            reason = stop
                            ok = False
                finally:
                    beat.cancel()
                return result_text, usd, reported, structured, ok, reason, tokens_in, tokens_out

            started = time.monotonic()
            try:
                (
                    output,
                    usd,
                    reported,
                    structured,
                    ok,
                    reason,
                    tokens_in,
                    tokens_out,
                ) = asyncio.run(asyncio.wait_for(collect(), timeout=QUERY_TIMEOUT_SECONDS))
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - started
                return TurnResult(
                    ok=False,
                    output=(
                        f"agent sdk query timed out after {QUERY_TIMEOUT_SECONDS} seconds "
                        f"(role={role}, elapsed={elapsed:.0f}s, events={len(raw_events)}, "
                        f"prompt={len(prompt)} chars). Raise SOL3_QUERY_TIMEOUT_SECONDS "
                        f"or shrink the prompt."
                    ),
                    stop_reason="query timeout",
                    raw_output="\n".join(raw_events),
                    elapsed_s=elapsed,
                    prompt_chars=len(prompt),
                    events=len(raw_events),
                )
            elapsed = time.monotonic() - started
            wrote = [path for path in _changed(before, _snapshot(root)) if scope.permits(path)]
            return TurnResult(
                wrote=wrote,
                output=output,
                usd=usd,
                ok=ok,
                structured=structured,
                stop_reason=reason,
                raw_output="\n".join(raw_events),
                cost_reported=reported,
                elapsed_s=elapsed,
                prompt_chars=len(prompt),
                events=len(raw_events),
                input_tokens=tokens_in,
                output_tokens=tokens_out,
            )
        except Exception as exc:  # graceful failure. Never claim a write it did not make.
            return TurnResult(ok=False, output=f"agent sdk backend failed: {exc}")
