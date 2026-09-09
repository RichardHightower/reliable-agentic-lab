"""A `doers.Backend` for this runtime port, copied flat into this folder.

`implementer.run()` in this standalone folder takes a `doers.Backend`: a
`.name` and a `.run(*, repo, prompt, allow) -> DoerResult`. Import that local
contract so `doers.build()` recognizes this runtime adapter and passes it
through unchanged.

`deepagents` is not installed in this environment. The import stays inside
`build_agent()` (already true in `roles.py`), so `harness.py --table-only`
keeps working without it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import steps
from doers import Backend, DoerResult
from write_scope import WriteScope

# Sonnet-class list prices. LangChain never emits a cost field, so the money
# exit is dead unless we price the token counts ourselves. These numbers are
# the estimate the loop uses, not a bill.
INPUT_USD_PER_MTOK = 3.0
OUTPUT_USD_PER_MTOK = 15.0

# #562. Copied verbatim from `solutions/sol2_implementer_agent_sdk/e2e_t001.py`'s
# `_redact` (#543, widened by #545 follow-up), never imported: this port has
# no e2e script of its own to hold it, and a durable, checked-in raw log
# needs the same guarantee -- no operator home directory, no live key --
# that port already gives its own `--raw-log-dir` copies.
_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9]+")
_HOME_TILDE_PATTERN = re.compile(r"~/[^\s'\"]*")
_BEARER_PATTERN = re.compile(r"Bearer\s+\S+")
_HOME_NAME = Path.home().name


def _redact(text: str) -> str:
    """Strip what a durable, checked-in copy must never carry: the
    operator's own home directory (resolved, `~/`-shorthand, or slugified
    with `-` in place of `/`), anything shaped like a live key
    (`sk-ant-...`, `ghp_...`), and a bearer auth header."""
    text = text.replace(str(Path.home()), "<HOME>")
    text = _HOME_TILDE_PATTERN.sub("<HOME>", text)
    if _HOME_NAME:
        text = re.sub(re.escape(_HOME_NAME), "<HOME>", text)
    text = _BEARER_PATTERN.sub("Bearer <REDACTED-TOKEN>", text)
    return _KEY_PATTERN.sub("<REDACTED-KEY>", text)


def _phase_of(allow: list[str]) -> str:
    """#562. The raw log filename's own label. Mirrors the routing
    `_agent_for` does below, but as a name rather than a graph, so a raw
    log can be written even when `phase_agents` is a single plain `agent`
    (`_agent_for` returns that agent unconditionally in that case)."""
    if any(pattern == steps.STEPS_FILE for pattern in allow):
        return "plan"
    if any(pattern.startswith("tests/") for pattern in allow):
        return "test"
    if any(pattern.startswith(("app/", "src/")) for pattern in allow):
        return "code"
    return "unknown"


def _changed_files(repo: Path) -> set[str]:
    """Every path this working tree changes, including untracked files.

    `git diff --name-only` only sees tracked edits. A Deep Agents write that
    creates a new test file is the common case, and that file would vanish
    from `DoerResult.wrote` if we asked diff.
    """
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    paths: set[str] = set()
    for line in out.stdout.splitlines():
        if len(line) > 3:
            paths.add(line[3:].strip().split(" -> ")[-1])
    return paths


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


def _raw_messages(result) -> str:
    """Every message this turn produced, as diagnostics, never as the answer.

    #539. This is the proof a failed run's `.harness/` should keep; the SDK
    port's `adapter._raw_event` does the same job for its own event stream,
    and only this port's `DoerResult.raw_output` was left empty.
    """
    parts = []
    for message in _messages(result) or []:
        role = _role_of(message) or "message"
        parts.append(f"## {role}\n\n{message!r}\n")
    return "\n".join(parts)


def _usage_usd(usage: dict) -> float:
    """One message's cost. Vendor dollars first, then priced tokens."""
    for key in ("total_cost", "total_cost_usd", "cost"):
        if usage.get(key) is None:
            continue
        try:
            return float(usage[key])
        except (TypeError, ValueError):
            continue
    try:
        inp = float(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        out = float(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        return 0.0
    if inp <= 0 and out <= 0:
        return 0.0
    return (inp * INPUT_USD_PER_MTOK + out * OUTPUT_USD_PER_MTOK) / 1_000_000


def last_usd(result) -> float:
    """What the run cost.

    LangChain `usage_metadata` has token counts, not dollars. When a cost key
    is present we trust it. When only tokens are present we price them at
    Sonnet-class rates so `usd_left` can actually drop. Missing is zero, not
    a guess of a different kind.
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
        total += _usage_usd(usage)
    return total


def _describe_exc(exc: Exception) -> str:
    """#539. The exception's own class name first, so a `GraphRecursionError`
    reads as one, instead of surviving only in a message a reader would have
    to already know to look for."""
    return f"{type(exc).__name__}: {exc}"


class DeepAgentsBudgetExceeded(RuntimeError):
    """#549. Raised by the usage callback when a call's running cost passes
    its own per-call cap. This is the Deep Agents twin of the SDK port's
    `asyncio.wait_for` timeout on its per-query ceiling: the only other
    bound on one call was `recursion_limit`, a turn count, not a dollar
    figure, and the ticket's own live run spent $4.56 against a $3.00 cap
    before that structural ceiling ever fired.
    """


def _usage_callback(max_call_usd: float | None = None):
    """#543, #549. A callback that sums `usage_metadata` off every completed
    LLM call, so a `GraphRecursionError` (raised only after some number of
    model turns already ran) still reports what those turns cost, instead of
    losing them along with the exception. `agent.invoke()` returns no state
    on a raise, so `last_usd`, which reads the returned state, never gets
    the chance.

    `max_call_usd`, when given, turns the same running total into a stop
    condition: once a completed turn's cost pushes it over the cap, the
    callback raises `DeepAgentsBudgetExceeded` naming the spend so far, the
    same job the SDK's per-query `asyncio.wait_for` timeout does mid-turn.
    The check runs after a whole turn reports its cost, so the cap is a
    ceiling with up to one turn of slack, not a hard stop mid-turn.

    Imported lazily and never let to raise for a parsing failure: this
    module has to stay importable, and this handler safe to attach, with no
    `deepagents` or `langchain_core` installed, the same as every offline
    test already runs. The budget check is the one deliberate exception.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler  # noqa: PLC0415
    except ImportError:
        return None

    class UsageCallback(BaseCallbackHandler):
        # #549, judge of PR #552. langchain_core's callback manager
        # (`handle_event`/`ahandle_event`) wraps every handler call in its
        # own `except Exception`, logs a warning, and only re-raises when
        # `raise_error` is true. Without this, `DeepAgentsBudgetExceeded`
        # below never reaches `agent.invoke()`, and a live call spends
        # straight through the cap to the recursion limit, measured true
        # against langchain_core 1.6.2 for both the sync and async path.
        raise_error = True

        def __init__(self):
            self.total_usd = 0.0
            self.saw_usage = False

        def on_llm_end(self, response, **kwargs):
            try:
                for generation_list in getattr(response, "generations", None) or []:
                    for generation in generation_list:
                        message = getattr(generation, "message", None)
                        usage = getattr(message, "usage_metadata", None) if message else None
                        if isinstance(usage, dict):
                            self.total_usd += _usage_usd(usage)
                            self.saw_usage = True
            except Exception:
                # A telemetry side channel must never crash the run for a
                # parsing failure; only the deliberate budget check below
                # may raise.
                return
            if max_call_usd is not None and self.total_usd > max_call_usd:
                raise DeepAgentsBudgetExceeded(
                    f"budget_exhausted: spent ${self.total_usd:.4f} against a "
                    f"${max_call_usd:.2f} per-call cap"
                )

    return UsageCallback()


def _invoke_config(recursion_limit: int | None, usage) -> dict:
    """`{}` when neither is set, exactly matching `agent.invoke(payload)`
    with no `config=` at all -- the shape every existing test with no
    recursion limit and no `langchain_core` installed already pins."""
    config: dict = {}
    if recursion_limit:
        config["recursion_limit"] = recursion_limit
    if usage is not None:
        config["callbacks"] = [usage]
    return config


class DeepAgentsBackend(Backend):
    """Runs one role's prompt through the Deep Agents graph this folder builds."""

    name = "deep_agents"

    def __init__(
        self,
        agent=None,
        *,
        phase_agents=None,
        judge_agent=None,
        recursion_limit: int | None = None,
        max_call_usd: float | None = None,
        raw_log_dir: Path | None = None,
    ):
        if agent is None and not phase_agents:
            raise ValueError("provide an agent or one agent for each implementation phase")
        self.agent = agent
        self.phase_agents = phase_agents
        self.judge_agent = judge_agent
        self.recursion_limit = recursion_limit
        # #549. The per-call dollar cutoff, mirroring the SDK port's
        # per-query ceiling. None means no cutoff, the behavior before
        # this ticket.
        self.max_call_usd = max_call_usd
        # #562. Mirrors the SDK port's `--raw-log-dir`: when set, every call
        # writes a redacted copy of its own usage_metadata and message
        # sequence here, the same evidence `DoerResult.raw_output` already
        # carries in memory, before a killed run could lose it the way #562
        # found the SDK port's own spend was lost.
        self.raw_log_dir = raw_log_dir
        self._raw_log_calls = 0

    def _log_raw(self, raw_output: str, *, role: str) -> None:
        if not self.raw_log_dir or not raw_output:
            return
        self.raw_log_dir.mkdir(parents=True, exist_ok=True)
        self._raw_log_calls += 1
        name = f"deep-agents-raw-{self._raw_log_calls}-{role}.txt"
        (self.raw_log_dir / name).write_text(_redact(raw_output), encoding="utf-8")

    def _agent_for(self, allow: list[str]):
        """Choose the graph whose cast matches the driver's current phase."""
        if self.phase_agents is None:
            return self.agent
        # A9 (#437 #422). The planner's write scope is `steps.jsonl`, the same
        # scope `contract.py` declares for the role. Route on it before the
        # test/code branches, so an unconfigured planner fails closed rather
        # than a bare KeyError on `self.phase_agents["plan"]`.
        if any(pattern == steps.STEPS_FILE for pattern in allow):
            if "plan" not in self.phase_agents:
                raise ValueError("no Deep Agents planner graph is configured")
            return self.phase_agents["plan"]
        if any(pattern.startswith("tests/") for pattern in allow):
            phase = "test"
        elif any(pattern.startswith(("app/", "src/")) for pattern in allow):
            phase = "code"
        else:
            raise ValueError(f"no Deep Agents graph is configured for scope {allow!r}")
        return self.phase_agents[phase]

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        # #543. Attached whether or not a raise ever happens: `on_llm_end`
        # fires per completed model turn, well before a `GraphRecursionError`
        # (which only fires after some number of turns already ran) reaches
        # this method at all.
        usage = _usage_callback(self.max_call_usd)
        try:
            before = _changed_files(repo)
            payload = {"messages": [{"role": "user", "content": prompt}]}
            agent = self._agent_for(allow)
            config = _invoke_config(self.recursion_limit, usage)
            result = agent.invoke(payload, config=config) if config else agent.invoke(payload)
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = sorted(path for path in (after - before) if scope.permits(path))
            raw_output = _raw_messages(result)
            self._log_raw(raw_output, role=_phase_of(allow))
            return DoerResult(
                wrote=wrote,
                output=last_ai_text(result),
                usd=last_usd(result),
                raw_output=raw_output,
            )
        # Same contract every offline Backend keeps: never raise, report it.
        except Exception as exc:
            # #539. `agent.invoke()` is one synchronous call: a raise means it
            # never answered a final state, so `usd` is `None`, not the 0.0
            # that reads as "this turn was free" -- unless `usage` actually
            # saw a completed model turn before the raise (#543), in which
            # case that spend is real and reporting `None` would discard it.
            # `type(exc).__name__` names the exception (a `GraphRecursionError`
            # names itself and this port's `recursion_limit` in its own
            # message), so a caller no longer has to guess whether this was a
            # raised backend or an honest empty reply, the two the judge of
            # PR #537 found indistinguishable.
            spend = usage.total_usd if usage is not None and usage.saw_usage else None
            # #549, judge of PR #552. Named the same way the SDK port names
            # its own cost stop, so e2e_t001.CONTROLLED_STOPS reads a
            # deliberate cutoff as one, not as a crashed query.
            stop_reason = "cost budget spent" if isinstance(exc, DeepAgentsBudgetExceeded) else None
            return DoerResult(
                ok=False,
                usd=spend,
                output=f"deep_agents backend failed: {_describe_exc(exc)}",
                stop_reason=stop_reason,
            )

    def judge(self, *, repo: Path, prompt: str) -> DoerResult:
        """Run the judge-only graph. No write tools, JSON in, JSON out."""
        agent = self.judge_agent
        if agent is None:
            return super().judge(repo=repo, prompt=prompt)
        usage = _usage_callback(self.max_call_usd)
        try:
            payload = {"messages": [{"role": "user", "content": prompt}]}
            config = _invoke_config(self.recursion_limit, usage)
            result = agent.invoke(payload, config=config) if config else agent.invoke(payload)
            raw_output = _raw_messages(result)
            self._log_raw(raw_output, role="judge")
            return DoerResult(
                output=last_ai_text(result), usd=last_usd(result), raw_output=raw_output
            )
        except Exception as exc:
            spend = usage.total_usd if usage is not None and usage.saw_usage else None
            stop_reason = "cost budget spent" if isinstance(exc, DeepAgentsBudgetExceeded) else None
            return DoerResult(
                ok=False,
                usd=spend,
                output=f"deep_agents judge failed: {_describe_exc(exc)}",
                stop_reason=stop_reason,
            )

    def plan(self, *, repo: Path, prompt: str) -> DoerResult:
        """Route to the planner graph and run it with the planner's own scope.

        `_agent_for` returns the LangGraph agent itself, not a `Backend`, so
        there is no `self._for(...).run(...)` to delegate to the way the SDK
        adapter does. `run()` already resolves the graph from `allow`, so
        calling it with the planner's own scope is the whole method.
        """
        return self.run(repo=repo, prompt=prompt, allow=[steps.STEPS_FILE])
