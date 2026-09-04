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
import json
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import evidence
import gates
import outline as outlines
import research
import sections
import stages
import state as pstate
from stages import GateFailed, StageResult

HERE = Path(__file__).resolve().parent
DEFAULT_WORK = HERE / "work" / "paper"
DEFAULT_BRAIN = HERE / ".." / ".." / ".." / "loop_eng_2nd_brain" / "knowledge"

DEFAULT_MAX_USD = 12.0
DEFAULT_STAGE_ATTEMPTS = 3
DEFAULT_SEARCH_CALLS = 36

DONE, COST, MAX_TURNS = "done", "cost", "max turns"


def _section_word_range(heading: str, claim_count: int) -> str:
    """How long a section should be. The Saturday brief is already short."""
    name = heading.strip().lower()
    if name == "abstract":
        return "120 to 180"
    if name == "limitations":
        return "150 to 250"
    if claim_count < 3:
        return "400 to 800"
    return "700 to 1200"


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
    attempts: int = DEFAULT_STAGE_ATTEMPTS
    theme: str = "spillwave-light"
    publish: bool = False
    quiet: bool = False
    brains: list = field(default_factory=list)
    ingest_brain: Path | None = None
    require_approval: bool = False
    resume: bool = False

    state: pstate.PaperState = field(init=False)
    ledger: evidence.Ledger = field(init=False)
    plan: dict = field(default_factory=dict, init=False)
    outline: dict = field(default_factory=dict, init=False)
    written: dict = field(default_factory=dict, init=False)
    figures: list = field(default_factory=list, init=False)
    charts: list = field(default_factory=list, init=False)
    budget: research.Budget = field(init=False)
    # Diagram names the complexity gate rejected, so a retry redraws only those.
    _redraw: set = field(default_factory=set, init=False)
    # The most expensive call seen per role. The budget check reads it as the
    # headroom the next call of that kind is likely to need.
    _worst: dict = field(default_factory=dict, init=False)

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
        with _heartbeat(role, self.state.current_stage, started, self.quiet):
            reply = self.runner.ask(role, prompt)
        elapsed = time.monotonic() - started

        self.state.spend(reply.usd)
        self._worst[role] = max(self._worst.get(role, 0.0), reply.usd)
        self._record_turn(role, reply, elapsed, len(prompt))
        return reply

    def _record_turn(self, role: str, reply: Reply, elapsed: float, prompt_chars: int) -> None:
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
        extra = ""

        for attempt in range(1, self.attempts + 1):
            self.state.mark_in_progress(name)
            self.state.save()
            try:
                result = handler(extra)
            except BudgetSpent as spent:
                self.state.mark_failed(name, str(spent))
                self.state.save()
                return self._escalate(name, COST, str(spent))
            except GateFailed as failure:
                signature = failure.signature
                decision = gates.decide(
                    passed=False,
                    iteration=attempt,
                    budget=self.attempts,
                    signature=signature,
                    previous_signature=previous,
                    usd_left=max(0.0, self.max_usd - self.state.total_cost_usd),
                )
                self.say(f"  {name:<10} attempt {attempt} failed: {', '.join(signature)}")
                if decision.stop:
                    self.state.mark_failed(name, str(failure))
                    self.state.save()
                    return self._escalate(name, decision.reason, str(failure))
                previous = signature
                extra = gates.retry_instruction(decision, list(signature)) + "\n" + str(failure)
                if name == "review":
                    revised = self.stage_revise(extra)
                    self.say(f"  revise     {revised.summary}")
                elif name == "assemble" and "cited" in signature:
                    # This gate names a mechanical, local defect.  Send only
                    # the offending sections back to the maker; a full rewrite
                    # would risk the reviewer-approved prose just to add a
                    # traceable source marker.
                    targets = self._uncited_section_headings()
                    revised = self.stage_revise(extra, targets=targets or None)
                    self.say(f"  revise     {revised.summary}")
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
        return StageResult(
            "corpus",
            artifacts={"corpus/brain-pack.json": str(dest / "brain-pack.json")},
            summary=f"{packed.get('hits') or 0} hits, thin={packed.get('corpus_thin')}",
        )

    def stage_plan(self, extra: str = "") -> StageResult:
        path = self.work_dir / "plan.json"
        usd = 0.0
        if path.exists() and not extra:
            self.plan = json.loads(path.read_text(encoding="utf-8"))
        else:
            reply = self._ask(
                "planner",
                f"Topic: {self.topic}\n\nWrite plan.json for a technical white paper "
                f"on this topic.\n{extra}",
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
        stages.plan_gate(self.plan)
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

    def _approve_outline(self) -> float:
        """Validate, judge, and stamp the outline. `--approve` stops before research."""
        dest = self.work_dir / "outline.json"
        judged_path = self.work_dir / "outline-judged.json"
        stamped = self.work_dir / "outline.approved.json"
        usd = 0.0
        if dest.exists():
            drafted = json.loads(dest.read_text(encoding="utf-8"))
        else:
            drafted = outlines.outline_from_plan(self.plan)
        errors = outlines.validate(drafted, word_target_total=drafted.get("word_target_total") or 2000)
        if errors:
            raise GateFailed(outlines.retry_note(errors), ("outline",))
        dest.write_text(json.dumps(drafted, indent=2) + "\n", encoding="utf-8")
        (self.work_dir / "outline.md").write_text(outlines.to_markdown(drafted), encoding="utf-8")

        if not judged_path.exists() or self.resume:
            reply = self._ask(
                "outline_judge",
                "Grade this outline against logical flow, completeness, titles, "
                "and corpus_fit. Do not re-litigate Python's validator.\n"
                + json.dumps(drafted, indent=2)[:8000],
            )
            usd = reply.usd
            verdict = self._json_reply("outline_judge", reply)
            (self.work_dir / "outline-verdict.json").write_text(
                json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
            )
            if not verdict.get("passed"):
                raise GateFailed(
                    "the outline judge rejected the outline: "
                    + (verdict.get("summary") or "failed"),
                    outlines.judge_signature(verdict),
                )
            judged_path.write_text(json.dumps(drafted, indent=2) + "\n", encoding="utf-8")

        if self.require_approval and not self.resume:
            raise AwaitingApproval(self.work_dir / "outline.md")

        approved_by = "operator" if self.resume else "judge"
        stamped.write_text(
            json.dumps(outlines.stamp(drafted, approved_by=approved_by), indent=2) + "\n",
            encoding="utf-8",
        )
        return usd

    # -- 2. search ---------------------------------------------------------

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
                if self.runner.name == "deep_agents"
                else None
            )
            if repository_report is not None:
                stages.record_findings(self.ledger, question, repository_report)
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
            stages.record_findings(self.ledger, question, self._json_reply("researcher", reply))
            # Persist per question. A stop between questions must not discard
            # the answers this run already paid for.
            self.ledger.write()
        stages.search_gate(self.ledger, self.plan)
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
            '"corroborate_status": "agreed|disagreed|not_found", "quote": "..."}]}',
        )
        counts = stages.apply_verification(
            self.ledger,
            stages.resolve_placeholders(self._json_reply("verifier", reply), self.ledger),
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
            f"Sections the plan asked for: {', '.join(self.plan['sections'])}\n"
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
        self._need_plan()
        planned = self.plan.get("diagrams") or []
        if not planned:
            self.state.mark_skipped("diagram", "the plan asked for no figures")
            return StageResult("diagram", summary="no figures planned")

        self.diagram_src.mkdir(parents=True, exist_ok=True)
        usd = 0.0
        for figure in planned:
            name = evidence.slug(figure["name"])
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
            reply = self._ask(
                "diagrammer",
                f"Draw a {figure['kind']} diagram named {name}.\n"
                f"It must show: {figure['shows']}{order_instruction}\n"
                f"Paper topic: {self.topic}\n{extra}\n\n"
                "Return only the diagram source. No fences, no commentary.",
            )
            usd += reply.usd
            # A scoped Deep Agents diagrammer writes the requested source.
            # Its final message may only acknowledge that tool call. Preserve
            # the file in that case; answer-only and fixture runners still
            # supply source in the reply for Python to checkpoint.
            if not target.exists():
                target.write_text(_strip_fence(reply.text), encoding="utf-8")

        semantic_complaints = []
        for figure in planned:
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
        self._redraw = {Path(c.split(":", 1)[0]).stem for c in complaints}
        stages.diagram_gate(self.figures, complaints, planned)
        for complaint in complaints:
            self.say(f"    note: {complaint}")
        accepted = sum(1 for figure in self.figures if figure.best is not None)
        return StageResult(
            "diagram",
            usd=usd,
            artifacts={"figures": len(self.figures), "accepted": accepted},
            summary=f"{accepted} judged imagen-diagrams PNGs",
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
                skipped.append(name)
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
        # `write` can be interrupted between sections. Load its artifact before
        # deciding what remains so a resumed process preserves every accepted
        # section instead of spending another turn to replace it.
        if not self.written:
            path = self.work_dir / "sections.json"
            if path.exists():
                self.written = json.loads(path.read_text(encoding="utf-8"))
        index, _ = stages.numbering(self.ledger)
        usd = 0.0
        for section in self.outline["sections"]:
            heading = section["heading"]
            if heading.lower() == "references":
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
            briefs = "\n".join(stages.claim_brief(self.ledger, cid, index) for cid in claim_ids)
            word_range = _section_word_range(heading, len(claim_ids))
            reply = self._ask(
                "writer",
                f"Write the {heading!r} section of {self.plan['title']!r}.\n"
                f"Purpose: {section.get('purpose', '')}\n"
                f"Audience: {self.plan['audience']}\n{extra}\n\n"
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
        self._need_written()
        index, _ = stages.numbering(self.ledger)
        # These two rubric rows apply across a draft. A reviewer may name a
        # different example on the second pass, so revising only the first
        # named section creates an oscillating review loop. Rewrite every
        # substantive body once, rather than guessing which mechanism it will
        # mention next.
        # The abstract appears first, so it cannot introduce a term that its
        # body section defines later. Limitations is already a caveat-only
        # section, but every other section, including the abstract, needs the
        # same global terminology and citation repair.
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
            briefs = "\n".join(stages.claim_brief(self.ledger, claim_id, index) for claim_id in claim_ids)
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
            'Return JSON: {"failed_rows": ["..."], "notes": ["..."]}',
        )
        verdict = self._json_reply("reviewer", reply)
        stages.review_gate(verdict)
        return StageResult("review", usd=reply.usd, summary="every rubric row passed")

    # -- 8. assemble -------------------------------------------------------

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
        body = stages.assemble(
            self.plan, self.outline, self.written, self.figures, self.ledger, charts=self._loaded_charts()
        )
        # The em dash sweep is mechanical and runs before the gate that checks
        # for em dashes. Arguing with a model about punctuation costs a turn.
        import brief  # noqa: PLC0415

        body = brief.strip_em_dashes(body)
        score = stages.assemble_gate(body, self.ledger, charts=self._loaded_charts())
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

    def _uncited_section_headings(self) -> list[str]:
        """Return exactly the writer bodies that the citation gate rejects."""
        import brief  # noqa: PLC0415

        return [
            heading
            for heading, body in self.written.items()
            if heading.lower() != "references" and brief.uncited_claims(section_body(body, heading))
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


FENCE = re.compile(r"\A```[\w]*\n(.*?)\n?```\Z", re.S)


def _strip_fence(text: str) -> str:
    """Diagram source, without the fence a model adds however often you ask."""
    match = FENCE.match(text.strip())
    return (match.group(1) if match else text).strip() + "\n"


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
