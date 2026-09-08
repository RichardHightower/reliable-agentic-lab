"""The white paper pipeline. Python owns the order, the state, and the money.

Nine stages, run in order, checkpointed after each one. A stage asks a model for
something, a gate in `stages.py` decides whether it is usable, and `gates.decide`
decides whether to retry, escalate, or move on.

Nothing here calls a model directly. Every model call goes through a `Runner`,
which is any object with `.ask(role, prompt) -> Reply`. The offline runner reads
recorded fixtures, and the Deep Agents runner drives real subagents. The pipeline
cannot tell them apart, which is why the whole thing tests without an SDK, a key,
or a network.

Three exits and no fourth, checked before every stage:

    done        stage 9 finished and every hard gate passed
    cost        the money budget is spent
    max turns   a stage exhausted its retries

A fourth exit is always somebody adding "and also stop if it seems stuck".
Stuck work is not an exit. It burns turns or dollars until one of the three
fires, and `gates.decide` short circuits the specific case worth catching: the
same rows failing twice, which means the loop is not converging.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import brief
import diagrams
import evidence
import gates
import locate
import outline as outlines
import paper_check
import research
import sections
import source_policy
import stages
import state as pstate
from stages import GateFailed, StageResult

HERE = Path(__file__).resolve().parent
DEFAULT_WORK = HERE / "work" / "paper"
DEFAULT_BRAIN = HERE / ".." / ".." / ".." / "loop_eng_2nd_brain" / "knowledge"

DEFAULT_MAX_USD = 12.0
DEFAULT_STAGE_ATTEMPTS = 3
DEFAULT_SEARCH_CALLS = 36
OUTLINE_JUDGE_ROUNDS = int(os.environ.get("SOL3_OUTLINE_JUDGE_ROUNDS", "14"))

DONE, COST, MAX_TURNS = "done", "cost", "max turns"

# Backoff before a retried model call, in seconds. A module-level `_sleep`
# (rather than `time.sleep` inline) is what lets a test replace the wait with
# a no-op instead of actually pausing three times.
RETRY_WAITS_S: tuple[float, ...] = (5.0, 15.0, 45.0)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _transient_provider_errors() -> tuple[type[BaseException], ...]:
    """Exception classes for a dropped connection, a rate limit, or an
    overloaded or failing provider.

    Imported lazily, the same way `roles.py` imports `langchain_anthropic`:
    the fixture runner needs neither package installed, and importing here
    keeps a missing SDK from failing at module load. `anthropic.APIConnectionError`
    and `anthropic.RateLimitError` are the base classes LangChain's Anthropic
    wrapper (`AnthropicConnectionError`, `AnthropicTimeoutError`,
    `AnthropicRateLimitError`) subclasses, so catching the two bases catches
    the wrapped forms too.

    #482: `anthropic.OverloadedError` (HTTP 529, the most common transient
    Anthropic failure in practice) and `anthropic.InternalServerError` (a
    5xx) are `APIStatusError`s, not `APIConnectionError`s, so the pair above
    missed them. LangChain's `AnthropicOverloadedError` subclasses
    `anthropic.OverloadedError` and `AnthropicAPIError` subclasses
    `anthropic.InternalServerError`, so catching the two Anthropic bases
    catches LangChain's wrapped forms too, the same way the pair above
    already does. A gate failure, `BudgetSpent`, and a schema error are
    never in this tuple.
    """
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        return ()
    return (
        anthropic.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.OverloadedError,
        anthropic.InternalServerError,
    )


def _section_word_range(heading: str, claim_count: int) -> str:
    """How long a section should be. The Saturday brief is already short."""
    name = heading.strip().lower()
    if name == "abstract":
        return "120 to 180"
    if name == "conclusion":
        return "120 to 250"
    if name == "limitations":
        return "150 to 250"
    if claim_count < 3:
        return "400 to 800"
    return "700 to 1200"


def _strip_policy_leak(text: str, allowed_domains) -> str:
    """Scrub the run's admitted hosts and the harness's retrieval language out
    of feedback text before it reaches the writer. #452 #465 #412.

    A reviewer's own note, or the Python report a `policy_leak` gate failure
    writes, can name the offending host or phrase while explaining what to
    fix. The writer never sees the allowlist, only the instruction to stop
    naming a source host.
    """
    if not text:
        return text
    scrubbed = text
    for host in tuple(source_policy.SEED_ALLOWLIST) + tuple(allowed_domains or ()):
        host = str(host).strip()
        if host:
            scrubbed = re.sub(re.escape(host), "an admitted source", scrubbed, flags=re.IGNORECASE)
    return paper_check.POLICY_LEAK_PHRASE.sub("the source policy", scrubbed)


def section_body(text: str, heading: str) -> str:
    """Remove a repeated section heading from a role's body-only reply.

    The writer contract says that the assembler owns headings.  Models
    occasionally repeat one anyway, and treating that one-word line as prose
    makes the deterministic citation gate reject an otherwise grounded paper.
    This is a boundary normalization, not an attempt to edit the writer's
    argument.
    """
    pattern = rf"\A\s*(?:#{{1,6}}\s*)?{re.escape(heading)}\s*(?:\n+|\Z)"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()


class AwaitingApproval(RuntimeError):
    """`--approve` stops here. The operator edits outline.json, then `--resume`."""


class OutlineRejected(GateFailed):
    """The inner judge/editor loop exhausted. Do not send the planner back.

    `_run_stage` retries a failed plan by re-asking the planner, which is how
    a repaired outline gets thrown away. This failure is terminal for the
    stage: the editor already had its rounds.
    """

    terminal = True


class BudgetSpent(RuntimeError):
    """The money ran out mid-stage. Not a gate failure, so never a retry.

    A gate failure means the model produced something unusable and another
    attempt might fix it. A spent budget means another attempt costs money the
    run does not have. Retrying on this is how a cost cap turns into a cost
    multiplier.
    """


def check_stop(*, done: bool, spent_usd: float, max_usd: float, exhausted: bool = False) -> dict:
    """Three exits, and no fourth. Done first, then cost, then turns.

    Done beats a spent budget. A run that finished and then noticed it was over
    its cap did finish, and reporting that as a cost failure throws away the
    paper it already wrote.
    """
    if done:
        return {"stop": True, "reason": DONE}
    if spent_usd >= max_usd:
        return {"stop": True, "reason": COST}
    if exhausted:
        return {"stop": True, "reason": MAX_TURNS}
    return {"stop": False, "reason": None}


@dataclass
class Reply:
    """One answer from a role. `usd` is what it cost.

    `cost_reported` separates "the call cost nothing" from "nothing told us".
    The turn log writes null for the second, because a zero there reads as a
    free call and hides a broken cost path.
    """

    text: str = ""
    data: dict | None = None
    usd: float = 0.0
    cost_reported: bool = False
    input_tokens: int = 0
    output_tokens: int = 0

    def json(self) -> dict:
        return self.data if self.data is not None else stages.parse_json(self.text)


HEARTBEAT_SECONDS = 15


@contextlib.contextmanager
def _heartbeat(role: str, stage: str, started: float, quiet: bool):
    """Say the call is still running, about every `HEARTBEAT_SECONDS`.

    `runner.ask` is one blocking call with no events to hang a progress line
    on, so the beat runs on its own daemon thread. A live outline call took ten
    minutes and printed nothing for all of it.
    """
    if quiet:
        yield
        return
    done = threading.Event()

    def beat() -> None:
        while not done.wait(HEARTBEAT_SECONDS):
            print(
                f"[sol3] t+{time.monotonic() - started:.0f}s stage={stage or '?'} role={role}",
                file=sys.stderr,
                flush=True,
            )

    worker = threading.Thread(target=beat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        done.set()


def _reply_from(adapter, text: str, result) -> Reply:
    """One reply, with its cost and its token counts."""
    tokens_in, tokens_out = adapter.usage_tokens(result)
    return Reply(
        text=text,
        usd=adapter.last_usd(result),
        cost_reported=adapter.cost_is_reported(result),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
    )


class Runner:
    """Anything that can ask a role for something. Three implementations exist."""

    name = "runner"

    def ask(self, role: str, prompt: str) -> Reply:
        raise NotImplementedError


class FixtureRunner(Runner):
    """Recorded replies, keyed by role. Runs offline, in a room with no network.

    A role's entry is either a dict or a list.

    A dict is keyed by a phrase that appears in the prompt: a section heading, a
    question, a diagram name. Keying by content rather than by position is what
    makes a partial resume work. A positional queue restarts at zero when the
    run resumes at stage six, and hands the writer the outline reply.

    A list is positional, consumed in order, and the last entry repeats. That
    repeat is deliberate: a retry gets the same answer, which is exactly the
    stable failure `gates.decide` exists to catch, so the offline run can
    demonstrate the escalate path without anybody faking it.
    """

    name = "fixture"

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.replies: dict = json.loads(self.path.read_text(encoding="utf-8"))
        self.used: dict[str, int] = {}

    def ask(self, role: str, prompt: str) -> Reply:
        entries = self.replies.get(role)
        if not entries:
            raise GateFailed(f"no recorded reply for the {role} role.", ("no_fixture",))
        if isinstance(entries, dict):
            entry = self._match(role, entries, prompt)
        else:
            turn = self.used.get(role, 0)
            entry = entries[min(turn, len(entries) - 1)]
            self.used[role] = turn + 1
        if isinstance(entry, str):
            return Reply(text=entry)
        return Reply(
            text=entry.get("text", ""),
            data=entry.get("data"),
            usd=float(entry.get("usd", 0.0)),
        )

    @staticmethod
    def _match(role: str, entries: dict, prompt: str):
        """The longest key the prompt contains. Longest wins, so a specific key
        beats a generic one that happens to be a prefix of it."""
        best = None
        for key, entry in entries.items():
            if key.lower() in prompt.lower() and (best is None or len(key) > len(best[0])):
                best = (key, entry)
        if best is None:
            raise GateFailed(
                f"no recorded {role} reply matches this prompt. Recorded keys: {sorted(entries)}.",
                ("no_fixture",),
            )
        return best[1]


class DeepAgentsRunner(Runner):
    """One Deep Agents graph, addressed one subagent at a time.

    The orchestrator is asked to delegate to a named subagent rather than to do
    the work. Deep Agents routes by name, and naming the role in the prompt is
    what keeps the orchestrator from quietly answering itself.
    """

    name = "deep_agents"

    def __init__(self, agent, *, debug: bool = False, debug_stream=None):
        self.agent = agent
        self.debug = debug
        self.debug_stream = debug_stream or sys.stderr

    def ask(self, role: str, prompt: str) -> Reply:
        import adapter  # noqa: PLC0415

        instruction = (
            f"Delegate this to the {role.replace('_', '-')} subagent. "
            f"Return its answer and nothing else.\n\n{prompt}"
        )
        payload = {"messages": [{"role": "user", "content": instruction}]}
        if isinstance(self.agent, dict):
            role_agent = self.agent.get(role)
            if role_agent is None:
                raise KeyError(f"no compiled Deep Agent for role {role!r}")
            # Direct role graphs receive the original stage prompt, not the
            # parent-only delegation wrapper. That makes the evidence contract
            # visible to the writer and verifier whose output Python gates.
            direct_payload = {"messages": [{"role": "user", "content": prompt}]}
            result = self._run_direct(role, role_agent, direct_payload) if self.debug else role_agent.invoke(direct_payload)
            return _reply_from(adapter, adapter.last_ai_text(result), result)
        parent, delegated = self._run_subgraphs(role, payload, debug=self.debug)
        text = adapter.last_ai_text(delegated) if delegated is not None else adapter.last_agent_ai_text(parent, role)
        return _reply_from(adapter, text, parent)

    def _run_direct(self, role: str, agent, payload: dict):
        """Debug a compiled role graph without the parent-task event flood."""
        result = None
        for chunk in agent.stream(
            payload,
            stream_mode=["debug", "values"],
            subgraphs=True,
            version="v2",
        ):
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") == "debug":
                namespace = "/".join(str(part) for part in chunk.get("ns", ()) or ()) or role
                print(
                    f"[deepagents debug] role={role} namespace={namespace}",
                    file=self.debug_stream,
                )
                print(chunk.get("data"), file=self.debug_stream, flush=True)
            elif chunk.get("type") == "values" and not chunk.get("ns"):
                result = chunk.get("data")
        if result is None:
            raise RuntimeError(f"Deep Agents role stream ended without final values for {role!r}.")
        return result

    def _run_subgraphs(self, role: str, payload: dict, *, debug: bool):
        """Capture the parent state and the named subagent's final state.

        `.invoke()` returns the parent's messages. After a `task` call, its
        last payload is often a tool receipt, not the delegated writer's prose.
        LangGraph v2 values events keep the two states separate. The parent
        stays the cost source; the matching child namespace supplies the role
        answer. Debug mode only adds the event flood, it does not change this
        extraction rule.

        This is intentionally local to the run. Do not call LangChain's
        process-wide debug switch: a paper can make many model and tool calls,
        and an all-process trace obscures the one delegated role being probed.
        """
        import adapter  # noqa: PLC0415

        parent = None
        delegated = None
        modes = ["values"]
        if debug:
            modes.insert(0, "debug")
        expected = role.replace("_", "-")
        for chunk in self.agent.stream(
            payload,
            stream_mode=modes,
            subgraphs=True,
            version="v2",
        ):
            if not isinstance(chunk, dict):
                continue
            if debug and chunk.get("type") == "debug":
                namespace = "/".join(str(part) for part in chunk.get("ns", ()) or ()) or "parent"
                print(
                    f"[deepagents debug] role={role} namespace={namespace}",
                    file=self.debug_stream,
                )
                print(chunk.get("data"), file=self.debug_stream, flush=True)
            elif chunk.get("type") == "values":
                namespace = "/".join(str(part) for part in chunk.get("ns", ()) or ())
                if not namespace:
                    parent = chunk.get("data")
                elif expected in namespace or adapter.has_agent_ai_message(chunk.get("data"), role):
                    delegated = chunk.get("data")
        if parent is None:
            raise RuntimeError(
                "Deep Agents stream ended without a final parent values event. "
                "Inspect the streamed debug events or retry the stage."
            )
        return parent, delegated


def _write_briefing(work_dir: Path, payload: dict) -> None:
    dest = Path(work_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "scout-briefing.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Scout briefing", ""]
    if payload.get("skipped"):
        lines += [f"Skipped: {payload.get('reason') or 'pack is thick'}", ""]
    else:
        headings = payload.get("headings") or []
        titles = payload.get("titles") or []
        admitted = payload.get("admitted") or []
        if headings:
            lines += ["## Candidate headings", ""]
            lines += [f"- {item}" for item in headings]
            lines.append("")
        if admitted:
            lines += ["## Admitted hosts", ""]
            lines += [f"- {item}" for item in admitted]
            lines.append("")
        if titles:
            lines += ["## Flagship titles", ""]
            lines += [f"- {item}" for item in titles]
            lines.append("")
        if payload.get("seeded_by_field"):
            lines += [f"Seeded by field: {payload.get('field')}.", ""]
        lines += [
            "This is a map, not evidence. The outline judge must not treat it as research.",
            "",
        ]
    (dest / "scout-briefing.md").write_text("\n".join(lines), encoding="utf-8")


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


# #475. A scout title counts as retrieved only on a normalized exact match,
# or a token-set overlap of at least 0.8 against an admitted source's own
# title. One shared word, even a distinctive one, is not enough: judge
# revision on #520, follow-up 1, found a never-retrieved flagship work
# reading as retrieved on one word shared with an unrelated source, such as
# "trial" or "study".
TITLE_OVERLAP_MIN = 0.8


def _scout_title_retrieved(title: str, sources) -> bool:
    normalized_wanted = _normalize_title(title)
    wanted = set(re.findall(r"[a-z0-9]{4,}", normalized_wanted))
    if not normalized_wanted or not wanted:
        return False
    for source in sources:
        normalized_found = _normalize_title(getattr(source, "title", "") or "")
        if normalized_wanted == normalized_found:
            return True
        found = set(re.findall(r"[a-z0-9]{4,}", normalized_found))
        if found and len(wanted & found) / min(len(wanted), len(found)) >= TITLE_OVERLAP_MIN:
            return True
    return False


def _briefing_markdown(work_dir: Path) -> str:
    """The map, if the scout actually ran. A skipped briefing is not a map."""
    path = Path(work_dir) / "corpus" / "scout-briefing.json"
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict) or payload.get("skipped"):
        return ""
    md = Path(work_dir) / "corpus" / "scout-briefing.md"
    if not md.exists():
        return ""
    return md.read_text(encoding="utf-8")


@dataclass
class Paper:
    """One run. Owns the budget, the state file, and the order of the stages."""

    topic: str
    runner: Runner
    backend: research.Backend
    work_dir: Path
    docs_backend: research.Backend | None = None
    search_budget: research.Budget | None = None
    max_usd: float = DEFAULT_MAX_USD
    max_verify: int = stages.MAX_VERIFY_CLAIMS
    # #473. How many secondary-tier numeric claims get a follow turn asking
    # for the primary study, per run: the ticket asked for a cap per
    # section, and eight sections at six each would roughly double a run.
    # `self.follow_used`, synced with `state.follow_used`, is the running
    # count `_follow_primaries` checks and increments on every call,
    # `stage_search` retries included.
    max_follow: int = 6
    # #474. How many generalizing claims get a counter-evidence turn, per
    # run, for the same reason `max_follow` is per run: Open decision 4
    # asked for a cap per section, and eight sections at six each would
    # roughly double a run. `self.counter_used`, synced with
    # `state.counter_used`, is the running count `_counter_evidence` checks
    # and increments on every call, `stage_search` retries included.
    max_counter: int = 6
    attempts: int = DEFAULT_STAGE_ATTEMPTS
    theme: str = "spillwave-light"
    publish: bool = False
    quiet: bool = False
    brains: list = field(default_factory=list)
    ingest_brain: Path | None = None
    require_approval: bool = False
    resume: bool = False
    outline_judge_rounds: int = OUTLINE_JUDGE_ROUNDS
    # The seminar's own paper taught this repository's exit order as its
    # subject. Any other topic plans without it. On restores today's
    # behavior: the doctrine question is bound, the repository answers it,
    # and the assembled body is graded on naming it.
    loop_doctrine: bool = False
    # #475. Every important question is expected to carry its own
    # `evidence_requirements` block. Off by default, the same as
    # `loop_doctrine`, so the many tests that build a `Paper` directly and
    # exercise `stage_plan`/`stage_search` with an older-shaped plan are
    # unaffected; `loop.py`'s real run turns it on.
    require_evidence_requirements: bool = False

    state: pstate.PaperState = field(init=False)
    ledger: evidence.Ledger = field(init=False)
    plan: dict = field(default_factory=dict, init=False)
    outline: dict = field(default_factory=dict, init=False)
    written: dict = field(default_factory=dict, init=False)
    figures: list = field(default_factory=list, init=False)
    charts: list = field(default_factory=list, init=False)
    allowed_domains: tuple = field(default_factory=tuple, init=False)
    budget: research.Budget = field(init=False)
    # #473. Loaded from `state.follow_used` in `__post_init__`, so a
    # `search_gate` retry re-entering `stage_search` sees what earlier
    # attempts already spent, not a fresh `max_follow`.
    follow_used: int = field(default=0, init=False)
    # #474. Loaded from `state.counter_used` in `__post_init__`, the same way
    # `follow_used` is.
    counter_used: int = field(default=0, init=False)
    # Diagram names the complexity gate rejected, so a retry redraws only those.
    _redraw: set = field(default_factory=set, init=False)
    # The most expensive call seen per role. The budget check reads it as the
    # headroom the next call of that kind is likely to need.
    _worst: dict = field(default_factory=dict, init=False)
    # #475. Loaded from `state.scout_retried` in `__post_init__`, so a
    # resumed `scout` stage does not spend a second retry turn.
    scout_retried: bool = field(default=False, init=False)
    # #475, judge revision on #520. Loaded from `state.evidence_shortfall_unmet`
    # in `__post_init__`: question id -> the measured shortfall text, for a
    # question whose one turn is spent and the block is still short. Being
    # in this dict is what tells `_research_shortfalls` not to ask again and
    # `search_gate` to accept the gap rather than fail the run on it.
    evidence_shortfall_unmet: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.work_dir = Path(self.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.state = pstate.PaperState.load_or_create(
            self.work_dir, slug=self.work_dir.name, topic=self.topic
        )
        self.state.backend = self.backend.name
        self.ledger = evidence.Ledger(self.work_dir / "evidence").load()
        self.budget = self.search_budget or research.Budget(
            max_usd=self.max_usd, max_calls=DEFAULT_SEARCH_CALLS
        )
        self.budget.spent_usd = self.state.search_cost_usd
        self.budget.calls = self.state.search_calls
        self.budget.on_charge = self._reserve_search
        self.follow_used = self.state.follow_used
        self.counter_used = self.state.counter_used
        self.scout_retried = self.state.scout_retried
        self.evidence_shortfall_unmet = dict(self.state.evidence_shortfall_unmet)
        self._load_allowlist()

    def _load_allowlist(self) -> None:
        """Resume must use the run's admitted hosts, not the leftover seed.

        `stage_sources` writes `corpus/source_allowlist.json` and sets
        `allowed_domains`. A later `--resume` that skips that stage would
        otherwise search the vendor seed and drop every host the librarian
        had admitted.
        """
        path = self.work_dir / "corpus" / "source_allowlist.json"
        if path.exists():
            decided = json.loads(path.read_text(encoding="utf-8"))
            admitted = decided.get("admitted") if isinstance(decided, dict) else None
            self.allowed_domains = source_policy.run_allowlist(admitted or [])
        else:
            self.allowed_domains = source_policy.SEED_ALLOWLIST
        setter = getattr(self.backend, "set_allowlist", None)
        if callable(setter):
            setter(self.allowed_domains)
        else:
            self.backend.allowlist = self.allowed_domains

    # -- plumbing ----------------------------------------------------------

    def say(self, line: str) -> None:
        if not self.quiet:
            print(line, flush=True)

    def _reserve_search(self, usd: float) -> None:
        """Checkpoint a provider call before the search tool makes it."""
        self.state.reserve_search(usd)
        self.state.save()

    def _json_reply(self, role: str, reply: Reply) -> dict:
        """Parse a structured reply and retain its raw form if the gate rejects it."""
        try:
            return reply.json()
        except GateFailed:
            diagnostics = self.work_dir / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / f"last-{role}-reply.txt").write_text(reply.text, encoding="utf-8")
            raise

    @property
    def diagram_src(self) -> Path:
        return self.work_dir / "diagrams"

    @property
    def figure_dir(self) -> Path:
        return self.work_dir / "figures"

    @property
    def paper_path(self) -> Path:
        return self.work_dir / "whitepaper.md"

    def _ask(self, role: str, prompt: str) -> Reply:
        """One model call, checked against the cap before it is made.

        Checking only between stages is not a cost cap. A stage that loops over
        six sections makes six calls with nothing between them, so the run
        discovers it is over budget once the money is already gone. Measured on
        the recorded fixtures with a realistic price per role, a $3.00 cap spent
        $4.45 that way.

        The check needs headroom, not just a "have we passed it" test, or the
        last call still starts with one cent left and finishes two dollars over.
        `_worst` is the most expensive call this run has seen for this role, so
        after the first writer turn the loop knows what a writer turn costs.
        Before that it has no basis for an estimate and says so by allowing the
        call, which is why the cap is documented as enforced to within one call
        per role rather than exactly.
        """
        left = self.max_usd - self.state.total_cost_usd
        headroom = self._worst.get(role, 0.0)
        if left <= 0 or left < headroom:
            raise BudgetSpent(
                f"the {role} call needs about ${headroom:.2f} and ${max(0.0, left):.2f} is left "
                f"of the ${self.max_usd:.2f} cap"
            )
        started = time.monotonic()
        transient_errors = _transient_provider_errors()
        retries = 0
        with _heartbeat(role, self.state.current_stage, started, self.quiet):
            while True:
                try:
                    reply = self.runner.ask(role, prompt)
                    break
                except transient_errors as exc:
                    if retries >= len(RETRY_WAITS_S):
                        raise
                    wait = RETRY_WAITS_S[retries]
                    retries += 1
                    self.say(
                        f"  {role:<10} transient error, retry {retries}/{len(RETRY_WAITS_S)} "
                        f"after {wait:.0f}s: {exc}"
                    )
                    _sleep(wait)
                    # #482: the caller may have opened a request window
                    # around this whole `_ask` call (`begin_request`, one
                    # tool call and its provider calls). The first attempt
                    # can spend that window before it drops, and a retry
                    # that reuses the spent window hits `BudgetExceeded` on
                    # its own search instead of trying again. Re-arm the
                    # window with its own limits so the retried attempt
                    # gets its budget back; a no-op when no window is open.
                    self.budget.reset_request()
        elapsed = time.monotonic() - started

        self.state.spend(reply.usd)
        self._worst[role] = max(self._worst.get(role, 0.0), reply.usd)
        self._record_turn(role, reply, elapsed, len(prompt), retries=retries)
        return reply

    def _record_turn(
        self, role: str, reply: Reply, elapsed: float, prompt_chars: int, *, retries: int = 0
    ) -> None:
        """Checkpoint one call: the state file and the append-only turn log.

        Saving on the stage boundary was not enough. A stage that makes six
        calls left the checkpoint stale for the whole stage, so a run killed in
        the middle reported the role before the one it died in.
        """
        row = {
            "turn": self.state.total_calls,
            "at": pstate.now(),
            "stage": self.state.current_stage,
            "role": role,
            "elapsed_s": round(elapsed, 3),
            "prompt_chars": prompt_chars,
            # Null, never zero. A zero reads as a free call.
            "usd": round(reply.usd, 6) if reply.cost_reported else None,
            "total_usd": round(self.state.total_cost_usd, 6),
            "input_tokens": reply.input_tokens,
            "output_tokens": reply.output_tokens,
            "retries": retries,
        }
        self.state.current_role = role
        self.state.last_turn = row
        path = self.work_dir / ".harness" / "turns.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            self.state.save()
        except OSError:
            pass  # telemetry never fails a run

    # -- the loop ----------------------------------------------------------

    def run(self) -> int:
        """Run every incomplete stage in order. Returns a shell exit code."""
        order = [name for name in stages.STAGE_ORDER if name != "publish" or self.publish]
        self.say(f"paper: {self.topic}")
        self.say(
            f"backend: {self.backend.name}  budget: ${self.max_usd:.2f}  work: {self.work_dir}"
        )
        if self.state.stages:
            self.say(f"resuming: {self.state.line()}")

        for name in order:
            if self.state.is_complete(name):
                self.say(f"  {name:<10} already done")
                continue

            stop = check_stop(done=False, spent_usd=self.state.total_cost_usd, max_usd=self.max_usd)
            if stop["stop"]:
                return self._escalate(name, f"the {stop['reason']} budget is spent")

            try:
                decision = self._run_stage(name)
            except AwaitingApproval as exc:
                self.say(f"  outline    awaiting approval ({exc})")
                self.state.save()
                return 3
            if decision is not None:
                return decision

        self.state.save()
        stop = check_stop(done=True, spent_usd=self.state.total_cost_usd, max_usd=self.max_usd)
        if self.ingest_brain is not None:
            import corpus as corpus_mod  # noqa: PLC0415

            bundle = self.work_dir / "knowledge"
            result = corpus_mod.ingest_brain(bundle, self.ingest_brain)
            self.say(f"  ingest     {result}")
        self.say(f"\nstopped: {stop['reason']}. {self.state.line()}")
        self.say(f"paper: {self.paper_path}")
        return 0

    def _run_stage(self, name: str) -> int | None:
        """One stage, with its retry loop. None means it passed, an int stops."""
        handler = getattr(self, f"stage_{name}")
        previous: tuple[str, ...] | None = None
        previous_score: float | None = None
        extra = ""

        # A `FAILED` stage re-entered here, on `--resume` or a same-process
        # retry alike, used to start counting at 1 with no memory of what the
        # state file already knows was spent. The persisted count is the
        # truth: a resume is another attempt against the same budget, not a
        # clean slate (#411).
        entry = self.state.stages.get(name)
        prior_attempts = entry.attempts if entry and entry.status == pstate.FAILED else 0
        if prior_attempts >= self.attempts:
            self.say(
                f"  {name:<10} already spent {prior_attempts} of {self.attempts} "
                "attempts before this resume"
            )
            reason = f"the iteration budget is spent after {self.attempts} attempts"
            return self._escalate(name, reason, (entry.error or "") if entry else "")
        if prior_attempts:
            self.say(f"  resuming {name} at attempt {prior_attempts + 1} of {self.attempts}")

        for attempt in range(prior_attempts + 1, self.attempts + 1):
            self.state.mark_in_progress(name)
            self.state.save()
            try:
                result = handler(extra)
            except BudgetSpent as spent:
                self.state.mark_failed(name, str(spent))
                self.state.save()
                return self._escalate(name, COST, str(spent))
            except GateFailed as failure:
                if getattr(failure, "terminal", False):
                    self.state.mark_failed(name, str(failure))
                    self.state.save()
                    return self._escalate(name, MAX_TURNS, str(failure))
                signature = failure.signature
                score = failure.score
                # A rubric row that measurably closed its gap since the last
                # attempt is work in progress, not a stall: the failed-row
                # count fell, or the reviewer's own score rose by a tenth.
                # Copied from the SDK port's `decide(progressed=...)` rule
                # (#361, #362).
                progressed = previous is not None and (
                    len(signature) < len(previous)
                    or (
                        score is not None
                        and previous_score is not None
                        and score - previous_score >= 0.1 - 1e-9
                    )
                )
                decision = gates.decide(
                    passed=False,
                    iteration=attempt,
                    budget=self.attempts,
                    signature=signature,
                    previous_signature=previous,
                    usd_left=max(0.0, self.max_usd - self.state.total_cost_usd),
                    progressed=progressed,
                )
                self.say(f"  {name:<10} attempt {attempt} failed: {', '.join(signature)}")
                if decision.stop:
                    self.state.mark_failed(name, str(failure))
                    self.state.save()
                    return self._escalate(name, decision.reason, str(failure))
                previous = signature
                previous_score = score
                extra = gates.retry_instruction(decision, list(signature)) + "\n" + str(failure)
                # A failure inside the recovery path is a failure of this
                # attempt, never a crash. These two calls run from inside the
                # handler that is already handling a GateFailed, so an
                # unguarded raise here escapes both and kills the run with a
                # traceback: no attempt accounting, no escalation, no reason
                # for the operator to read. One model turn returning prose
                # instead of JSON used to end a run that had cleared every
                # stage up to review.
                try:
                    if name == "review":
                        revised = self.stage_revise(extra)
                        self.say(f"  revise     {revised.summary}")
                    elif name == "assemble" and "cited" in signature:
                        # This gate names a mechanical, local defect.  Send only
                        # the offending sections back to the maker; a full
                        # rewrite would risk the reviewer-approved prose just to
                        # add a traceable source marker.
                        targets = self._uncited_section_headings()
                        revised = self.stage_revise(extra, targets=targets or None)
                        self.say(f"  revise     {revised.summary}")
                except GateFailed as revise_failure:
                    self.say(
                        f"  revise     failed: "
                        f"{', '.join(revise_failure.signature) or 'unknown'}"
                    )
                    previous = revise_failure.signature
                    extra = f"{extra}\nThe revision also failed: {revise_failure}"
                    self.state.save()
                continue

            self.state.mark_complete(name, cost_usd=result.usd, **result.artifacts)
            self.state.save()
            self.say(f"  {name:<10} {result.summary}")
            return None
        return None

    def _escalate(self, name: str, reason: str, detail: str = "") -> int:
        self.state.save()
        self.say(f"\nescalate at {name}: {reason}")
        if detail:
            self.say(detail)
        self.say(f"{self.state.line()}")
        self.say(f"state kept at {self.work_dir / pstate.STATE_FILE}. Rerun with --resume.")
        return 2

    # -- 1. plan -----------------------------------------------------------

    def stage_corpus(self, extra: str = "") -> StageResult:
        """Read configured brains before any model call. Missing brain is a note."""
        import corpus as corpus_mod  # noqa: PLC0415

        dest = self.work_dir / "corpus"
        packed = corpus_mod.pack(self.topic, list(self.brains), dest, limit=40)
        summary = (
            f"{len(packed.get('hits') or [])} hits, "
            f"{packed['relevant']} relevant, "
            f"thin={packed.get('corpus_thin')}"
        )
        return StageResult(
            "corpus",
            artifacts={"corpus/brain-pack.json": str(dest / "brain-pack.json")},
            summary=summary,
        )

    def stage_scout(self, extra: str = "") -> StageResult:
        """A cheap map of the field when the cabinet missed. Not a gate.

        Fat pack: skip. Thin pack: one researcher turn. Failure is a note.
        Copied from the Agent SDK port, not imported.
        """
        pack_path = self.work_dir / "corpus" / "brain-pack.json"
        pack = {}
        if pack_path.exists():
            try:
                packed = json.loads(pack_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                packed = {}
            pack = packed if isinstance(packed, dict) else {}
        if not pack.get("corpus_thin", True):
            payload = {
                "skipped": True,
                "reason": "pack is thick",
                "headings": [],
                "titles": [],
                "admitted": [],
                "dropped": [],
                "proposed": [],
            }
            _write_briefing(self.work_dir, payload)
            return StageResult(
                "scout",
                artifacts={"skipped": True, "hits": len(pack.get("hits") or [])},
                summary="skipped, pack is thick",
            )

        proposal: dict = {"headings": [], "domains": [], "titles": []}
        usd = 0.0
        try:
            reply = self._ask(
                "researcher",
                "Map the field for a white paper. This is a briefing, not research. "
                "Do not return claims, quotes, or citation numbers.\n\n"
                f"Topic: {self.topic}\n\n"
                "Return JSON with headings (5-8 standard section titles for this "
                "kind of paper), domains (canonical hosts with org_type from "
                f"{', '.join(source_policy.ORG_TYPES)}; at most "
                f"{source_policy.MAX_PERPLEXITY_DOMAINS}), titles (a few "
                "flagship works, names only), and field (software, physics, "
                "biomedical, economics, law, or general, naming this topic's "
                "own research field). Name the hosts that field actually "
                "publishes in. Prefer .gov, .edu, .int, peer-reviewed "
                "publishers, and official documentation. Not blogs, not "
                "encyclopedias, not cable news."
                + extra,
            )
            usd = reply.usd
            parsed = self._json_reply("researcher", reply)
            if isinstance(parsed, dict):
                proposal = parsed
        except BudgetSpent:
            raise
        except Exception as exc:
            self.say(f"  scout failed: {exc}; outlining from the topic")

        # #475. A scout that named headings -- a literature exists -- but no
        # flagship titles is retried once, the missing field named in the
        # prompt. `self.scout_retried`, persisted to `state.scout_retried`,
        # means a resumed scout stage does not spend a second retry turn.
        if proposal.get("headings") and not proposal.get("titles") and not self.scout_retried:
            self.scout_retried = True
            self.state.scout_retried = True
            self.state.save()
            try:
                retry = self._ask(
                    "researcher",
                    "Map the field for a white paper. This is a briefing, not "
                    "research. Do not return claims, quotes, or citation "
                    "numbers.\n\nTopic: " + self.topic + "\n\n"
                    "The first pass named headings but no titles. Name titles: "
                    "list a few flagship works for this field, by name.\n\n"
                    "Return JSON with headings, domains (canonical hosts with "
                    f"org_type from {', '.join(source_policy.ORG_TYPES)}; at "
                    f"most {source_policy.MAX_PERPLEXITY_DOMAINS}), titles (a "
                    "few flagship works, names only), and field."
                    + extra,
                )
                usd += retry.usd
                retried = self._json_reply("researcher", retry)
                if isinstance(retried, dict) and retried.get("titles"):
                    proposal = retried
            except BudgetSpent:
                raise
            except Exception as exc:
                self.say(f"  scout retry failed: {exc}")

        proposed = []
        for item in proposal.get("domains") or []:
            if isinstance(item, str):
                proposed.append({"host": item, "org_type": "preprint"})
            elif isinstance(item, dict):
                proposed.append(item)
        field = str(proposal.get("field") or "").strip().lower()
        # A named field's seed is added on top of whatever the model itself
        # proposed, never in place of it: an economics topic that named one
        # real host still gets doi.org beside it, not instead of it. A blank
        # field seeds nothing, so a scout that cannot yet name its field
        # forces nothing onto the run. #469
        existing_hosts = {str(item.get("host") or "").strip().lower() for item in proposed}
        seed_hosts = [
            seed
            for seed in source_policy.seed_for_field(field)
            if str(seed.get("host") or "").strip().lower() not in existing_hosts
        ]
        seeded_by_field = bool(seed_hosts)
        proposed = proposed + seed_hosts
        decided = source_policy.admit(proposed)
        payload = {
            "skipped": False,
            "field": field,
            "seeded_by_field": seeded_by_field,
            "headings": [str(h) for h in (proposal.get("headings") or []) if str(h).strip()][:8],
            "titles": [str(t) for t in (proposal.get("titles") or []) if str(t).strip()][:8],
            "proposed": decided["proposed"],
            "admitted": decided["admitted"],
            "dropped": decided["dropped"],
        }
        _write_briefing(self.work_dir, payload)
        return StageResult(
            "scout",
            usd=usd,
            artifacts={
                "skipped": False,
                "headings": len(payload["headings"]),
                "admitted": len(payload["admitted"]),
                "dropped": len(payload["dropped"]),
            },
            summary=f"{len(payload['headings'])} headings, {len(payload['admitted'])} hosts",
        )

    def stage_plan(self, extra: str = "") -> StageResult:
        path = self.work_dir / "plan.json"
        usd = 0.0
        if path.exists() and not extra:
            self.plan = json.loads(path.read_text(encoding="utf-8"))
        else:
            briefing = _briefing_markdown(self.work_dir)
            map_note = (
                "\n\nThe scout briefing below is a map of the field, not evidence. "
                "Do not cite it. Research has not run.\n"
                + briefing
                if briefing
                else ""
            )
            # The skill only binds a first question the delegation message
            # names. Off, the planner writes any first question the topic
            # earns; nothing here mentions exits, cost, or max turns.
            doctrine_note = (
                f"\n\nRequired first question, exactly: {stages.EXIT_DOCTRINE_QUESTION}"
                if self.loop_doctrine
                else ""
            )
            reply = self._ask(
                "planner",
                f"Topic: {self.topic}\n\nWrite plan.json for a technical white paper "
                f"on this topic.\n{extra}{map_note}{doctrine_note}",
            )
            usd = reply.usd
            # The Deep Agents planner owns exactly one scoped write:
            # ``plan.json``. Its useful result can therefore be the file while
            # its final message is only a tool receipt such as "wrote
            # plan.json". Prefer that artifact when the role produced it.
            # Fixture and answer-only runners still return the plan directly.
            self.plan = (
                stages.parse_json(path.read_text(encoding="utf-8"))
                if path.exists()
                else reply.json()
            )
        self.plan = stages.normalize_plan(self.plan)
        stages.plan_gate(
            self.plan,
            loop_doctrine=self.loop_doctrine,
            require_evidence_requirements=self.require_evidence_requirements,
        )
        path.write_text(json.dumps(self.plan, indent=2), encoding="utf-8")
        usd += self._approve_outline()
        self.state.record("plan", path)
        return StageResult(
            "plan",
            usd=usd,
            artifacts={"questions": len(self.plan["questions"])},
            summary=f"{len(self.plan['questions'])} questions, "
            f"{len(self.plan['diagrams'])} figures planned",
        )

    def _edit_outline(self, drafted: dict, verdict: dict) -> tuple[dict | None, float]:
        """Repair a judged outline, rather than re-planning it.

        The planner plans. Sending a failed outline back to it produces a
        different plan with different defects, which is how a loop hovers
        instead of converging. The editor changes only what the judge named.

        Returns `(None, cost)` when there is nothing usable, so the caller
        keeps the outline it already has.
        """
        objections = "\n".join(
            f"- {item}" for item in (verdict.get("blocking_issues") or verdict.get("notes") or [])
        ) or (verdict.get("summary") or "the judge rejected the outline")
        changes = "\n".join(f"- {item}" for item in (verdict.get("actionable_changes") or []))
        if changes:
            objections += "\n\nApply these actionable changes:\n" + changes
        try:
            reply = self._ask(
                "outline_editor",
                "Edit this outline so it clears the objections below. Make the "
                "fewest edits that do it. Every field the judge did not name "
                "comes back exactly as you received it, and a section the judge "
                "did not fault is returned unchanged. Do not rewrite, reorder, "
                "or renumber anything. Python revalidates before the judge sees "
                "this, and a rejected edit wastes the round.\n\n"
                f"The outline:\n{json.dumps(drafted, indent=2)}\n\n"
                f"The objections:\n{objections}",
            )
        except BudgetSpent:
            raise
        except Exception as exc:  # a failed repair must not lose the outline
            self.say(f"  outline editor failed: {exc}")
            return None, 0.0

        usd = reply.usd
        try:
            edited = self._json_reply("outline_editor", reply)
        except GateFailed as exc:
            if stages.reply_was_truncated(reply.text):
                self.say(f"  outline editor reply was cut off at {len(reply.text)} characters")
            else:
                self.say(f"  outline editor returned no outline: {exc}")
            return None, usd
        if not isinstance(edited, dict):
            return None, usd
        errors = outlines.validate(
            edited, word_target_total=edited.get("word_target_total") or 2000, require_next_step=True
        )
        if errors:
            self.say(f"  outline editor edit rejected: {errors[0]}")
            return None, usd
        return edited, usd

    def _approve_outline(self) -> float:
        """Validate, judge, edit in place, and stamp. `--approve` stops before research.

        The planner plans once. A failed judge used to raise GateFailed, and
        `_run_stage` retried the whole plan stage, which asked the planner
        again. That is how a repaired outline got thrown away. The sibling
        port judges then edits, at most N rounds, without re-planning.
        """
        dest = self.work_dir / "outline.json"
        judged_path = self.work_dir / "outline-judged.json"
        stamped = self.work_dir / "outline.approved.json"
        usd = 0.0
        if dest.exists():
            drafted = json.loads(dest.read_text(encoding="utf-8"))
        else:
            drafted = outlines.outline_from_plan(self.plan)
        errors = outlines.validate(
            drafted, word_target_total=drafted.get("word_target_total") or 2000, require_next_step=True
        )
        if errors:
            raise GateFailed(outlines.retry_note(errors), ("outline",))
        dest.write_text(json.dumps(drafted, indent=2) + "\n", encoding="utf-8")
        (self.work_dir / "outline.md").write_text(outlines.to_markdown(drafted), encoding="utf-8")

        if not judged_path.exists() or self.resume:
            previous: tuple[str, ...] | None = None
            rounds = max(1, int(self.outline_judge_rounds))
            # A pack with zero hits cannot support or contradict any claim
            # this outline makes, so `corpus_fit` against it is re-filed as
            # `flow` below. Checked once: the pack does not change between
            # judge rounds. A missing brain-pack.json also reads as empty,
            # which is harmless now that the finding is relabeled rather
            # than dropped.
            pack_empty = not self._pack_hits()
            for round_no in range(1, rounds + 1):
                reply = self._ask(
                    "outline_judge",
                    "Grade this outline against logical flow, completeness, titles, "
                    "and corpus_fit. Do not re-litigate Python's validator."
                    + (
                        " The corpus pack is empty for this topic, so corpus_fit "
                        "passes by definition; do not fail it for that."
                        if pack_empty
                        else ""
                    )
                    + "\n"
                    + outlines.for_judge(drafted),
                )
                usd += reply.usd
                verdict = self._json_reply("outline_judge", reply)
                if pack_empty:
                    verdict, refiled = outlines.refile_corpus_fit(verdict)
                    if refiled:
                        self.say("    outline judge: corpus_fit refiled as flow, the pack is empty")
                (self.work_dir / "outline-verdict.json").write_text(
                    json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
                )
                if verdict.get("passed"):
                    judged_path.write_text(json.dumps(drafted, indent=2) + "\n", encoding="utf-8")
                    break
                signature = outlines.judge_signature(verdict)
                decision = gates.decide(
                    passed=False,
                    iteration=round_no,
                    budget=rounds,
                    signature=signature,
                    previous_signature=previous,
                    usd_left=max(0.0, self.max_usd - self.state.total_cost_usd),
                )
                self.say(f"    outline judge round {round_no}: {decision.reason}")
                if decision.stop:
                    raise OutlineRejected(
                        "the outline judge rejected the outline: "
                        + (verdict.get("summary") or "failed"),
                        signature or ("outline",),
                    )
                previous = signature
                edited, edit_usd = self._edit_outline(drafted, verdict)
                usd += edit_usd
                if edited is not None:
                    drafted = edited
                    dest.write_text(json.dumps(drafted, indent=2) + "\n", encoding="utf-8")
                    (self.work_dir / "outline.md").write_text(
                        outlines.to_markdown(drafted), encoding="utf-8"
                    )
            else:
                raise OutlineRejected(
                    "the outline judge rejected the outline after "
                    f"{rounds} rounds",
                    ("outline",),
                )

        if self.require_approval and not self.resume:
            raise AwaitingApproval(self.work_dir / "outline.md")

        approved_by = "operator" if self.resume else "judge"
        stamped.write_text(
            json.dumps(outlines.stamp(drafted, approved_by=approved_by), indent=2) + "\n",
            encoding="utf-8",
        )
        return usd

    # -- 1b. sources -------------------------------------------------------

    def stage_sources(self, extra: str = "") -> StageResult:
        """Pick this run's search domains, once, before any paid search.

        The provider takes twenty domains for the whole run. The seed is vendor
        documentation, which is right for a paper about those vendors and close
        to useless for one about oncology or monetary policy. The librarian
        proposes this topic's twenty and `source_policy.admit` decides.

        A failure here is a note, never a stop. The seed still works. The
        offline fixture has no librarian reply, so it takes that path.
        """
        dest = self.work_dir / "corpus" / "source_allowlist.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        headings = []
        outline_path = self.work_dir / "outline.json"
        if outline_path.exists():
            drafted = json.loads(outline_path.read_text(encoding="utf-8"))
            headings = [section.get("heading") for section in drafted.get("sections") or []]
        elif self.plan:
            headings = [section.get("heading") for section in self.plan.get("sections") or []]
        pack = self.work_dir / "corpus" / "brain-pack.md"
        prior = pack.read_text(encoding="utf-8") if pack.exists() else ""
        briefing = _briefing_markdown(self.work_dir)
        if briefing:
            prior = f"{prior}\n\n{briefing}" if prior else briefing

        proposal: dict = {"domains": []}
        usd = 0.0
        try:
            reply = self._ask(
                "source_librarian",
                "Name the domains this paper should search.\n\n"
                f"Topic: {self.topic}\n\n"
                "Sections:\n"
                + "\n".join(f"- {heading}" for heading in headings if heading)
                + f"\n\nAt most {source_policy.MAX_PERPLEXITY_DOMAINS} entries. "
                "Each needs a host and an org_type from the schema enum. Name "
                "hosts, not journal titles. `.gov`, `.edu`, and `.int` may be "
                "whole top level domains; no other TLD is admitted. Cable news "
                "and encyclopedias are dropped under every type. Fewer good "
                "hosts beats a padded list. A scout briefing, if present, "
                "lists candidate hosts; propose from the headings and that "
                "map. Do not search."
                + (f"\n\nHosts the curated corpus already cites:\n{prior[:3000]}" if prior else "")
                + extra,
            )
            usd = reply.usd
            parsed = self._json_reply("source_librarian", reply)
            if isinstance(parsed, dict):
                proposal = parsed
        except BudgetSpent:
            raise
        except Exception as exc:
            self.say(f"  source librarian failed: {exc}; keeping the seed")

        decided = source_policy.admit(proposal.get("domains") or [])
        decided["seed_used"] = len(decided["admitted"]) < source_policy.MIN_ADMITTED
        dest.write_text(json.dumps(decided, indent=2) + "\n", encoding="utf-8")
        self.allowed_domains = source_policy.run_allowlist(decided["admitted"])
        setter = getattr(self.backend, "set_allowlist", None)
        if callable(setter):
            setter(self.allowed_domains)
        else:
            self.backend.allowlist = self.allowed_domains
        return StageResult(
            "sources",
            usd=usd,
            artifacts={
                "proposed": len(decided["proposed"]),
                "admitted": len(decided["admitted"]),
                "dropped": len(decided["dropped"]),
                "seed": decided["seed_used"],
            },
            summary=(
                f"{len(self.allowed_domains)} domains"
                + (" (seed)" if decided["seed_used"] else "")
            ),
        )

    # -- 2. search ---------------------------------------------------------

    def _pack_hits(self) -> list[dict]:
        """The hits `stage_corpus` wrote, or an empty list."""
        path = self.work_dir / "corpus" / "brain-pack.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [hit for hit in (payload.get("hits") or []) if isinstance(hit, dict)]

    def _resolve_pack_hit(self, pack: list[dict], key: str) -> tuple[dict | None, str]:
        """The cabinet record behind one reference key, and why there is none.

        The pack first, because it is already on disk and it is what this run
        planned against. A model writes the bare claim id where the pack holds
        `knowledge:claim.<subject>.<ULID>`, so an exact match alone rejects
        keys that are real. A suffix counts only on a segment boundary, or a
        short id would collide with the middle of an unrelated ULID.

        Two candidates end the search. `corpus.resolve` returns the first claim
        file whose name starts with the id, so falling through would settle the
        ambiguity by directory order and cite whichever paper sorted first.
        """
        import corpus as corpus_mod  # noqa: PLC0415

        if not key:
            return None, "unresolved corpus key"
        keys = [str(hit.get("key") or "") for hit in pack]
        if key in keys:
            return pack[keys.index(key)], ""
        matches = [item for item in keys if item.endswith((f".{key}", f":{key}"))]
        if len(matches) == 1:
            return pack[keys.index(matches[0])], ""
        if len(matches) > 1:
            return None, "ambiguous corpus key: " + ", ".join(sorted(matches))
        found = corpus_mod.resolve(key, list(self.brains))
        return (found.as_dict(), "") if found is not None else (None, "unresolved corpus key")

    def _located_cache(self) -> dict:
        path = self.work_dir / "corpus" / "located.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_located(self, cache: dict) -> None:
        path = self.work_dir / "corpus" / "located.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")

    def _record_unresolved(self, rows: list[dict]) -> None:
        """Append the cabinet sources that could not be cross-referenced."""
        if not rows:
            return
        path = self.work_dir / "corpus" / "unresolved.json"
        existing: list = []
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                existing = payload.get("unresolved") or []
            except (OSError, json.JSONDecodeError):
                existing = []
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"unresolved": [*existing, *rows]}, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _rewrite_claims(reply: dict, key: str, url: str) -> None:
        """Point every claim that named this corpus key at the located URL.

        A claim whose only reference is a corpus key is dropped by
        `record_findings`, because the key is not an allowed URL. Rewriting the
        reference is what keeps the claim and its source bound together.
        """
        for claim in reply.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            named = claim.get("source_urls") or []
            claim["source_urls"] = [
                url if locate.normalize_key(ref) == key else ref for ref in named
            ]

    @staticmethod
    def _drop_key_from_claims(reply: dict, key: str) -> list[str]:
        """Unbind a missed key, and drop the claims that rested on it alone.

        If the page does not support the sentence, the sentence does not go in
        the paper. Leaving the claim with an empty `source_urls` is worse than
        dropping it: `record_findings` reads "names none" as "inherits every
        source this answer produced", so a claim the cabinet could not back
        would be published citing an unrelated web page.

        A claim that also named an http source keeps that source and stays.
        A claim that named nothing to begin with is not this pass's business.
        """
        kept: list = []
        dropped: list[str] = []
        for claim in reply.get("claims") or []:
            if not isinstance(claim, dict):
                kept.append(claim)
                continue
            named = claim.get("source_urls") or []
            remaining = [ref for ref in named if locate.normalize_key(ref) != key]
            claim["source_urls"] = remaining
            if named and not remaining:
                dropped.append(str(claim.get("text") or "")[:60])
                continue
            kept.append(claim)
        reply["claims"] = kept
        return dropped

    def _locate_cabinet_sources(self, question: dict, reply: dict) -> dict:
        """Give every cabinet source in one reply a URL a reader can open, or drop it.

        A researcher that read `corpus_search` reports the hit as a source, and
        the only reference it has is the corpus key. `corpus:knowledge:claim.x`
        is not a bibliography entry, it is a string only this run understands.
        This asks the locator once per source and writes the answer back onto
        the reply, the SourceDocument in the brain, and a run-level cache.

        A source that cannot be located is removed from the reply along with
        every claim reference to it, and recorded in `corpus/unresolved.json`.
        Dropping it is the point: an unlocatable cabinet claim must not reach
        the paper wearing a reference nobody can follow.
        """
        import corpus as corpus_mod  # noqa: PLC0415

        del question  # the log line is per question; the work is per source
        sources = reply.get("sources") or []
        pack = self._pack_hits()
        # The belt. A researcher that cites the pack hit's public page instead
        # of its key has cited the same cabinet source, and the run must not
        # depend on which spelling the model chose: the skill says use the key,
        # and this is what happens when it does not. No turn, no rewrite.
        # First hit wins, and the pack is ranked, so two claims out of one
        # paper tag with the better of the two keys rather than the later one.
        public_keys: dict[str, str] = {}
        for hit in pack:
            public = str(hit.get("url") or "").strip()
            if public.lower().startswith(("http://", "https://")):
                public_keys.setdefault(public, str(hit.get("key") or ""))
        cache = self._located_cache()
        kept: list = []
        unresolved: list[dict] = []
        turns = hits = misses = 0

        for item in sources:
            if not isinstance(item, dict) or not locate.is_cabinet_url(item.get("url")):
                tag = public_keys.get(str((item or {}).get("url") or "").strip())
                if tag:
                    item["located_from"] = tag
                    hits += 1
                kept.append(item)
                continue

            key = locate.normalize_key(item.get("url"))
            hit, why = self._resolve_pack_hit(pack, key)
            if hit is None:
                unresolved.append(
                    {
                        "key": key,
                        "title": str(item.get("title") or ""),
                        "reason": why,
                        "claims_dropped": self._drop_key_from_claims(reply, key),
                    }
                )
                misses += 1
                continue

            pack_key = str(hit.get("key") or key)
            title = str(item.get("title") or "") or str(hit.get("source_title") or "")
            vendor = str(item.get("vendor") or "") or str(hit.get("vendor") or "")

            # The cabinet already knows where the public copy lives. Paying a
            # turn to rediscover it is money for an answer we hold.
            public = str(hit.get("url") or "")
            if public.startswith(("http://", "https://")):
                self._attach(item, reply, key, pack_key, public, hit)
                kept.append(item)
                hits += 1
                continue

            # One source, one answer. Two claims out of the same paper are one
            # turn, and the cache survives a stop between questions.
            dedupe = str(hit.get("source_hash") or "") or pack_key
            entry = cache.get(dedupe)
            if entry is None:
                if not title:
                    unresolved.append(
                        {
                            "key": pack_key,
                            "title": "",
                            "reason": "no title to locate",
                            "claims_dropped": self._drop_key_from_claims(reply, key),
                        }
                    )
                    misses += 1
                    continue
                reason = "not found"
                parsed = {"url": "", "supports": False, "excerpt": ""}
                # One tool call, and one provider call inside it. The locator
                # has no scout pass and no Ask repair, so a second request out
                # of this turn is a locator researching the claim instead.
                self.budget.begin_request(max_calls=1, max_provider_calls=1)
                try:
                    answer = self._ask("locator", locate.query_for(title, vendor, item.get("quote")))
                    parsed = self._json_reply("locator", answer)
                except (GateFailed, BudgetSpent) as exc:
                    reason = str(exc)
                finally:
                    self.budget.end_request()
                turns += 1
                url = locate.admit(parsed)
                entry = {
                    "url": url,
                    "supports": bool(url),
                    "excerpt": str(parsed.get("excerpt") or ""),
                    "key": pack_key,
                    "reason": "" if url else reason,
                }
                cache[dedupe] = entry
                # Before the next source, not at the end. A kill after a paid
                # turn must not make the next run pay for it again.
                self._write_located(cache)

            url = locate.admit(entry)
            if not url:
                unresolved.append(
                    {
                        "key": pack_key,
                        "title": title,
                        "reason": str(entry.get("reason") or "not found"),
                        "claims_dropped": self._drop_key_from_claims(reply, key),
                    }
                )
                misses += 1
                continue

            source_hash = str(hit.get("source_hash") or "")
            if source_hash:
                for root in self.brains:
                    if corpus_mod.attach_url(root, source_hash, url) is not None:
                        break
            self._attach(item, reply, key, pack_key, url, hit)
            kept.append(item)
            hits += 1

        reply["sources"] = kept
        self._record_unresolved(unresolved)
        self.say(f"    locate: {turns} turns, {hits} hits, {misses} misses")
        return {"turns": turns, "hits": hits, "misses": misses, "unresolved": unresolved}

    def _attach(self, item: dict, reply: dict, key: str, pack_key: str, url: str, hit: dict) -> None:
        """Install the located URL on the source item and on every claim."""
        item["url"] = url
        item["located_from"] = pack_key
        if not item.get("title"):
            item["title"] = str(hit.get("source_title") or "")
        if not item.get("vendor"):
            item["vendor"] = str(hit.get("vendor") or "")
        self._rewrite_claims(reply, key, url)

    def stage_search(self, extra: str = "") -> StageResult:
        self._need_plan()
        usd = 0.0
        for question in self.plan["questions"]:
            # Only a finding with admitted claims is complete. Persisting an
            # empty finding is useful diagnostics, but treating it as answered
            # makes the stage's "search again with narrower wording" retry a
            # no-op that immediately fails with the same signature.
            if any(
                f.subject == question["subject"]
                and (f.claim_ids or not question.get("important"))
                for f in self.ledger.findings.values()
            ):
                continue
            # This one binding question is about checked-in Python, not the
            # web. Perplexity does not index the file, and asking a model to
            # rewrite the query can turn the exact repository lookup into a
            # generic vendor search. Validate and record the first-party source
            # deterministically; every other question still goes through the
            # Deep Agents researcher and its single filtered search tool.
            repository_report = (
                research.repository_doctrine_report(question["question"])
                if self.loop_doctrine and self.runner.name == "deep_agents"
                else None
            )
            if repository_report is not None:
                stages.record_findings(
                    self.ledger,
                    question,
                    repository_report,
                    seed=self.allowed_domains,
                    backend=self.backend,
                )
                self.ledger.write()
                continue
            # The researcher has one tool call. Its filtered Perplexity boundary
            # may spend Scout, Retrieve, and the no-quote Ask repair inside that
            # one call, so provider reservations have their own hard ceiling.
            self.budget.begin_request(max_calls=1, max_provider_calls=3)
            try:
                reply = self._ask(
                    "researcher",
                    f"Question: {question['question']}\n"
                    f"What answers it: {question['check']}\n{extra}\n\n"
                    "Search once, then return JSON: "
                    '{"answer": "...", "sources": [{"title": "...", "url": "...", '
                    '"vendor": "...", "quote": "..."}], '
                    '"claims": [{"text": "...", "confidence": 0.8, "source_urls": ["..."]}]}',
                )
            finally:
                self.budget.end_request()
            usd += reply.usd
            parsed = self._json_reply("researcher", reply)
            # Before the ledger, not after. `record_findings` refuses a source
            # whose URL fails the allowlist, and a corpus key fails it, so a
            # cabinet source that is not cross-referenced here never reaches
            # the bibliography at all.
            self._locate_cabinet_sources(question, parsed)
            stages.record_findings(
                self.ledger,
                question,
                parsed,
                seed=self.allowed_domains,
                backend=self.backend,
            )
            # Persist per question. A stop between questions must not discard
            # the answers this run already paid for.
            self.ledger.write()
        # Every one of these returns what it spent, added into this stage's
        # own total. `_ask` already adds every call to
        # `self.state.total_cost_usd` regardless; without this,
        # `stage_search`'s `StageResult.usd` (what `mark_complete` records
        # as this stage's `cost_usd`) undercounted by exactly what these
        # passes spent, and the invariant
        # `state.total_cost_usd == sum(stage.cost_usd for every stage)`
        # silently broke the moment any of them spent a real turn.
        usd += self._follow_primaries()
        usd += self._counter_evidence()
        usd += self._research_shortfalls()
        self._record_scout_title_status()
        stages.search_gate(self.ledger, self.plan, unmet=self.evidence_shortfall_unmet)
        self.ledger.write()
        provider = self.backend.active_name
        transport = self.backend.active_transport
        return StageResult(
            "search",
            usd=usd,
            artifacts={
                "claims": len(self.ledger.claims),
                "sources": len(self.ledger.sources),
                "provider": provider,
                "transport": transport,
            },
            summary=(
                f"{len(self.ledger.claims)} claims from {len(self.ledger.sources)} sources "
                f"via {provider}" + (f" ({transport})" if transport else "")
            ),
        )

    def _follow_primaries(self) -> float:
        """One follow turn per shaky numeric claim, capped at `self.max_follow`
        across the whole run, not per `stage_search` attempt. #473

        A claim bound only to a review, a preprint, or a compilation is
        asked once for the primary study behind its number. A hit rebinds
        the claim to that primary; a miss is recorded `secondary`, so
        `stages.claim_brief` can tell the writer "as summarized by [n]".

        `self.follow_used`, loaded from `state.follow_used`, is the running
        count across every call. `stage_search` retries on a `search_gate`
        failure by re-entering this same method from the top; without the
        persisted count, each retry saw a fresh `max_follow` and a run could
        spend `max_follow * attempts` turns rather than `max_follow`.

        Returns what it spent, so `stage_search` can fold it into its own
        `StageResult.usd`. `_ask` already adds every call to
        `self.state.total_cost_usd` on its own; a caller that dropped this
        return value undercounted the search stage's own recorded cost by
        exactly this much. #474
        """
        candidates = stages.claims_needing_a_primary(self.ledger)
        if not candidates:
            return 0.0
        remaining = max(0, self.max_follow - self.follow_used)
        followed = candidates[:remaining]
        self.say(
            f"    follow: {len(followed)} of {len(candidates)} candidate(s), "
            f"{self.follow_used + len(followed)}/{self.max_follow} used this run"
        )
        spent = 0.0
        for claim in followed:
            self.budget.begin_request(max_calls=1, max_provider_calls=3)
            try:
                reply = self._ask(
                    "researcher",
                    f"This numeric claim rests only on a summary, not the primary study: "
                    f"{claim.text}\n\nFind the primary study the summary cites for this "
                    "number. Search once. Return JSON: "
                    '{"found": true|false, "url": "...", "title": "...", "quote": "..."}.',
                )
            finally:
                self.budget.end_request()
            spent += reply.usd
            parsed = self._json_reply("researcher", reply)
            stages.apply_follow_result(self.ledger, claim, parsed, backend=self.backend)
            self.follow_used += 1
            self.state.follow_used = self.follow_used
            self.state.save()
        return spent

    def _counter_evidence(self) -> float:
        """One counter-evidence turn per generalizing claim, capped at
        `self.max_counter` across the whole run, not per `stage_search`
        attempt. #474

        A hit creates a new claim bound to its own source,
        `counterargument_to` pointing at the claim it contradicts. A miss is
        recorded on the claim's own `counter` field ("hit", "miss"), never
        `note`: `apply_verification` overwrites `note` on its `disagreed`
        and `not_found` branches, and the verifier runs right after this
        pass on the live `STAGE_ORDER`.

        `self.counter_used`, loaded from `state.counter_used`, is the
        running count across every call, the same way `follow_used` bounds
        `_follow_primaries`. `stages.generalizing_claims` already excludes a
        claim that already carries a `counter` state, so a retry does not
        re-ask it.

        A candidate the cap does not reach this call is marked `capped`
        immediately, deterministically, with no model turn: `counterweighed`
        must find every generalizing claim in one of `hit`, `miss`, or
        `capped` once this pass has run, and a `capped` claim's brief tells
        the writer to hedge it like a single source.

        Returns what it spent, so `stage_search` can fold it into its own
        `StageResult.usd`. #474
        """
        candidates = stages.generalizing_claims(self.ledger)
        if not candidates:
            return 0.0
        remaining = max(0, self.max_counter - self.counter_used)
        followed = candidates[:remaining]
        for claim in candidates[remaining:]:
            claim.counter = "capped"
            claim.counter_note = "counter-evidence not searched, run cap reached"
        self.say(
            f"    counter: {len(followed)} of {len(candidates)} candidate(s), "
            f"{self.counter_used + len(followed)}/{self.max_counter} used this run"
        )
        spent = 0.0
        for claim in followed:
            self.budget.begin_request(max_calls=1, max_provider_calls=3)
            try:
                reply = self._ask(
                    "researcher",
                    f"This claim generalizes: {claim.text}\n\nFind evidence that "
                    "it is not the case, or holds only under conditions. Search "
                    'once. Return JSON: {"found": true|false, "counter_claim": '
                    '"...", "url": "...", "title": "...", "quote": "..."}.',
                )
            finally:
                self.budget.end_request()
            spent += reply.usd
            parsed = self._json_reply("researcher", reply)
            stages.apply_counter_result(self.ledger, claim, parsed, backend=self.backend)
            self.counter_used += 1
            self.state.counter_used = self.counter_used
            self.state.save()
        return spent

    def _research_shortfalls(self) -> float:
        """One extra research turn per important question whose bound
        evidence still falls short of its own `evidence_requirements` block,
        before `search_gate` grades it. #475

        `self.evidence_shortfall_unmet`, persisted to
        `state.evidence_shortfall_unmet`, holds a question id once its one
        shot is spent and the block is still short: `stage_search` retries
        on a `search_gate` failure by re-entering this method from the top,
        and it is a specific still-short question, not a shared budget,
        that must not be asked twice. A question the one extra turn fully
        resolves is never added: `evidence_shortfall` on the next check
        already reads "" for it, the same as one that was never short.

        Judge revision on #520, blocking finding 1: a shortfall that
        survives the one turn used to end the run, because `search_gate`
        re-entered this method found nothing left to do and failed with an
        unchanged signature. Being marked unmet here is what lets
        `search_gate` accept the gap as named, not terminal, the same shape
        `_counter_evidence`'s `capped` state already gives `counterweighed`.

        Returns what it spent, so `stage_search` can fold it into its own
        `StageResult.usd`. #475
        """
        spent = 0.0
        for question in self.plan.get("questions", []):
            if not question.get("important"):
                continue
            qid = question.get("id") or ""
            if qid in self.evidence_shortfall_unmet:
                continue
            # This one question is about checked-in Python, answered by
            # `stage_search`'s own repository lookup, never a model. Asking
            # a researcher turn about it here would be the same mistake
            # `stage_search`'s own comment already refuses. #475
            if (
                self.loop_doctrine
                and self.runner.name == "deep_agents"
                and research.repository_doctrine_report(question["question"]) is not None
            ):
                continue
            reason = stages.evidence_shortfall(self.ledger, question)
            if not reason:
                continue
            self.say(f"    evidence_requirements shortfall on {qid}: {reason}")
            self.budget.begin_request(max_calls=1, max_provider_calls=3)
            try:
                reply = self._ask(
                    "researcher",
                    f"Question: {question['question']}\n"
                    f"What answers it: {question['check']}\n"
                    f"Evidence requirements shortfall: {reason}. Search again "
                    "naming what is missing.\n\n"
                    "Search once, then return JSON: "
                    '{"answer": "...", "sources": [{"title": "...", "url": "...", '
                    '"vendor": "...", "quote": "..."}], '
                    '"claims": [{"text": "...", "confidence": 0.8, "source_urls": ["..."]}]}',
                )
            finally:
                self.budget.end_request()
            spent += reply.usd
            parsed = self._json_reply("researcher", reply)
            self._locate_cabinet_sources(question, parsed)
            stages.record_findings(
                self.ledger, question, parsed, seed=self.allowed_domains, backend=self.backend
            )
            self.ledger.write()
            still_short = stages.evidence_shortfall(self.ledger, question)
            if still_short:
                self.evidence_shortfall_unmet[qid] = still_short
                self.state.evidence_shortfall_unmet = dict(self.evidence_shortfall_unmet)
                self.state.save()
        return spent

    def _record_scout_title_status(self) -> None:
        """Each scout-briefing flagship title, retrieved or a named skip. #475

        The scout's `titles` are a map, not evidence; this is what makes the
        map bind to something a reader can open, or names why it does not.
        Recomputed on every call, not accumulated: a `stage_search` retry
        only adds sources, never removes one, so a later recompute can only
        turn a skip into a retrieval, never the reverse -- no persisted
        counter is needed here, unlike the scout retry and the shortfall
        pass, neither of which is free to repeat.
        """
        path = self.work_dir / "corpus" / "scout-briefing.json"
        if not path.exists():
            return
        try:
            briefing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        titles = briefing.get("titles") or []
        if not titles:
            return
        status = []
        for title in titles:
            retrieved = _scout_title_retrieved(title, self.ledger.sources.values())
            status.append(
                {
                    "title": title,
                    "retrieved": retrieved,
                    "reason": "" if retrieved else "no admitted source matched this title",
                }
            )
        briefing["title_status"] = status
        path.write_text(json.dumps(briefing, indent=2) + "\n", encoding="utf-8")

    # -- 3. verify ---------------------------------------------------------

    def stage_verify(self, extra: str = "") -> StageResult:
        self._need_ledger()
        # The list handed to the verifier is the size of the work, because it
        # searches once per claim. Bounded, shakiest first. Everything past the
        # cap is written down as not cross-checked rather than quietly dropped.
        pending, skipped = stages.verify_batch(self.ledger, self.max_verify)
        stages.note_uncrosschecked(skipped)
        if not pending:
            self.ledger.write()
            self.state.mark_skipped("verify", "no claim needed a second look")
            return StageResult("verify", summary="no important claims to check")

        listing = "\n".join(f"- {claim.id}: {claim.text}" for claim in pending)
        reply = self._ask(
            "verifier",
            f"Cross-check each claim below against a second, independent source.\n{extra}\n\n"
            f"{listing}\n\n"
            'Return JSON: {"checked": [{"claim_id": "...", "second_source_url": "...", '
            '"corroborate_status": "agreed|disagreed|not_found", "quote": "...", '
            '"queries_used": ["..."]}]}. On `not_found`, report every query you tried; '
            "silence is not a result.",
        )
        counts = stages.apply_verification(
            self.ledger,
            stages.resolve_placeholders(self._json_reply("verifier", reply), self.ledger),
            backend=self.backend,
        )
        stages.verify_gate(self.ledger)
        self.ledger.write()
        return StageResult(
            "verify",
            usd=reply.usd,
            artifacts=counts,
            summary=f"{counts.get('corroborated', 0)} corroborated, "
            f"{counts.get('single_source', 0)} single source, "
            f"{counts.get('contradicted', 0)} contradicted"
            + (f", {len(skipped)} past the cap" if skipped else ""),
        )

    # -- 4. outline --------------------------------------------------------

    def stage_outline(self, extra: str = "") -> StageResult:
        self._need_plan()
        self._need_ledger()
        usable = [
            f"- {claim.id} [{claim.truth_state}]: {claim.text}"
            for claim in self.ledger.claims.values()
            if claim.usable
        ]
        reply = self._ask(
            "writer",
            f"Title: {self.plan['title']}\nAudience: {self.plan['audience']}\n"
            f"Sections the plan asked for: "
            f"{', '.join(stages.plan_heading(item) for item in self.plan['sections'])}\n"
            f"Figures available: {[f['name'] for f in self.plan['diagrams']]}\n{extra}\n\n"
            "Bind each section to the claims it may use. Claims:\n"
            + "\n".join(usable)
            + '\n\nReturn JSON: {"sections": [{"heading": "...", "purpose": "...", '
            '"claim_ids": ["..."], "figures": ["..."]}]}',
        )
        self.outline = stages.resolve_placeholders(
            self._json_reply("writer-outline", reply), self.ledger
        )
        stages.outline_gate(self.outline, self.ledger, self.plan)
        path = self.work_dir / "outline.json"
        path.write_text(json.dumps(self.outline, indent=2), encoding="utf-8")
        self.state.record("outline", path)
        return StageResult(
            "outline",
            usd=reply.usd,
            artifacts={"sections": len(self.outline["sections"])},
            summary=f"{len(self.outline['sections'])} sections bound to claims",
        )

    # -- 5. diagram --------------------------------------------------------

    def stage_diagram(self, extra: str = "") -> StageResult:
        """Commission every planned figure, from the section's own claims.

        `diagram` moved here from right after `outline` (#476): a figure
        cannot be commissioned from claims that do not exist until the
        section is written. Guarded by `sections_sha`, recorded in
        `diagrams.json`: re-commissioning on every write retry is not
        acceptable at a diagram's price, so a matching sha skips straight to
        the already-rendered figures.

        The guard is coarse (one hash for every section, not one per
        figure), but the attempt budget is durable per figure regardless:
        `diagrams.json` carries each figure's lifetime `attempts` and
        `dropped` state, and a sections_sha change does not buy an
        already-dropped figure a fresh three. #476 B2. A figure whose own
        source still renders keeps redrawing on a real content change, the
        same as before; only a figure that already exhausted its budget
        stays untouched.
        """
        self._need_written()
        planned = self.plan.get("diagrams") or []
        if not planned:
            self.state.mark_skipped("diagram", "the plan asked for no figures")
            return StageResult("diagram", summary="no figures planned")

        sections_sha = _sections_sha(self.written)
        guard_path = self.work_dir / "diagrams.json"
        recorded: dict = {}
        if guard_path.exists():
            try:
                recorded = json.loads(guard_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                recorded = {}
        if recorded.get("sections_sha") == sections_sha:
            self.figures, _ = stages.render_figures(
                self.diagram_src, self.figure_dir, self.plan.get("title") or self.topic,
                theme_name=self.theme,
            )
            accepted = sum(1 for figure in self.figures if figure.best is not None)
            return StageResult(
                "diagram",
                artifacts={"figures": len(self.figures), "accepted": accepted},
                summary="unchanged sections, figures kept",
            )
        if recorded and not self._redraw:
            # A previously commissioned run, but the sections moved. The
            # guard is coarse the same way the Agent SDK port's is: redraw
            # every figure rather than track which one's owning section
            # changed. `self._redraw` is only non-empty mid-retry, inside one
            # already-in-progress commissioning attempt; do not repeat this
            # wipe on that path.
            for stale in self.diagram_src.glob("*"):
                if stale.suffix in (".mmd", ".puml"):
                    stale.unlink()

        self.diagram_src.mkdir(parents=True, exist_ok=True)
        usd = 0.0
        dropped: set[str] = set()
        previous = {f.get("name"): f for f in (recorded.get("figures") or [])}
        records: dict[str, dict] = dict(previous)
        for figure in planned:
            name = evidence.slug(figure["name"])
            prior = previous.get(name) or {}
            # #476 N2: the budget check reads `dropped`, not attempts alone.
            # A figure that succeeded is not carrying a lifetime debt; only
            # a durably dropped figure's prior attempts count against the
            # next budget. Charging a passed figure's own `attempts: 3` here
            # left `remaining` at 0, an empty attempt loop that never
            # rebuilds a source the wipe-on-change step just deleted, and
            # `diagram_gate` raised `missing_figures` on re-entry for a
            # figure the run never dropped.
            spent = int(prior.get("attempts") or 0) if prior.get("dropped") else 0
            if prior.get("dropped") and spent >= diagrams.MAX_LABEL_ATTEMPTS:
                # This figure already spent its lifetime attempt budget on
                # an earlier commissioning. A section changing elsewhere in
                # the paper must not buy it a fresh three; durable means
                # durable. No source, no ask, no image.
                dropped.add(name)
                continue
            remaining = diagrams.MAX_LABEL_ATTEMPTS - spent
            suffix = ".mmd" if figure["kind"] == "mermaid" else ".puml"
            target = self.diagram_src / f"{name}{suffix}"
            # Same rule as the writer: a source that already rendered is kept.
            # A retry redraws only what the complexity gate rejected, and
            # `_retry_targets` says which those are.
            if target.exists() and name not in self._redraw:
                continue
            ordered_exits = all(
                term in figure.get("shows", "").lower()
                for term in ("done", "cost", "max-turn", "order")
            )
            order_instruction = (
                "\nDraw done, cost, and max-turns as sequential decision nodes. "
                "The no edge from done leads to cost, and the no edge from cost leads "
                "to max turns. Never fan all three exits out from one node."
                if ordered_exits
                else ""
            )
            claims = self._claims_for_figure(figure["name"])
            claim_texts = [claim.text for claim in claims]
            grounding = (
                "\nClaims this section may draw on:\n" + "\n".join(f"- {t}" for t in claim_texts)
                if claim_texts
                else ""
            )
            mismatch_note = ""
            for attempt in range(1, remaining + 1):
                # Clear any prior draft before asking: a redraw must land, not
                # be skipped because the last attempt's file is still there.
                # A live subagent then writes its own fresh file with its own
                # tool during `_ask`; Python's fallback below only fires when
                # that did not happen.
                target.unlink(missing_ok=True)
                reply = self._ask(
                    "diagrammer",
                    f"Draw a {figure['kind']} diagram named {name}.\n"
                    f"It must show: {figure['shows']}{order_instruction}{grounding}\n"
                    f"Paper topic: {self.topic}\n{extra}{mismatch_note}\n\n"
                    "Return only the diagram source. No fences, no commentary.",
                )
                usd += reply.usd
                # A scoped Deep Agents diagrammer writes the requested source.
                # Its final message may only acknowledge that tool call.
                # Preserve the file in that case; answer-only and fixture
                # runners still supply source in the reply for Python to
                # checkpoint.
                if not target.exists():
                    target.write_text(_strip_fence(reply.text), encoding="utf-8")
                # #476 F3: absence of claims is not support, so this always
                # runs, `claims` empty included.
                inv = diagrams.inventory(target.read_text(encoding="utf-8"), diagrams.kind_of(target))
                mismatches = diagrams.figure_claims(inv.labels, claims)
                if not mismatches:
                    records[name] = {"name": name, "attempts": spent + attempt, "dropped": False}
                    break
                if attempt == remaining:
                    # #476 B2/B3: budget exhausted. The figure is dropped:
                    # no source, no image, no dangling reference in the
                    # paper, and it stays dropped through a later section
                    # change instead of a later successful redraw landing
                    # it as an orphan under a generated Figures heading.
                    target.unlink(missing_ok=True)
                    dropped.add(name)
                    self._drop_figure_reference(figure["name"])
                    self.say(f"    note: {name} dropped, labels never matched the section's claims")
                    records[name] = {"name": name, "attempts": spent + attempt, "dropped": True}
                    break
                mismatch_note = (
                    "\n\nThe last draft's labels do not match this section's claims: "
                    + "; ".join(mismatches)
                    + ". Redraw with labels the claims above support."
                )

        survivors = [f for f in planned if evidence.slug(f["name"]) not in dropped]

        semantic_complaints = []
        for figure in survivors:
            description = figure.get("shows", "").lower()
            if not all(term in description for term in ("done", "cost", "max-turn", "order")):
                continue
            name = evidence.slug(figure["name"])
            suffix = ".mmd" if figure["kind"] == "mermaid" else ".puml"
            target = self.diagram_src / f"{name}{suffix}"
            if figure["kind"] != "mermaid" or not diagrams.ordered_exit_checks(
                target.read_text(encoding="utf-8")
            ):
                semantic_complaints.append(
                    f"{target.name}: show done, then cost, then max turns as sequential "
                    "checks; do not draw them as parallel branches."
                )
        if semantic_complaints:
            self._redraw = {
                Path(complaint.split(":", 1)[0]).stem for complaint in semantic_complaints
            }
            raise GateFailed(" ".join(semantic_complaints), ("exit_order",))

        self.figures, complaints = stages.render_figures(
            self.diagram_src,
            self.figure_dir,
            self.plan.get("title") or self.topic,
            theme_name=self.theme,
        )
        # #514: a live backend call failing for one figure, once the
        # renderer already reported itself available, must not sink the
        # whole run. `stages.render_figures` marks such a complaint with
        # `BACKEND_FAILURE_MARK`; pull those figures out before the gate
        # ever sees them as "missing," the same way a claims-mismatch drop
        # already does, and name the backend's own error in `records`.
        backend_failed: dict[str, str] = {}
        for complaint in complaints:
            if stages.BACKEND_FAILURE_MARK in complaint:
                name = Path(complaint.split(":", 1)[0]).stem
                backend_failed[name] = complaint.split(stages.BACKEND_FAILURE_MARK, 1)[1]
        if backend_failed:
            complaints = [c for c in complaints if stages.BACKEND_FAILURE_MARK not in c]
            for name, reason in backend_failed.items():
                dropped.add(name)
                prior_attempts = records.get(name, {}).get("attempts", 0)
                # A backend failure is not a label failure. `dropped: True`
                # here would make the durable budget check above (`spent =
                # attempts if dropped else 0`) treat a figure that already
                # earned its labels as permanently disqualified once
                # `attempts` reaches `MAX_LABEL_ATTEMPTS`, for a cause its
                # labels had nothing to do with; the Agent SDK does not
                # have this problem, it leaves `dropped` false on the same
                # path. Keep `dropped` false and `attempts` exactly what
                # the label loop already earned, so a later commissioning
                # gets its full label budget back once the backend
                # recovers.
                figure_spec = next(
                    (f for f in survivors if evidence.slug(f["name"]) == name), None
                )
                # #464. The owning section, captured before the reference is
                # dropped below: `_drop_figure_reference` empties this out
                # of `outline.json`, and `assemble` still needs to know
                # where to name the skip.
                owning_section = None
                if figure_spec:
                    owning_section = self._section_for_figure(figure_spec["name"])
                records[name] = {
                    "name": name,
                    "attempts": prior_attempts,
                    "dropped": False,
                    "section": (owning_section or {}).get("id") or "",
                    "reason": f"{stages.BACKEND_FAILURE_MARK}{reason}",
                }
                self.say(f"    note: {name} skipped, {stages.BACKEND_FAILURE_MARK}{reason}")
                if figure_spec:
                    self._drop_figure_reference(figure_spec["name"])
            survivors = [f for f in survivors if evidence.slug(f["name"]) not in backend_failed]
        self._redraw = {Path(c.split(":", 1)[0]).stem for c in complaints}
        stages.diagram_gate(self.figures, complaints, survivors)
        for complaint in complaints:
            self.say(f"    note: {complaint}")
        figure_records = [
            records[evidence.slug(f["name"])]
            for f in planned
            if evidence.slug(f["name"]) in records
        ]
        guard_path.write_text(
            json.dumps({"figures": figure_records, "sections_sha": sections_sha}, indent=2) + "\n",
            encoding="utf-8",
        )
        # #476 F4: this stage is done. A complaint that did not trip
        # `diagram_gate` above must not leave `_redraw` non-empty for a
        # later, unrelated `stage_diagram` call to misread as "mid-retry",
        # which would skip both the stale-source wipe and every figure
        # whose source is still on disk, claims gate included.
        self._redraw = set()
        accepted = sum(1 for figure in self.figures if figure.best is not None)
        claims_dropped = len(dropped) - len(backend_failed)
        return StageResult(
            "diagram",
            usd=usd,
            artifacts={"figures": len(self.figures), "accepted": accepted, "dropped": sorted(dropped)},
            summary=f"{accepted} judged imagen-diagrams PNGs"
            + (f", {claims_dropped} dropped for a claims mismatch" if claims_dropped else "")
            + (
                f", {len(backend_failed)} skipped, image backend unavailable"
                if backend_failed
                else ""
            ),
        )

    def _section_for_figure(self, figure_name: str) -> dict | None:
        """The outline section that named this figure in `figures: [...]`."""
        slug = evidence.slug(figure_name)
        for section in self.outline.get("sections", []):
            for entry in section.get("figures") or []:
                if evidence.slug(str(entry)) == slug:
                    return section
        return None

    def _claims_for_figure(self, figure_name: str) -> list:
        """This figure's owning section's usable claims, for the diagrammer
        and for `figure_claims`. Empty when no section names this figure, or
        the section is not yet bound to any claim."""
        section = self._section_for_figure(figure_name)
        if section is None:
            return []
        claims = []
        for claim_id in section.get("claim_ids") or []:
            claim = self.ledger.claim(claim_id)
            if claim is not None and claim.usable:
                claims.append(claim)
        return claims

    def _drop_figure_reference(self, figure_name: str) -> None:
        """Remove a dropped figure's name from every section that named it.

        `assemble` already skips a name with no rendered `Figure` behind it,
        so this is not load bearing for "no dangling image" -- it keeps
        `outline.json` honest about what the paper actually carries.
        """
        slug = evidence.slug(figure_name)
        changed = False
        for section in self.outline.get("sections", []):
            figures = section.get("figures") or []
            kept = [f for f in figures if evidence.slug(str(f)) != slug]
            if len(kept) != len(figures):
                section["figures"] = kept
                changed = True
        if changed:
            (self.work_dir / "outline.json").write_text(
                json.dumps(self.outline, indent=2), encoding="utf-8"
            )

    # -- 5b. charts --------------------------------------------------------

    def stage_charts(self, extra: str = "") -> StageResult:
        """Render `kind: chart` figures. Python plots; the chartist only specs.

        A chart with no rows is skipped with `no data`, not with a phase-skip
        log. No model touches the pixels.
        """
        import charts as charts_mod  # noqa: PLC0415

        if not self.outline:
            path = self.work_dir / "outline.json"
            if path.exists():
                self.outline = json.loads(path.read_text(encoding="utf-8"))
        if not self.outline:
            self.state.mark_skipped("charts", "no outline")
            return StageResult("charts", summary="no outline")
        planned = outlines.charts(self.outline)
        dest = self.work_dir / "charts"
        dest.mkdir(parents=True, exist_ok=True)
        rendered = []
        skipped = []
        usd = 0.0
        ledger = _paper_ledger(self.work_dir)
        for figure in planned:
            name = figure.get("name") or "chart"
            rows = charts_mod.collect(self.work_dir, figure, ledger)
            if not rows:
                self.say(f"    skipping chart {name!r}: no data")
                # #386, #464. A skip is the product, not a phase-skip log
                # line nobody reads: `section` and `reason` travel with the
                # name so `assemble` can name both under the section a
                # reader expects this chart to sit in.
                skipped.append({"name": name, "section": figure.get("section") or "", "reason": "no data"})
                continue
            spec = {}
            try:
                reply = self._ask(
                    "chartist",
                    "Return a chart spec. Do not invent a number. Empty rows "
                    "means an empty spec.\n"
                    + json.dumps({"figure": figure, "rows": rows[:40]}, indent=2)
                    + (f"\n{extra}" if extra else ""),
                )
                usd += reply.usd
                parsed = stages.parse_json(reply.text) if reply.text else {}
                if isinstance(parsed, dict):
                    spec = parsed
            except BudgetSpent:
                raise
            except Exception:
                spec = {}
            if not spec.get("x"):
                spec = charts_mod.default_spec(figure, rows)
            spec.setdefault("section", figure.get("section") or "")
            spec.setdefault("name", name)
            record = charts_mod.render(spec, rows, dest)
            record["section"] = figure.get("section") or spec.get("section") or ""
            rendered.append(record)
            self.say(f"    chart {name}: {len(record.get('values') or [])} values")
        self.charts = rendered
        (self.work_dir / "charts.json").write_text(
            json.dumps({"charts": rendered, "skipped": skipped}, indent=2) + "\n",
            encoding="utf-8",
        )
        if not planned:
            self.state.mark_skipped("charts", "the outline asked for no charts")
        return StageResult(
            "charts",
            usd=usd,
            artifacts={"rendered": len(rendered), "skipped": len(skipped)},
            summary=f"{len(rendered)} charts, {len(skipped)} skipped",
        )

    # -- 6. write ----------------------------------------------------------

    def stage_write(self, extra: str = "") -> StageResult:
        self._need_outline()
        # #452 #465 #412. `extra` carries a prior attempt's gate failure text
        # on a retry, and the writer must not see an admitted host or the
        # harness's own retrieval language in it either.
        extra = _strip_policy_leak(extra, self.allowed_domains)
        # `write` can be interrupted between sections. Load its artifact before
        # deciding what remains so a resumed process preserves every accepted
        # section instead of spending another turn to replace it.
        if not self.written:
            path = self.work_dir / "sections.json"
            if path.exists():
                self.written = json.loads(path.read_text(encoding="utf-8"))
        index, _ = stages.numbering(self.ledger)
        usd = 0.0
        # P7, #472. The abstract restates the body, so it is written last, from
        # the sections already stamped. `sorted` is stable, so every other
        # section keeps the outline's own order; only "Abstract" moves to the
        # end of the loop. #478: the conclusion restates the body the same
        # way, so it joins the abstract at the end. `normalize_plan` already
        # puts Abstract ahead of Conclusion in the outline's own order, and
        # the stable sort keeps that order inside the moved group.
        ordered_sections = sorted(
            self.outline["sections"],
            key=lambda item: item["heading"].strip().lower() in ("abstract", "conclusion"),
        )
        for section in ordered_sections:
            heading = section["heading"]
            # Methods is Python-written at assemble time, never by the
            # writer: it never reaches `close_section`. #478
            if heading.lower() in ("references", "methods"):
                continue
            # A section that already passed its gate is kept across a retry. The
            # retry exists to fix the section that failed, and rewriting the
            # ones that passed spends money to risk breaking them.
            if heading in self.written:
                continue
            claim_ids = section.get("claim_ids") or []
            if heading.lower() in stages.UNBOUND_SECTIONS:
                # The abstract restates the paper. It may cite anything the
                # paper cites, and nothing the paper does not.
                claim_ids = [c.id for c in self.ledger.claims.values() if c.usable]
            allowed = sorted(
                {
                    index[sid]
                    for cid in claim_ids
                    if self.ledger.claim(cid)
                    for sid in self.ledger.claim(cid).source_ids
                    if sid in index
                }
            )
            # #517. Every on-topic guideline the ledger already holds from
            # another section's research, named for the writer and added to
            # `allowed` so citing it here is never read as a stray citation.
            guideline_note, allowed = sections.guideline_brief(
                self.ledger, section, self.topic, index, allowed
            )
            briefs = "\n".join(stages.claim_brief(self.ledger, cid, index) for cid in claim_ids)
            if guideline_note:
                briefs = f"{briefs}\n{guideline_note}" if briefs else guideline_note
            word_range = _section_word_range(heading, len(claim_ids))
            # #475, judge revision on #520: a question graded and still
            # short after its one shot travels as a named gap, not a run
            # failure. The section that answers it is told to hedge its
            # generalizations the same way a single-source claim is
            # hedged, so the paper does not overstate what a thin ledger
            # supports.
            subjects = {self.ledger.claim(cid).subject for cid in claim_ids if self.ledger.claim(cid)}
            shortfalls = [
                self.evidence_shortfall_unmet[qid]
                for question in self.plan.get("questions", [])
                if question.get("subject") in subjects
                and (qid := question.get("id") or "") in self.evidence_shortfall_unmet
            ]
            hedge = (
                "Evidence requirements were not fully met for this section: "
                f"{'; '.join(shortfalls)}. Hedge every generalization here the way "
                "a single-source claim is hedged: say what the evidence shows is "
                "limited, not settled.\n"
                if shortfalls
                else ""
            )
            if heading.strip().lower() == "abstract":
                # Every other section is already stamped by the time this
                # runs. The writer may state only what that body states, and
                # must carry the same hedge the body carries.
                written_body = "\n\n".join(
                    f"## {other}\n\n{text}" for other, text in self.written.items()
                )
                lead = (
                    f"Write the {heading!r} section of {self.plan['title']!r}, last, "
                    "from the body already written below. State only what that body "
                    "states, and carry the same hedge it carries for a single-source "
                    "claim: say \"single source\", \"one study\", \"one trial\", or "
                    "\"preliminary\" in the same sentence that cites it. Never write "
                    "\"proves\", \"definitively\", \"conclusively\", or \"establishes "
                    "that\" for a claim the body hedges.\n"
                    f"Purpose: {section.get('purpose', '')}\n"
                    f"Audience: {self.plan['audience']}\n{extra}\n{hedge}\n"
                    f"The paper body, already written:\n{written_body}\n\n"
                )
            elif heading.strip().lower() == "conclusion":
                # #478. One writer turn after the body, from the body, with
                # no new citation: `allowed` above already carries every
                # numbered source the paper cites, and none the paper does
                # not, so a marker outside that set is a stray citation the
                # write gate rejects.
                written_body = "\n\n".join(
                    f"## {other}\n\n{text}" for other, text in self.written.items()
                )
                lead = (
                    f"Write the {heading!r} section of {self.plan['title']!r}, from the "
                    "body already written below. State only what that body states. Cite "
                    "only a number the body already cites; introduce no new source and "
                    "no new citation. Carry the same hedge it carries for a "
                    "single-source claim: say \"single source\", \"one study\", \"one "
                    "trial\", or \"preliminary\" in the same sentence that cites it. "
                    "Never write \"proves\", \"definitively\", \"conclusively\", or "
                    "\"establishes that\" for a claim the body hedges.\n"
                    f"Purpose: {section.get('purpose', '')}\n"
                    f"Audience: {self.plan['audience']}\n{extra}\n{hedge}\n"
                    f"The paper body, already written:\n{written_body}\n\n"
                )
            else:
                lead = (
                    f"Write the {heading!r} section of {self.plan['title']!r}.\n"
                    f"Purpose: {section.get('purpose', '')}\n"
                    f"Audience: {self.plan['audience']}\n{extra}\n{hedge}\n"
                )
            reply = self._ask(
                "writer",
                f"{lead}"
                f"Use only these claims and their citation markers:\n{briefs}\n\n"
                f"Return {word_range} words of section body as markdown. No heading "
                "line, the assembler adds it. No references section. Unpack every "
                "bound claim: finding, mechanism, alternative and its cost, then the "
                "limit of the evidence. Do not invent facts. Do not repeat a paragraph. "
                "Every prose paragraph that makes a "
                "factual claim must include one or more of its allowed citation markers. "
                "Every sentence must be entailed by a listed claim. Omit unsupported "
                "background, framing, forecasts, and generalizations. "
                "The gate treats scope, transition, recommendation, and limitation paragraphs "
                "as prose claims too, so every prose paragraph must carry at least one allowed "
                "marker; do not leave an editorial paragraph uncited.",
            )
            usd += reply.usd
            body = section_body(reply.text, heading)
            # A live subagent can return a parent tool receipt, an empty
            # completion, or malformed prose. Preserve the exact pre-gate body
            # locally so a failed citation gate is diagnosable without another
            # provider call. The next successful section overwrites only its
            # own filename.
            if self.runner.name == "deep_agents":
                diagnostics = self.work_dir / "diagnostics"
                diagnostics.mkdir(parents=True, exist_ok=True)
                (diagnostics / f"last-writer-{evidence.slug(heading)}.md").write_text(
                    body, encoding="utf-8"
                )
            body = stages.drop_uncited_prose(body)
            # `assemble` strips em dashes deterministically; `style` is a hard
            # row since #517 follow-up 2, so a writer's em dash must not cost
            # this section an attempt over something `assemble` would have
            # fixed silently anyway. Same normalization, applied here first.
            # This loop skips a heading already in `self.written` (above), so
            # it never runs on the text `stage_trim` (#464, after `write` in
            # `STAGE_ORDER`) has already added a figure mention to; nothing
            # here can undo a mention `trim` persisted.
            body = brief.strip_em_dashes(body)
            # Store first, then gate. A failure drops this section only, so the
            # retry re-asks for it and leaves its neighbours alone.
            stages.write_gate(heading, body, allowed)
            self.written[heading] = body
            self._save_sections()
            try:
                usd += sections.close_section(self, section, body)
            except GateFailed:
                self.written.pop(heading, None)
                self._save_sections()
                raise
        self._save_sections()
        words = sum(len(body.split()) for body in self.written.values())
        return StageResult(
            "write",
            usd=usd,
            artifacts={"sections": len(self.written), "words": words},
            summary=f"{len(self.written)} sections, about {words} words",
        )

    def _save_sections(self) -> Path:
        """Checkpoint the prose written so far.

        Called after every section, not once at the end of the stage. A stage
        that persists only on success makes a mid-stage stop cost the whole
        stage again, which is the opposite of what a cost cap is for.
        """
        path = self.work_dir / "sections.json"
        path.write_text(json.dumps(self.written, indent=2), encoding="utf-8")
        return path

    def stage_revise(self, feedback: str, *, targets: list[str] | None = None) -> StageResult:
        """Rewrite only the sections named by a failed quality gate.

        Re-running a reviewer after it finds prose defects cannot change the
        draft. Keep that maker-checker separation intact: the reviewer names
        the defect, the writer revises bounded prose, and the reviewer grades
        the new text on the next attempt.
        """
        # #452 #465 #412. `feedback` is the reviewer's own free text, and a
        # reviewer that names the run's search host or its retrieval boundary
        # while explaining a defect must not hand that name to the writer.
        feedback = _strip_policy_leak(feedback, self.allowed_domains)
        self._need_written()
        index, _ = stages.numbering(self.ledger)
        # These two rubric rows apply across a draft. A reviewer may name a
        # different example on the second pass, so revising only the first
        # named section creates an oscillating review loop. Rewrite every
        # substantive body once, rather than guessing which mechanism it will
        # mention next.
        # P7, #472: `stage_write` now stamps the abstract last, so it is the
        # one section already checked against the finished body. It still
        # needs the same global terminology and citation repair as every
        # other section here. Limitations is already a caveat-only section.
        if targets is None:
            targets = [heading for heading in self.written if heading.lower() != "limitations"]

        usd = 0.0
        for heading in targets:
            section = next(item for item in self.outline["sections"] if item["heading"] == heading)
            claim_ids = section.get("claim_ids") or []
            if heading.lower() in stages.UNBOUND_SECTIONS:
                claim_ids = [claim.id for claim in self.ledger.claims.values() if claim.usable]
            allowed = sorted(
                {
                    index[source_id]
                    for claim_id in claim_ids
                    if self.ledger.claim(claim_id)
                    for source_id in self.ledger.claim(claim_id).source_ids
                    if source_id in index
                }
            )
            # #517. Same widening `stage_write` applies, so a revise pass can
            # still add a ledger guideline's citation without `write_gate`
            # calling it stray.
            guideline_note, allowed = sections.guideline_brief(
                self.ledger, section, self.topic, index, allowed
            )
            briefs = "\n".join(stages.claim_brief(self.ledger, claim_id, index) for claim_id in claim_ids)
            if guideline_note:
                briefs = f"{briefs}\n{guideline_note}" if briefs else guideline_note
            word_range = _section_word_range(heading, len(claim_ids))
            earlier = []
            for prior_heading, prior_body in self.written.items():
                if prior_heading == heading:
                    break
                earlier.append(f"## {prior_heading}\n{prior_body}")
            earlier_context = "\n\n".join(earlier)
            reply = self._ask(
                "writer",
                f"Revise the existing {heading!r} section of {self.plan['title']!r}.\n\n"
                f"Reviewer feedback to fix:\n{feedback}\n\n"
                f"Current section:\n{self.written[heading]}\n\n"
                f"Use only these claims and their citation markers:\n{briefs}\n\n"
                f"Earlier sections, supplied only to prevent repetition:\n{earlier_context}\n\n"
                f"Return {word_range} words of replacement markdown body. No heading or references. "
                "Preserve factual grounding and citation markers. Where the reviewer asks for a "
                "tradeoff, name a credible alternative and its cost without inventing evidence. "
                "Do not repeat the paper's section list or its abstract in this section. Define every "
                "specialized term before its first use; the abstract must avoid or define terms that "
                "body sections introduce later. Do not reuse a citation for a distinct claim unless the "
                "provided claim brief explicitly supports both claims. Every prose paragraph that makes "
                "a factual claim must include one or more of its allowed citation markers. "
                "Every sentence must be entailed by a listed claim. Unpack mechanism, alternative, "
                "and evidence limit instead of restating the claims. "
                "Do not restate a mechanism already explained in an earlier section. Build on it "
                "with a new implication supported by this section's claims, or omit it. "
                "The gate treats scope, transition, recommendation, and limitation paragraphs "
                "as prose claims too, so every prose paragraph must carry at least one allowed "
                "marker; do not leave an editorial paragraph uncited.",
            )
            usd += reply.usd
            body = section_body(reply.text, heading)
            body = stages.drop_uncited_prose(body)
            # See `stage_write`'s own call: `style` is hard, `assemble` is not
            # the first reader to see this text any more. This stage replaces
            # `self.written[heading]` outright from a fresh reply, so a
            # figure mention `stage_trim` added to the text being replaced is
            # already gone before this line runs; stripping em dashes from
            # the new text does not do that, it only means the new text was
            # never going to carry the old mention either way. #517
            body = brief.strip_em_dashes(body)
            stages.write_gate(heading, body, allowed)
            self.written[heading] = body
            self._save_sections()
            usd += sections.close_section(self, section, body, force=True)
        return StageResult("revise", usd=usd, artifacts={"sections": len(targets)}, summary=f"{len(targets)} sections")

    # -- 7. review ---------------------------------------------------------

    def stage_review(self, extra: str = "") -> StageResult:
        self._need_written()
        self.written = stages.define_acronym_once(
            self.written, "Model Context Protocol", "MCP"
        )
        self._save_sections()
        draft = "\n\n".join(f"## {head}\n\n{body}" for head, body in self.written.items())
        reply = self._ask(
            "reviewer",
            f"Grade this draft against the rubric.\n{extra}\n\n{draft}\n\n"
            'Return JSON: {"failed_rows": [{"row": "...", "note": "..."}], '
            '"score": 0.0 to 1.0}',
        )
        verdict = self._json_reply("reviewer", reply)
        stages.review_gate(verdict)
        return StageResult("review", usd=reply.usd, summary="every rubric row passed")

    # -- 8. assemble -------------------------------------------------------

    def _methods_lines(self) -> list[str]:
        """Methods, Python-written from the run record. No model turn. #478

        Prose, the same shape the SDK twin renders, not a bulleted list. PR
        #535 judge revision, ruling (b): the two ports may not differ in
        the paper's shape for a section Python writes from the same record
        in both. Named hosts and a citation-free process description are
        why `policy_leak`, `caveat_once`, and `cited` all exempt this
        section by name (`_mask_for_policy`, `CAVEAT_EXEMPT_SECTIONS`,
        `PYTHON_WRITTEN_SECTIONS`), not by an incidental list-line rule.
        """
        allowlist_path = self.work_dir / "corpus" / "source_allowlist.json"
        allowlist: dict = {}
        if allowlist_path.exists():
            try:
                allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                allowlist = {}
        briefing_path = self.work_dir / "corpus" / "scout-briefing.json"
        briefing: dict = {}
        if briefing_path.exists():
            try:
                briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                briefing = {}
        # source_allowlist.json is the librarian's own decision; the scout
        # briefing (the E1 field seed) is the fallback for a run, or a
        # phase test, that never reached that stage.
        admitted = list(allowlist.get("admitted") or briefing.get("admitted") or [])
        dropped = list(allowlist.get("dropped") or briefing.get("dropped") or [])
        # PR #535 judge revision F4: "fields searched" names the topic's
        # own research field (biomedical, software, ...), the scout's own
        # classification and the input to `source_policy.seed_for_field`,
        # not the outline's section headings.
        field = str(briefing.get("field") or "").strip()
        retrieved = len(self.ledger.sources)
        admitted_sources = len(self.ledger.bibliography())
        started = (self.state.started_at or "")[:10] or "an unrecorded date"

        lines = [
            f"This paper searched the {field} field for evidence, starting {started}."
            if field
            else f"This paper searched the topic for evidence, starting {started}, "
            "before a field was classified.",
            f"Admitted search hosts, decided once before any paid search ran: "
            f"{', '.join(admitted)}. A host outside this list was not searched, and "
            "a source from it never reached a claim."
            if admitted
            else "Admitted search hosts, decided once before any paid search ran: "
            "the vendor documentation seed. No topic-specific host was proposed.",
            f"Sources retrieved during research: {retrieved}. Sources admitted to "
            "the reference list, after the same host and claim checks every finding "
            f"in this paper passed: {admitted_sources}.",
            # PR #535 judge revision F4: "this run spent N", not "of which N
            # were spent", so the sentence never has to agree a verb with a
            # count that might be exactly one.
            f"The verification cap for this run allows a second opinion on up to "
            f"{self.max_verify} claims. The follow-turn cap allows {self.max_follow} "
            f"secondary claims a look at their own primary study; this run spent "
            f"{self.follow_used}. The counter-evidence cap allows {self.max_counter} "
            f"generalizing claims a search for a contrary finding; this run spent "
            f"{self.counter_used}.",
        ]
        if dropped:
            reasons = "; ".join(
                f"{item.get('host')} ({item.get('why')})" for item in dropped[:5] if item.get("host")
            )
            lines.append(
                f"Hosts excluded during admission, with the reason each was dropped: {reasons}."
                if reasons
                else "No proposed host was excluded during admission; every host cleared the wall."
            )
        else:
            lines.append(
                "No proposed host was excluded during admission; every host cleared the wall."
            )
        if not any(claim.usable and claim.study for claim in self.ledger.claims.values()):
            lines.append("No claim in this run carries a recorded human study.")
        return lines

    def stage_assemble(self, extra: str = "") -> StageResult:
        self._need_written()
        # Recover old checkpoints as well as fresh writer replies.  A process
        # can be stopped between the writer and assembler, so normalizing only
        # in stage_write would leave a persisted duplicate heading untreated.
        normalized = {
            heading: section_body(body, heading) for heading, body in self.written.items()
        }
        if normalized != self.written:
            self.written = normalized
            self._save_sections()
        # #478. Methods never reaches `stage_write` (it names hosts, no
        # model turn), so it is injected here, right before assembly reads
        # `self.written`. Recomputed every call: it derives only from
        # already-persisted run state, so a retry costs nothing to redo.
        self.written["Methods"] = "\n\n".join(self._methods_lines())
        skipped_figures = self._skipped_figures()
        body = stages.assemble(
            self.plan,
            self.outline,
            self.written,
            self.figures,
            self.ledger,
            charts=self._loaded_charts(),
            skipped_figures=skipped_figures,
        )
        # The em dash sweep is mechanical and runs before the gate that checks
        # for em dashes. Arguing with a model about punctuation costs a turn.
        import brief  # noqa: PLC0415

        body = brief.strip_em_dashes(body)
        score = stages.assemble_gate(
            body,
            self.ledger,
            charts=self._loaded_charts(),
            allowed_domains=self.allowed_domains,
            loop_doctrine=self.loop_doctrine,
            # `self.plan`'s sections carry `key_questions`, so `question_heading`
            # can grade a heading against them, not only against "ends in ?". #463.
            outline=self.plan,
            skipped_figures=skipped_figures,
        )
        self.paper_path.write_text(body, encoding="utf-8")
        # A warning is not a failure. Filing both under one key made a short
        # paper look like it had failed a gate, and `publish` reads this file to
        # decide whether the paper may ship.
        (self.work_dir / "gates.json").write_text(
            json.dumps(
                {
                    "passed": score.passed,
                    "failures": list(score.signature()),
                    "warnings": list(score.warnings()),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.state.record("paper", self.paper_path)
        return StageResult(
            "assemble",
            artifacts={"words": len(body.split())},
            summary=f"{len(body.split())} words, every hard gate green",
        )

    # -- 7b. trim ------------------------------------------------------------

    def stage_trim(self, extra: str = "") -> StageResult:
        """The P9 whole-paper pass, now also #464's in-text figure pass.
        Runs once, between diagram and review: `stage_review` (the
        reviewer the creatine run's `no_filler` complaint named) never
        grades a draft that restates the same finding across sections, or
        one that still leaves a placed figure unmentioned. Operates on
        `self.written` directly: assembly proper has not run yet, so there
        is no `paper.md` to read, but a throwaway preview assemble (below)
        gives `Figure N` numbers to work from, since `diagram` now runs
        before this stage (#464's reorder of #476's own STAGE_ORDER move).

        Add no facts; `new_claims` reverts the whole edit if it invents a
        specific the evidence never retrieved, the same defence the SDK
        port's `edit_whole_paper` gives its own body. Never raises: a
        repeat this pass cannot clear is still Python's business at
        `stage_assemble`'s gate, not a reason to fail this stage.
        """
        self._need_written()
        by_lower = {heading.lower(): heading for heading in self.written}
        sections = {lowered: self.written[heading] for lowered, heading in by_lower.items()}
        repeats = paper_check.repeat_shingles(sections)

        # #464. Every figure this attempt will publish, numbered, from a
        # throwaway preview assemble: `self.written` carries no image or
        # caption line of its own, so this is the only way to learn a
        # figure's number before the real `stage_assemble` runs.
        preview = stages.assemble(
            self.plan, self.outline, self.written, self.figures, self.ledger,
            charts=self._loaded_charts(),
        )
        figures_for_trim = paper_check.placed_figures(preview)
        # #464 F5. Every figure already exists from the second attempt on,
        # so gating on "any figure at all" spent a writer turn on every
        # single attempt even when every figure was already named. Gate on
        # the figures that still need a sentence.
        unmentioned = [
            figure
            for figure in figures_for_trim
            if figure.get("section")
            and by_lower.get(figure["section"])
            and not paper_check.mentions_figure(self.written[by_lower[figure["section"]]], figure["number"])
        ]
        # #531. A "Figure N" mention with no figure behind it can survive in
        # `self.written` alone even with nothing else to do this attempt: a
        # figure an earlier pass pointed a section at, that this attempt's
        # own commissioning then dropped. Still worth the pass, to clean it.
        # #464 F5: a valid mention is not dangling, or this never idles.
        valid_numbers = {f["number"] for f in figures_for_trim if f.get("number")}
        dangling = any(
            int(n) not in valid_numbers
            for text in self.written.values()
            for n in paper_check.FIGURE_MENTION.findall(text)
        )

        if not repeats and not unmentioned and not dangling:
            return StageResult("trim", summary="no repeat, no figure")

        before = dict(self.written)
        if self.runner.name == "fixture":
            # A canned reply is keyed by a phrase in the prompt; a
            # whole-paper prompt has no fixed heading to key on. No model,
            # so no paraphrase either: replace the repeat named by each
            # match, in the one section it names, with a back reference.
            # `self.written` is already split per section, so the edit
            # touches only that section's own string, never the rest of
            # the draft.
            usd = 0.0
            for item in repeats:
                source = by_lower.get(item["section"], item["section"])
                for match in item.get("matches") or []:
                    sentence = match.get("sentence") or ""
                    target_heading = by_lower.get(match["section"])
                    if not sentence or target_heading is None:
                        continue
                    text = self.written[target_heading]
                    if sentence not in text:
                        continue
                    reference = f"As stated in {source}, this point also holds here."
                    self.written[target_heading] = text.replace(sentence, reference, 1)
            # #464. One plain sentence naming the figure, appended to the
            # end of its owning section's own prose, for any figure that
            # section does not already mention. Joined onto the last
            # paragraph, not a new one: a standalone sentence would read
            # as an uncited claim, and the paragraph it joins already
            # carries the citation this figure is illustrating.
            for figure in figures_for_trim:
                heading = by_lower.get(figure.get("section") or "")
                number = figure.get("number")
                if not heading or not number:
                    continue
                text = self.written[heading]
                # Word-bounded, so "Figure 1" is not satisfied by a
                # "Figure 12" mention already in the prose. #464 F1.
                if paper_check.mentions_figure(text, number):
                    continue
                sentence = _figure_mention_sentence(number, figure.get("caption") or "")
                self.written[heading] = f"{text.rstrip()} {sentence}"
        else:
            draft = "\n\n".join(f"## {head}\n\n{body}" for head, body in self.written.items())
            figure_note = (
                (
                    "\n\nEach entry below also names a figure the paper already "
                    "carries a caption for: its number, its owning section, and "
                    "its caption. If that section's own prose does not yet name "
                    "the figure, add one short sentence there that does, for "
                    "example \"Figure 2 shows the retry sequence.\" Do not "
                    "renumber a figure or move its image or caption line.\n\n"
                    f"Figures:\n{json.dumps(figures_for_trim, indent=2)}"
                )
                if figures_for_trim
                else ""
            )
            reply = self._ask(
                "writer",
                "This is the whole-paper pass. Each entry below names a "
                "sentence and the other sections that restate it. Keep the "
                "first statement, in full, with its numbers and units, "
                "exactly where it already is. Replace every later "
                "restatement with one sentence of 24 words or fewer that "
                "opens with one of these four phrases and names one of the "
                "paper's own `##` headings: \"As stated in\", \"As noted "
                "in\", \"As shown in\", or \"See\". Do not simply delete a "
                "repeat; a reader needs the pointer, and a paragraph must "
                "never end up as only a citation marker with no sentence. "
                "Add no facts. Keep every heading and every figure line "
                f"exactly as it is. Return the whole edited body.{figure_note}\n\n"
                f"Repeats:\n{json.dumps(repeats, indent=2)}\n\n"
                f"The paper body:\n{draft}",
            )
            usd = reply.usd
            edited = (reply.text or "").strip()
            if edited:
                blocks = paper_check.top_level_sections(edited)
                for lowered, heading in by_lower.items():
                    if lowered in blocks:
                        self.written[heading] = blocks[lowered].strip()

        # #521. Pointing two repeats in the same section at the same
        # source leaves the identical pointer sentence stacked once per
        # repeat, whichever branch above wrote it; a reader needs it once.
        # #531: `self.written[heading]` carries no `##` line of its own, so
        # the paper's real heading set travels in explicitly. A dangling
        # `Figure N` -- a mention an earlier attempt added for a figure
        # this attempt's own commissioning then dropped -- is stripped the
        # same pass. #514, #531.
        real_headings = frozenset(h.lower() for h in self.written)
        for heading in self.written:
            text = paper_check.collapse_repeated_back_references(
                self.written[heading], real_headings
            )
            self.written[heading] = paper_check.drop_dangling_figure_mentions(text, valid_numbers)

        before_blob = "\n\n".join(before.values())
        after_blob = "\n\n".join(self.written.values())
        evidence_blob = "\n".join(
            [claim.text for claim in self.ledger.claims.values()]
            + [f"{src.title} {src.url} {src.text}" for src in self.ledger.bibliography()]
        )
        novel = paper_check.new_claims(before_blob, after_blob)
        invented = [token for token in novel if token.lower() not in evidence_blob.lower()]
        if invented:
            self.written = before
            return StageResult(
                "trim", usd=usd, artifacts={"trimmed": False, "reverted": invented},
                summary="reverted: an invented specific",
            )
        self._save_sections()
        self._restamp_diagram_guard()
        return StageResult(
            "trim", usd=usd, artifacts={"trimmed": True, "reverted": []},
            summary=f"{len(repeats)} repeats cut, {len(figures_for_trim)} figures checked",
        )

    def _restamp_diagram_guard(self) -> None:
        """Re-hash `diagrams.json`'s own `sections_sha` to the section text
        `stage_trim` just finished editing. #464.

        `diagram` now runs before `trim` (the opposite of #476's own
        order), so the guard it wrote reflects the pre-trim draft. Without
        this, a caveat cut or an added figure mention makes a future
        resume's freshly hashed `self.written` no longer match what the
        guard recorded, and a real render budget gets spent redrawing
        figures no section change actually touched.
        """
        path = self.work_dir / "diagrams.json"
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if "sections_sha" not in payload:
            return
        payload["sections_sha"] = _sections_sha(self.written)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _uncited_section_headings(self) -> list[str]:
        """Return exactly the writer bodies that the citation gate rejects."""
        import brief  # noqa: PLC0415

        return [
            heading
            for heading, body in self.written.items()
            # Methods is Python-written, never a writer body to revise.
            # #478
            if heading.lower() not in ("references", "methods")
            and brief.uncited_claims(section_body(body, heading))
        ]

    # -- 9. publish --------------------------------------------------------

    def stage_publish(self, extra: str = "") -> StageResult:
        import publish  # noqa: PLC0415

        result = publish.push(self.work_dir, title=self.plan.get("title", self.topic))
        self.state.record("gist", result.url)
        return StageResult("publish", artifacts={"gist": result.url}, summary=result.url)

    # -- resume helpers ----------------------------------------------------

    def _need_plan(self) -> None:
        if self.plan:
            return
        path = self.work_dir / "plan.json"
        if not path.exists():
            raise GateFailed("there is no plan.json to work from.", ("no_plan",))
        self.plan = stages.normalize_plan(json.loads(path.read_text(encoding="utf-8")))

    def _need_ledger(self) -> None:
        if not self.ledger.claims:
            self.ledger = evidence.Ledger(self.work_dir / "evidence").load()
        if not self.ledger.claims:
            raise GateFailed("there is no evidence to work from.", ("no_evidence",))

    def _need_outline(self) -> None:
        self._need_plan()
        self._need_ledger()
        if self.outline:
            return
        path = self.work_dir / "outline.json"
        if not path.exists():
            raise GateFailed("there is no outline.json to work from.", ("no_outline",))
        self.outline = json.loads(path.read_text(encoding="utf-8"))

    def _need_written(self) -> None:
        self._need_outline()
        if not self.written:
            path = self.work_dir / "sections.json"
            if path.exists():
                self.written = json.loads(path.read_text(encoding="utf-8"))
        if not self.written:
            raise GateFailed("no section was written.", ("no_sections",))
        if not self.figures and self.figure_dir.is_dir():
            self.figures, _ = stages.render_figures(
                self.diagram_src, self.figure_dir, self.topic, theme_name=self.theme
            )

    def _loaded_charts(self) -> list:
        if self.charts:
            return self.charts
        path = self.work_dir / "charts.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        self.charts = [item for item in payload.get("charts") or [] if item.get("path")]
        return self.charts

    def _skipped_charts(self) -> list[dict]:
        """Every skipped chart, `{"name", "section", "reason"}`, section-
        owned.

        An older `charts.json` recorded a bare name list (`["a-chart"]`,
        pre #464). That still loads: a bare name becomes `reason: "no
        data"` (the only reason this port's chart stage ever logs) with an
        empty `section`, so `assemble` still has a name and a reason to
        write, only no section to own it.
        """
        path = self.work_dir / "charts.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        out = []
        for item in payload.get("skipped") or []:
            if isinstance(item, dict):
                out.append(
                    {
                        "name": str(item.get("name") or ""),
                        "section": str(item.get("section") or ""),
                        "reason": str(item.get("reason") or "no data"),
                    }
                )
            else:
                out.append({"name": str(item), "section": "", "reason": "no data"})
        return out

    def _skipped_diagrams(self) -> list[dict]:
        """Every diagram a live image backend failed to render, `{"name",
        "section", "reason"}`. #386, #464, #531.

        Only the #531 backend-failure case, named by `stage_diagram`'s own
        `reason` field (`BACKEND_FAILURE_MARK` prefixed). The renderer
        being absent altogether is not a skip worth narrating on every
        offline and CI page, and a claims-mismatch drop is E7's own
        territory: it already strips the figure's reference from the
        outline before assembly, so there is no dangling mention to
        explain here.
        """
        path = self.work_dir / "diagrams.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        out = []
        for item in payload.get("figures") or []:
            reason = str(item.get("reason") or "")
            if not reason.startswith(stages.BACKEND_FAILURE_MARK):
                continue
            out.append(
                {
                    "name": str(item.get("name") or ""),
                    "section": str(item.get("section") or ""),
                    "reason": reason,
                }
            )
        return out

    def _skipped_figures(self) -> list[dict]:
        """Every named skip on the page: a chart Python refused, and a
        diagram a live image backend failed to render. #386, #464, #531.
        """
        return self._skipped_charts() + self._skipped_diagrams()


FENCE = re.compile(r"\A```[\w]*\n(.*?)\n?```\Z", re.S)


def _strip_fence(text: str) -> str:
    """Diagram source, without the fence a model adds however often you ask."""
    match = FENCE.match(text.strip())
    return (match.group(1) if match else text).strip() + "\n"


def _figure_mention_sentence(number: int, caption: str) -> str:
    """A plain sentence naming a figure, distinct enough from another
    figure's own mention to never itself become a `caveat_once` repeat.

    #464. `WORD` (the shingle tokenizer `repeat_shingles` uses) drops a
    bare digit, so "Figure 1 illustrates this point." and "Figure 2
    illustrates this point." shingle identically once the number is gone
    and Jaccard-match each other as a restatement. A few words of the
    figure's own caption is content two different figures do not share.
    Copied from the SDK port's `turns.py`, not imported.
    """
    gist = " ".join((caption or "").split()[:6]).rstrip(",.:;")
    return f"Figure {number} shows {gist}." if gist else f"Figure {number} illustrates this point."


def _sections_sha(written: dict[str, str]) -> str:
    """A digest of every section body, in a stable (heading-sorted) order.

    `diagram` sits after `write` in `STAGE_ORDER` (#476) and commissions a
    figure from the claims the section it belongs to actually landed. A
    figure is not cheap enough to redraw every time the harness resumes into
    an unchanged paper; this is the guard `stage_diagram` checks, recorded in
    `diagrams.json`, before it spends a single diagrammer turn.
    """
    parts = [written[heading] for heading in sorted(written)]
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def _paper_ledger(work_dir: Path) -> dict:
    path = Path(work_dir) / "paper_ledger.json"
    if not path.exists():
        return {"entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": []}
    if isinstance(payload, list):
        return {"entries": payload}
    return payload


def build(
    topic: str,
    *,
    backend_name: str = "fixture",
    work_root: Path | str | None = None,
    fixture_dir: Path | str | None = None,
    brain: Path | None = None,
    debug: bool = False,
    **kwargs,
) -> Paper:
    """Wire a run from the environment the attendee actually has."""
    fixtures = Path(fixture_dir) if fixture_dir else HERE / "fixtures" / "paper"
    root = Path(work_root) if work_root else DEFAULT_WORK
    work_dir = root / evidence.slug(topic)

    if backend_name == "fixture":
        backend: research.Backend = research.FixtureBackend(fixtures / "research.json")
        docs: research.Backend | None = None
        runner: Runner = FixtureRunner(fixtures / "replies.json")
        search_budget = None
    else:
        backend = research.choose(fixture=fixtures / "research.json")
        docs = research.Context7Backend()
        search_budget = research.Budget(
            max_usd=float(kwargs.get("max_usd", DEFAULT_MAX_USD)), max_calls=DEFAULT_SEARCH_CALLS
        )
        runner = DeepAgentsRunner(
            _agents(
                brain, work_dir, backend=backend, docs_backend=docs, budget=search_budget, debug=debug
            ),
            debug=debug,
        )

    return Paper(
        topic=topic,
        runner=runner,
        backend=backend,
        docs_backend=docs,
        search_budget=search_budget,
        work_dir=work_dir,
        brains=[brain] if brain is not None else [],
        **kwargs,
    )


def _agents(
    brain: Path | None,
    work_dir: Path,
    *,
    backend: research.Backend,
    docs_backend: research.Backend | None,
    budget: research.Budget,
    debug: bool = False,
):
    """The live role graphs. Needs `deepagents`, which nothing else here does."""
    import roles as deep  # noqa: PLC0415

    return deep.build_paper_agents(
        None,
        loop="paper",
        backend=backend,
        docs_backend=docs_backend,
        budget=budget,
        repo=work_dir,
        brain=brain if brain and Path(brain).is_dir() else None,
        debug=debug,
    )
