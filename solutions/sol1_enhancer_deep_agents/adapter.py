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

import contextlib
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import roles
from write_scope import WriteScope


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
    # invoke, a raised exception), which is not the same as an answered turn
    # that cost nothing. The default stays 0.0: an offline classroom backend
    # really did answer, for free.
    usd: float | None = 0.0
    ok: bool = True
    timed_out: bool = False


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return set(proc.stdout.splitlines())


class QueryTimedOut(TimeoutError):
    """The one graph invocation exceeded this ticket's wall-clock allowance."""


@contextlib.contextmanager
def _wall_clock_timeout(seconds: float):
    """Interrupt a synchronous graph call on platforms that support SIGALRM.

    A worker thread cannot safely cancel a blocked HTTP request, and letting its
    executor wait would recreate the hang this guard is meant to prevent.
    LangGraph runs this synchronous adapter on the main thread, so SIGALRM
    interrupts the call directly on macOS and Linux. On platforms without it,
    the provider-level timeout remains the fallback.
    """
    can_alarm = (
        seconds > 0
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    if not can_alarm:
        yield
        return

    def expired(_signum, _frame):
        raise QueryTimedOut(f"Deep Agents query exceeded {seconds:g} seconds")

    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def _call_kind(prompt: str) -> tuple[str, str]:
    role = "judge" if "judge subagent" in prompt else "doer"
    match = re.search(r"(?:tickets/|ticket )(T\d+)", prompt)
    return role, match.group(1) if match else "unknown"


def _trace(repo: Path, *, role: str, ticket: str, prompt: str, result: str) -> None:
    """Persist the one bounded call's prompt and returned text for diagnosis."""
    path = repo / ".harness" / f"last-deep-agents-{role}-{ticket}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Deep Agents {role} call for {ticket}\n\n## Prompt\n\n{prompt}\n\n## Result\n\n{result}\n",
        encoding="utf-8",
    )


def _messages(result):
    """The message list, however this runtime wrapped it.

    `.invoke` returns a state dict on the graph path and can return an object
    elsewhere. Reading only `result["messages"]` makes every non-dict result
    look empty, which reads as a silent success.
    """
    if isinstance(result, dict):
        return result.get("messages")
    messages = getattr(result, "messages", None)
    if messages is None and hasattr(result, "get"):
        messages = result.get("messages")
    return messages


def _role_of(message) -> str:
    return (
        getattr(message, "type", None)
        or (message.get("role") if isinstance(message, dict) else None)
        or ""
    )


def _content_of(message):
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", "")


def _content_text(content) -> str:
    """Flatten message content into the text the model meant to send.

    Content is a string, a list of blocks, or an object carrying `.text`. A
    block is a string, a dict, or an object. Every shape that holds text has to
    come back, because a dropped block does not raise. It returns a shorter
    answer that still parses, and the loop acts on half a reply.

    A dict block with no `type` key is the common case. Testing
    `block.get("type") == "text"` drops it.
    """
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
                if "text" in block:
                    parts.append(block["text"])
            else:
                text = getattr(block, "text", None)
                parts.append(text if text is not None else str(block))
        return "".join(parts)
    text = getattr(content, "text", None)
    return text if text is not None else str(content)


def last_ai_text(result) -> str:
    """The answer this run produced. Not an older one, not the state repr.

    Walk backward and take the first non-empty content from an assistant or a
    tool message. One line, and it is the only rule that survives all four
    shapes a graph actually returns.

    Three ways to get this wrong, and this repo has shipped two of them.

    `str(result)` is a repr of every message, every tool call, and every id.
    Handing that to a JSON parser is how a working loop starts failing on
    nothing anyone changed.

    `messages[-1]` reads whichever message happens to be last without asking
    what it is.

    Walking backward for the last non-empty *assistant* message returns an
    answer from BEFORE the last tool ran. A tool-calling assistant message
    carries `tool_calls` and empty content, so that walk steps over it onto an
    earlier turn. A stale verdict that parses is worse than no verdict, because
    nothing reports it.

    A ToolMessage exists only because an assistant asked for it. So "the model
    has not spoken since the tool ran" and "the tool holds the answer" are the
    same state, and a subagent with a `response_format` puts its structured
    result exactly there, JSON-serialized.
    """
    if isinstance(result, str):
        return result
    messages = _messages(result)
    if not messages:
        return str(result)
    for message in reversed(messages):
        if _role_of(message) not in ("ai", "assistant", "tool"):
            continue
        text = _content_text(_content_of(message)).strip()
        if text:
            return text
    # Nothing carried content. The last message is the best answer left, and
    # returning "" here would look like a successful empty run.
    return _content_text(_content_of(messages[-1]))


def _usage_cost(usage: dict) -> float:
    """One usage dict's cost, reading the first cost key it carries."""
    for key in ("total_cost", "total_cost_usd", "cost"):
        if usage.get(key) is None:
            continue
        try:
            return float(usage[key])
        except (TypeError, ValueError):
            continue
    return 0.0


def last_usd(result) -> float:
    """What the run cost, summed from usage metadata. Missing is zero.

    Zero, not a guess. A budget built on estimated costs is wrong in whichever
    direction is least convenient, and this number decides when the loop stops.

    `usage_metadata` is not always a dict. Testing `key in usage` on an object
    raises, and a backend that raises takes the loop down with it.
    """
    if isinstance(result, dict) and result.get("usd") is not None:
        try:
            return float(result["usd"])
        except (TypeError, ValueError):
            pass
    total = 0.0
    for message in _messages(result) or []:
        usage = (
            message.get("usage_metadata")
            if isinstance(message, dict)
            else getattr(message, "usage_metadata", None)
        )
        if not isinstance(usage, dict):
            continue
        total += _usage_cost(usage)
    return total


