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

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import evidence
import gates
import research
import stages
import state as pstate
from stages import GateFailed, StageResult

HERE = Path(__file__).resolve().parent
DEFAULT_WORK = HERE / "work" / "paper"
DEFAULT_BRAIN = HERE / ".." / ".." / ".." / "loop_eng_2nd_brain" / "knowledge"

DEFAULT_MAX_USD = 5.0
DEFAULT_STAGE_ATTEMPTS = 3
DEFAULT_SEARCH_CALLS = 24

DONE, COST, MAX_TURNS = "done", "cost", "max turns"


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
    """One answer from a role. `usd` is what it cost, and zero means unknown."""

    text: str = ""
    data: dict | None = None
    usd: float = 0.0

    def json(self) -> dict:
        return self.data if self.data is not None else stages.parse_json(self.text)


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

    def __init__(self, agent):
        self.agent = agent

    def ask(self, role: str, prompt: str) -> Reply:
        import adapter  # noqa: PLC0415

        instruction = (
            f"Delegate this to the {role.replace('_', '-')} subagent. "
            f"Return its answer and nothing else.\n\n{prompt}"
        )
        result = self.agent.invoke({"messages": [{"role": "user", "content": instruction}]})
        return Reply(text=adapter.last_ai_text(result), usd=adapter.last_usd(result))


