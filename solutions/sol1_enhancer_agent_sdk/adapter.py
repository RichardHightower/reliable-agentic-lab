"""A `doers.Backend` for this folder's `ClaudeAgentOptions`.

The SDK streams tool events beside final results. A doer candidate must be one
ticket-shaped block: prefer the parent's final ``ResultMessage.result`` when
it is a ticket, otherwise use the last ticket-shaped message from the named
subagent. Joining every event is how Grep output became an issue body.

`usd` is filled from `total_cost_usd`. The field existed and was always 0.
`structured` is filled from `structured_output` when the judge query set
`output_format`. `stop_reason` is set when the SDK ended the query on
max turns or max budget, so Python can escalate rather than retry.
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
QUERY_TIMEOUT_SECONDS = 180


@dataclass
class DoerResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    usd: float = 0.0
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


def _from_result(result) -> tuple[str, float, dict | None, bool | None, str | None]:
    """Pull data from the SDK's final ``ResultMessage`` only.

    Returns (text, usd, structured, error_or_None, stop_reason_or_None).
    """
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


def _raw_event(message) -> str:
    """A local diagnostic record, intentionally never used as a candidate."""
    return f"## {type(message).__name__}\n\n{message!r}\n"


class AgentSdkBackend(Backend):
    """Runs a named subagent through `claude_agent_sdk.query`."""

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
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

            raw_events: list[str] = []

            async def collect() -> tuple[str, float, dict | None, bool, str | None, str]:
                result_text = ""
                subagent_tickets: list[str] = []
                usd = 0.0
                structured = None
                ok = True
                reason = None
                async for message in query(prompt=prompt, options=options):
                    raw_events.append(_raw_event(message))
                    if not isinstance(message, ResultMessage):
                        if return_subagent_text and getattr(message, "parent_tool_use_id", None):
                            subagent_tickets.extend(
                                text for text in _text_blocks(message) if _ticket_shaped(text)
                            )
                        continue
                    text, cost, parsed, error, stop = _from_result(message)
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
                if return_subagent_text:
                    output = (
                        result_text
                        if _ticket_shaped(result_text)
                        else (subagent_tickets[-1] if subagent_tickets else result_text)
                    )
                else:
                    output = result_text
                return output, usd, structured, ok, reason, "\n".join(raw_events)

            try:
                output, usd, structured, ok, reason, raw_output = asyncio.run(
                    asyncio.wait_for(collect(), timeout=QUERY_TIMEOUT_SECONDS)
                )
            except asyncio.TimeoutError:
                return DoerResult(
                    ok=False,
                    output=f"agent sdk query timed out after {QUERY_TIMEOUT_SECONDS} seconds",
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
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")