def _usage_callback():
    """#541. A callback that sums `usage_metadata` off every completed LLM
    call, so a wall-clock timeout that interrupts `agent.invoke()` mid-call
    still reports what those calls cost and how many of them ran, instead of
    losing them along with the interrupt. `agent.invoke()` returns no state
    on an interrupt or a raise, so `last_usd`, which reads the returned
    state, never gets the chance.

    Imported lazily and never let to raise: this module has to stay
    importable, and this handler safe to attach, with no `deepagents` or
    `langchain_core` installed, the same as every offline test already runs.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler  # noqa: PLC0415
    except ImportError:
        return None

    class UsageCallback(BaseCallbackHandler):
        def __init__(self):
            self.total_usd = 0.0
            self.calls = 0
            self.saw_usage = False

        def on_llm_end(self, response, **kwargs):
            self.calls += 1
            try:
                for generation_list in getattr(response, "generations", None) or []:
                    for generation in generation_list:
                        message = getattr(generation, "message", None)
                        usage = getattr(message, "usage_metadata", None) if message else None
                        if isinstance(usage, dict):
                            self.total_usd += _usage_cost(usage)
                            self.saw_usage = True
            except Exception:
                # A telemetry side channel must never crash the run it is
                # only supposed to be watching.
                pass

    return UsageCallback()


def _invoke_config(usage) -> dict:
    """`{}` when no callback is available, exactly matching `agent.invoke(payload)`
    with no `config=` at all -- the shape every existing test with no
    `langchain_core` installed already pins."""
    return {"callbacks": [usage]} if usage is not None else {}


def _describe_exc(exc: Exception) -> str:
    """#541, matching #539's fix in sol2. The exception's own class name
    first, so a raised backend reads as one, instead of surviving only in a
    message a reader would have to already know to look for."""
    return f"{type(exc).__name__}: {exc}"


class DeepAgentsBackend(Backend):
    """Runs the doer role through a Deep Agents agent's `.invoke`.

    `agent` is what this folder's `build_agent(contract, loop=LOOP)` already
    returns.
    """

    name = "deep_agents"

    def __init__(self, agent, *, timeout_s: float = QUERY_TIMEOUT_SECONDS):
        self.agent = agent
        self.timeout_s = timeout_s

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        role, ticket = _call_kind(prompt)
        print(f"deep-agents {ticket} {role}: started", flush=True)
        # #541. Attached whether or not the wall clock ever fires: `on_llm_end`
        # fires per completed model turn, well before a timeout or a raise
        # (which only happens after some number of turns already ran) reaches
        # this method at all.
        usage = _usage_callback()
        started = time.monotonic()
        try:
            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            payload = {"messages": [{"role": "user", "content": prompt}]}
            config = _invoke_config(usage)
            # `roles.write_allow` narrows every write tool to this turn's paths.
            # Without it the tool falls back to the role's row, which is where a
            # doer can reach the real ticket instead of its candidate.
            with roles.write_allow(allow), _wall_clock_timeout(self.timeout_s):
                result = (
                    self.agent.invoke(payload, config=config)
                    if config
                    else self.agent.invoke(payload)
                )
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            output = last_ai_text(result)
            _trace(repo, role=role, ticket=ticket, prompt=prompt, result=output)
            print(
                f"deep-agents {ticket} {role}: completed in {time.monotonic() - started:.1f}s",
                flush=True,
            )
            return DoerResult(wrote=wrote, output=output, usd=last_usd(result))
        except QueryTimedOut as exc:
            # #541. `agent.invoke()` was interrupted mid-call and never
            # returned a state, so there is no `last_usd(result)` to read.
            # `usage` still saw every model call that finished before the
            # interrupt, so a timeout reports elapsed seconds, how many of
            # those calls ran, and what they spent, instead of a bare 0.0
            # or a message with none of that.
            elapsed = time.monotonic() - started
            spent = usage.total_usd if usage is not None and usage.saw_usage else None
            events = usage.calls if usage is not None else 0
            message = (
                f"{exc} (elapsed={elapsed:.0f}s, events={events}, "
                f"usd={'unknown' if spent is None else format(spent, '.4f')}). "
                f"Raise SOL1_QUERY_TIMEOUT_SECONDS or shrink the prompt."
            )
            _trace(repo, role=role, ticket=ticket, prompt=prompt, result=message)
            print(f"deep-agents {ticket} {role}: timed out", flush=True)
            return DoerResult(ok=False, timed_out=True, usd=spent, output=message)
        # Graceful failure, mirrors CliBackend.run. A backend that raises
        # takes the loop down with it.
        except Exception as exc:
            # #541, matching #539's fix in sol2. A raise means `invoke()`
            # never answered a final state, so `usd` is `None`, not the 0.0
            # that reads as "this turn was free" -- unless `usage` actually
            # saw a completed model turn before the raise, in which case
            # that spend is real and reporting `None` would discard it.
            # `_describe_exc` names the exception class so a caller does not
            # have to guess whether this was a raised backend or an honest
            # empty reply.
            spent = usage.total_usd if usage is not None and usage.saw_usage else None
            message = f"deep agents backend failed: {_describe_exc(exc)}"
            _trace(repo, role=role, ticket=ticket, prompt=prompt, result=message)
            print(f"deep-agents {ticket} {role}: failed: {exc}", flush=True)
            return DoerResult(ok=False, usd=spent, output=message)