@dataclass
class Paper:
    """One run. Owns the budget, the state file, and the order of the stages."""

    topic: str
    runner: Runner
    backend: research.Backend
    work_dir: Path
    docs_backend: research.Backend | None = None
    max_usd: float = DEFAULT_MAX_USD
    max_verify: int = stages.MAX_VERIFY_CLAIMS
    attempts: int = DEFAULT_STAGE_ATTEMPTS
    theme: str = "spillwave-light"
    polish: bool = True
    publish: bool = False
    quiet: bool = False

    state: pstate.PaperState = field(init=False)
    ledger: evidence.Ledger = field(init=False)
    plan: dict = field(default_factory=dict, init=False)
    outline: dict = field(default_factory=dict, init=False)
    written: dict = field(default_factory=dict, init=False)
    figures: list = field(default_factory=list, init=False)
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
        self.budget = research.Budget(max_usd=self.max_usd, max_calls=DEFAULT_SEARCH_CALLS)
        self.budget.spent_usd = self.state.total_cost_usd

    # -- plumbing ----------------------------------------------------------

    def say(self, line: str) -> None:
        if not self.quiet:
            print(line)

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
        reply = self.runner.ask(role, prompt)
        self.state.spend(reply.usd)
        self._worst[role] = max(self._worst.get(role, 0.0), reply.usd)
        self.budget.spent_usd = self.state.total_cost_usd
        return reply

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

            decision = self._run_stage(name)
            if decision is not None:
                return decision

        self.state.save()
        stop = check_stop(done=True, spent_usd=self.state.total_cost_usd, max_usd=self.max_usd)
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
            self.plan = reply.json()
            usd = reply.usd
        self.plan = stages.normalize_plan(self.plan)
        stages.plan_gate(self.plan)
        path.write_text(json.dumps(self.plan, indent=2), encoding="utf-8")
        self.state.record("plan", path)
        return StageResult(
            "plan",
            usd=usd,
            artifacts={"questions": len(self.plan["questions"])},
            summary=f"{len(self.plan['questions'])} questions, "
            f"{len(self.plan['diagrams'])} figures planned",
        )

    # -- 2. search ---------------------------------------------------------

    def stage_search(self, extra: str = "") -> StageResult:
        self._need_plan()
        usd = 0.0
        for question in self.plan["questions"]:
            if any(f.subject == question["subject"] for f in self.ledger.findings.values()):
                continue
            try:
                self.budget.charge(self.backend.cost_per_call)
            except research.BudgetExceeded as exc:
                raise GateFailed(f"the search budget is spent. {exc}", ("search_budget",)) from exc
            reply = self._ask(
                "researcher",
                f"Question: {question['question']}\n"
                f"What answers it: {question['check']}\n{extra}\n\n"
                "Search, then return JSON: "
                '{"answer": "...", "sources": [{"title": "...", "url": "...", '
                '"vendor": "...", "quote": "..."}], '
                '"claims": [{"text": "...", "confidence": 0.8, "source_urls": ["..."]}]}',
            )
            usd += reply.usd
            stages.record_findings(self.ledger, question, reply.json())
            # Persist per question. A stop between questions must not discard
            # the answers this run already paid for.
            self.ledger.write()
        stages.search_gate(self.ledger, self.plan)
        self.ledger.write()
        return StageResult(
            "search",
            usd=usd,
            artifacts={"claims": len(self.ledger.claims), "sources": len(self.ledger.sources)},
            summary=f"{len(self.ledger.claims)} claims from {len(self.ledger.sources)} sources",
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
            self.ledger, stages.resolve_placeholders(reply.json(), self.ledger)
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
        self.outline = stages.resolve_placeholders(reply.json(), self.ledger)
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
            reply = self._ask(
                "diagrammer",
                f"Draw a {figure['kind']} diagram named {name}.\n"
                f"It must show: {figure['shows']}\n"
                f"Paper topic: {self.topic}\n{extra}\n\n"
                "Return only the diagram source. No fences, no commentary.",
            )
            usd += reply.usd
            target.write_text(_strip_fence(reply.text), encoding="utf-8")

        try:
            self.figures, complaints = stages.render_figures(
                self.diagram_src,
                self.figure_dir,
                self.topic,
                theme_name=self.theme,
                polish=self.polish,
            )
        except stages.RendererMissing as missing:
            # The paper ships without figures rather than not at all. Nothing in
            # `paper_check` requires a figure, and blocking every attendee who
            # has no Java would be a worse answer than saying so out loud.
            self.figures = []
            self.say(f"    {missing}")
            return StageResult(
                "diagram",
                usd=usd,
                artifacts={"figures": 0, "renderer": "missing"},
                summary=f"no renderer on this machine, {len(planned)} figures skipped",
            )
        self._redraw = {Path(c.split(":", 1)[0]).stem for c in complaints}
        stages.diagram_gate(self.figures, complaints, planned)
        for complaint in complaints:
            self.say(f"    note: {complaint}")
        polished = sum(1 for figure in self.figures if figure.polished)
        return StageResult(
            "diagram",
            usd=usd,
            artifacts={"figures": len(self.figures), "polished": polished},
            summary=f"{len(self.figures)} figures, {polished} polished",
        )

    # -- 6. write ----------------------------------------------------------

    def stage_write(self, extra: str = "") -> StageResult:
        self._need_outline()
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
            reply = self._ask(
                "writer",
                f"Write the {heading!r} section of {self.plan['title']!r}.\n"
                f"Purpose: {section.get('purpose', '')}\n"
                f"Audience: {self.plan['audience']}\n{extra}\n\n"
                f"Use only these claims and their citation markers:\n{briefs}\n\n"
                "Return the section body as markdown. No heading line, the "
                "assembler adds it. No references section.",
            )
            usd += reply.usd
            body = reply.text.strip()
            # Store first, then gate. A failure drops this section only, so the
            # retry re-asks for it and leaves its neighbours alone.
            stages.write_gate(heading, body, allowed)
            self.written[heading] = body
            self._save_sections()
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

    # -- 7. review ---------------------------------------------------------

    def stage_review(self, extra: str = "") -> StageResult:
        self._need_written()
        draft = "\n\n".join(f"## {head}\n\n{body}" for head, body in self.written.items())
        reply = self._ask(
            "reviewer",
            f"Grade this draft against the rubric.\n{extra}\n\n{draft}\n\n"
            'Return JSON: {"failed_rows": ["..."], "notes": ["..."]}',
        )
        verdict = reply.json()
        stages.review_gate(verdict)
        return StageResult("review", usd=reply.usd, summary="every rubric row passed")

    # -- 8. assemble -------------------------------------------------------

    def stage_assemble(self, extra: str = "") -> StageResult:
        self._need_written()
        body = stages.assemble(self.plan, self.outline, self.written, self.figures, self.ledger)
        # The em dash sweep is mechanical and runs before the gate that checks
        # for em dashes. Arguing with a model about punctuation costs a turn.
        import brief  # noqa: PLC0415

        body = brief.strip_em_dashes(body)
        score = stages.assemble_gate(body, self.ledger)
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
                self.diagram_src, self.figure_dir, self.topic, theme_name=self.theme, polish=False
            )


FENCE = re.compile(r"\A```[\w]*\n(.*?)\n?```\Z", re.S)


def _strip_fence(text: str) -> str:
    """Diagram source, without the fence a model adds however often you ask."""
    match = FENCE.match(text.strip())
    return (match.group(1) if match else text).strip() + "\n"


def build(
    topic: str,
    *,
    backend_name: str = "fixture",
    work_root: Path | str | None = None,
    fixture_dir: Path | str | None = None,
    brain: Path | None = None,
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
    else:
        backend = research.choose(fixture=fixtures / "research.json")
        docs = research.Context7Backend()
        runner = DeepAgentsRunner(_agent(brain, work_dir))

    return Paper(
        topic=topic, runner=runner, backend=backend, docs_backend=docs, work_dir=work_dir, **kwargs
    )


def _agent(brain: Path | None, work_dir: Path):
    """The live graph. Needs `deepagents`, which nothing else in this file does."""
    import roles as deep  # noqa: PLC0415

    fixtures = HERE / "fixtures" / "paper" / "research.json"
    return deep.build_agent(
        None,
        loop="paper",
        backend=research.choose(fixture=fixtures),
        docs_backend=research.Context7Backend(),
        repo=work_dir,
        brain=brain if brain and Path(brain).is_dir() else None,
    )
