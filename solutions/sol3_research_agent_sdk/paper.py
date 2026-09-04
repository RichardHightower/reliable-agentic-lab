"""The white paper driver. Python owns the phases, the budget, and the exits.

The list is the dispatch order and the number is only a state key, which is
what lets a phase slot in later without renumbering the run records that
already exist on disk.

    0 corpus_pack read the configured brains   -> corpus/brain-pack.md
    1 outline     two-level outline, judged -> outline.approved.json
    2 sections    per-section research/write -> sections/*.md, paper_ledger.json
    4 diagram     figures, rendered         -> diagrams.json
    3 charts      data charts, Python-rendered -> charts.json
    5 write       retry rewrite             -> sections/*.md
    6 assemble    stitch and reference      -> paper.md
    7 check       deterministic rows        -> check.json
    8 review      the judge, on what is left-> review.json
    8b edit       flow only, add no facts   -> sections/*.md (once)
    9 publish     a private gist, on request-> gist.json

The linear phases run once. Phases 5 to 8 are the retry cycle, because the
only thing worth redoing on a failed check is the writing. Re-running the
research because a paragraph lost its citation marker buys a bill, not a
better paper. The edit pass runs once after the first green check and
re-enters the cycle.

Every phase writes a new named file and no phase mutates another's output. That
one rule is what makes `--resume` need no bookkeeping: a phase whose file exists
is a phase that already ran.

A stop condition trusted to a model's own judgment is a stop condition a model
can talk itself past. `check` is arithmetic, `review` is the judge, and the run
ends only when both agree, or when a budget does.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import adapter
import checks
import charts
import corpus
import diagrams
import gates
import outline as outlines
import publish as publisher
import research
import rkc
import sections as section_loop
from turns import Escalate, TurnFailed, slugify

FOLDER = Path(__file__).resolve().parent

# The second brain is a sibling repo, not part of this one. It is read-only
# prior art, and a run must not need it. One definition, in `corpus`, or the
# two drift and a run reads a different brain than the one it reports.
BRAIN = corpus.DEFAULT_BRAIN

DEFAULT_AREA = "loop-engineering"
MAX_ITERATIONS = 3
MAX_PRIOR_ART_HITS = 12

# A ceiling on the plan, not on the planner's ambition. Asked to plan a paper on
# a broad topic it will return thirty good questions, and thirty questions is
# thirty research turns plus thirty verification turns. The cap is what keeps a
# well-planned paper from being an expensive one.
MAX_QUESTIONS = 12
MAX_DIAGRAMS = 4
MAX_CLAIMS = 40
MAX_WORDS = 2000
OUTLINE_JUDGE_ROUNDS = 3

# A ceiling on verification, for the same reason. Four good questions produced
# a hundred and eleven claims on one live run, and every claim is a turn. The
# cap decides how many get a second opinion; the rest stay `unverified`, which
# the writer states qualitatively.

# Which claims get the budget when there is not enough for all of them. A claim
# with a number, a version, or a date is the one most worth a second look: it is
# the kind that goes stale, and the kind a reader can check and find wrong.
NUMERIC = re.compile(r"\d")


def _section_instruction(section: dict, notes: str = "") -> str:
    """How long a section should be. The outline's word_target is the contract."""
    target = section.get("word_target")
    length_note = (
        "Unpack every bound claim: finding, mechanism, alternative and its cost, "
        "then the limit of the evidence. Do not invent facts. Do not repeat a paragraph."
    )
    if target:
        length_note = (
            f"Return about {target} words of section body (0.6 to 1.25 times that). "
            + length_note
        )
    if notes:
        return f"{length_note}\n\n{notes}"
    return length_note


class RunFailed(RuntimeError):
    """A person has to look at this. The run stopped."""


class AwaitingApproval(RuntimeError):
    """The outline passed the judge and is waiting for `--resume`.

    Exit code 3. Not a failure. The operator reads `outline.md`, edits
    `outline.json` if needed, and continues.
    """

    exit_code = 3

    def __init__(self, path: Path):
        self.path = Path(path)
        super().__init__(f"outline awaiting approval: {self.path}")


@dataclass
class State:
    """What survives a crash, and what `--resume` reads.

    Written with a temp file and `os.replace`, so a kill between the open and
    the write leaves the previous state rather than a truncated one.
    """

    topic: str = ""
    slug: str = ""
    started_at: str = ""
    total_usd: float = 0.0
    turns: int = 0
    iteration: int = 0
    previous_signature: list[str] | None = None
    phases: dict[str, dict] = field(default_factory=dict)
    # Live position. A run killed mid-phase leaves these pointing at the turn
    # that was in flight, instead of at the last phase that finished cleanly.
    phase: str = ""
    role: str = ""
    last_turn: dict | None = None
    query_timeout_s: int = 0

    @staticmethod
    def path(work_dir: Path) -> Path:
        return Path(work_dir) / ".harness" / "state.json"

    @classmethod
    def load_or_new(cls, work_dir: Path, topic: str) -> State:
        path = cls.path(work_dir)
        if path.exists():
            return cls(**json.loads(path.read_text(encoding="utf-8")))
        return cls(
            topic=topic,
            slug=slugify(topic),
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def save(self, work_dir: Path) -> None:
        path = self.path(work_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(f".json.tmp.{os.getpid()}")
        try:
            temp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
            os.replace(temp, path)
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def mark(self, name: str, status: str, **meta) -> None:
        self.phases[name] = {
            "status": status,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **meta,
        }


@dataclass
class Run:
    """One paper, being built."""

    topic: str
    work_dir: Path
    turns: object
    state: State
    area: str = DEFAULT_AREA
    max_usd: float | None = None
    max_iterations: int = MAX_ITERATIONS
    max_questions: int = MAX_QUESTIONS
    max_diagrams: int = MAX_DIAGRAMS
    max_claims: int = MAX_CLAIMS
    word_target_total: int = MAX_WORDS
    theme: str = diagrams.DEFAULT_THEME
    brain: Path | None = BRAIN
    brains: list = field(default_factory=list)
    corpus_subjects: list | None = None
    brief: str = ""
    should_publish: bool = False
    require_approval: bool = False
    resume: bool = False
    ingest_brain: Path | None = None
    # The workshop entry point enables these hard gates.  Keeping synthetic
    # phase tests opt-in lets them exercise one phase at a time without having
    # to manufacture the whole loop-control paper contract.
    enforce_research_policy: bool = False
    enforce_loop_doctrine: bool = False
    log: object = print

    # -- files -------------------------------------------------------------

    def file(self, name: str) -> Path:
        return Path(self.work_dir) / name

    def corpus_roots(self) -> list[Path]:
        if self.brains:
            return [Path(path) for path in self.brains]
        if self.brain:
            return [Path(self.brain)]
        return []

    def read_json(self, name: str) -> dict:
        return json.loads(self.file(name).read_text(encoding="utf-8"))

    def write_json(self, name: str, payload: dict) -> None:
        path = self.file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def spend(self, usd: float | None, **detail) -> None:
        """Record one turn: the running total, the state file, and the turn log.

        Every model call in this port funnels through here. Flushing the state
        on the phase boundary instead left a ten-minute outline phase looking
        dead from outside the process, and a killed run reporting the phase
        before the one it died in.
        """
        self.state.total_usd += float(usd or 0.0)
        self.state.turns += 1
        row = {
            "turn": self.state.turns,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "phase": self.state.phase,
            "iteration": self.state.iteration,
            # Null, never zero. A zero here reads as a free turn and hides a
            # cost field the runtime never reported.
            "usd": None if usd is None else round(float(usd), 6),
            "total_usd": round(self.state.total_usd, 6),
            **detail,
        }
        self.state.role = str(detail.get("role") or "")
        self.state.last_turn = row
        self.append_turn(row)
        try:
            self.state.save(self.work_dir)
        except OSError:
            pass  # telemetry never fails a run

    def append_turn(self, row: dict) -> None:
        """One JSON object per line, append only, beside the state file."""
        path = Path(self.work_dir) / ".harness" / "turns.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        except OSError:
            pass  # telemetry never fails a run

    def exhausted(self) -> str | None:
        if self.max_usd is not None and self.state.total_usd >= self.max_usd:
            return "cost budget spent"
        return None


class UnitFailed(RuntimeError):
    """One unit gave up after its attempts. The caller decides what that costs."""


def attempt(run: Run, *, kind: str, do, attempts: int = 2):
    """Run one unit, and hand it the gate's complaint once before giving up.

    The write cycle has had this since the beginning. Phases 0 to 4 did not, so
    one malformed answer killed a run that had already paid for its research.

    The unit is the retry granularity, never the phase. Re-running the whole
    research phase because the fourth question came back without JSON makes you
    pay again for the three that worked.

    `gates.decide` owns the arithmetic, exactly as it does for the writing. The
    signature is the failure kind, not its wording, so two identical failures
    read as a stall and escalate with "not converging" rather than burning the
    last attempt to watch it happen again.

    `Escalate` passes through untouched. A runtime ceiling is not a turn to
    retry, and retrying it spends the rest of the budget rediscovering it.
    """
    previous: tuple[str, ...] | None = None
    note = ""
    for iteration in range(1, attempts + 1):
        # Never spend on a retry the budget cannot cover.
        spent = run.exhausted()
        if spent and iteration > 1:
            raise UnitFailed(f"{kind}: {spent}")
        try:
            return do(note)
        except Escalate:
            raise
        except (TurnFailed, RunFailed) as exc:
            signature = (kind,)
            decision = gates.decide(
                passed=False,
                iteration=iteration,
                budget=attempts,
                signature=signature,
                previous_signature=previous,
                usd_left=0.0 if run.exhausted() else 1.0,
            )
            run.log(f"    {kind} attempt {iteration}: {exc}")
            if decision.stop:
                raise UnitFailed(f"{kind}: {exc}. {decision.reason}") from exc
            previous = signature
            note = gates.retry_instruction(decision, [str(exc)])
    raise UnitFailed(kind)


# ---------------------------------------------------------------------------
# Phases 0 to 4. Each runs once, and skips when its output already exists.


def corpus_pack(run: Run) -> dict:
    """Build the topic's corpus pack before any model call.

    Read-only, and optional. A missing brain is a thinner outline, not a
    failed run. Nothing here is treated as verified. It tells the outliner
    what words this body of work already uses, and which corpus keys a
    section may cite.
    """
    dest = run.file("corpus")
    packed = corpus.pack(
        run.topic,
        run.corpus_roots(),
        dest,
        limit=MAX_PRIOR_ART_HITS * 4,
        subjects=run.corpus_subjects,
    )
    return {
        "hits": len(packed["hits"]),
        "brains": packed["roots"],
        "missing": packed["missing"],
        "corpus_thin": packed["corpus_thin"],
        "subjects": packed["subjects"],
    }


# Old name. Tests and greps that still say prior_art keep working.
prior_art = corpus_pack


def _pack_keys(run: Run) -> list[str]:
    path = run.file("corpus/brain-pack.json")
    if not path.exists():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("keys") or [])
    except (OSError, json.JSONDecodeError):
        return []


def plan(run: Run) -> dict:
    """Outline the paper, validate it, judge it, and stamp the approved copy.

    Python writes `outline.json`, `outline-verdict.json`, and
    `outline.approved.json`. The outliner and the outline judge hold no write
    tool, so they cannot disagree with those files.

    Kept as `plan` so existing tests and log lines still name the phase.
    """
    return do_outline(run)


def _budget_for(run: Run) -> dict:
    return {
        "questions": run.max_questions,
        "diagrams": run.max_diagrams,
        "words": run.word_target_total,
    }


def _call_outliner(run: Run, note: str) -> dict:
    pack_path = run.file("corpus/brain-pack.md")
    prior_text = pack_path.read_text(encoding="utf-8") if pack_path.exists() else ""
    args = (run.topic, prior_text, _budget_for(run), note)
    method = getattr(run.turns, "outline", run.turns.plan)
    drafted = method(*args, brief=run.brief) if run.brief else method(*args)
    if not isinstance(drafted, dict):
        raise RunFailed("the outliner returned no outline object")
    errors = outlines.validate(
        drafted,
        word_target_total=run.word_target_total,
        corpus_keys=_pack_keys(run),
    )
    if errors:
        raise RunFailed(outlines.retry_note(errors))
    return drafted


def _draft_valid_outline(run: Run) -> dict:
    def once(note: str) -> dict:
        return _call_outliner(run, note)

    try:
        return attempt(run, kind="outline", do=once)
    except UnitFailed as exc:
        raise RunFailed(str(exc)) from exc


def _judge_loop(run: Run, drafted: dict) -> dict:
    """Judge, then re-outline with actionable_changes, at most three rounds.

    `passed` from the judge wins over `score`. A repeated failure signature
    escalates as a stall through `gates.decide`.
    """
    previous: tuple[str, ...] | None = None
    current = drafted
    judge = getattr(run.turns, "judge_outline", None)
    if judge is None:
        verdict = {
            "passed": True,
            "score": 1.0,
            "blocking_issues": [],
            "actionable_changes": [],
        }
        run.write_json("outline-verdict.json", verdict)
        return current

    for round_no in range(1, OUTLINE_JUDGE_ROUNDS + 1):
        spent = run.exhausted()
        if spent and round_no > 1:
            raise RunFailed(f"outline judge: {spent}")
        try:
            verdict = judge(current)
        except Escalate:
            raise
        except (TurnFailed, RunFailed) as exc:
            raise RunFailed(f"outline judge: {exc}") from exc
        if not isinstance(verdict, dict):
            raise RunFailed("the outline judge returned no verdict object")
        run.write_json("outline-verdict.json", verdict)
        # passed wins over score. A high score with passed false is still a fail.
        if verdict.get("passed"):
            return current
        signature = outlines.judge_signature(verdict)
        decision = gates.decide(
            passed=False,
            iteration=round_no,
            budget=OUTLINE_JUDGE_ROUNDS,
            signature=signature,
            previous_signature=previous,
            usd_left=0.0 if run.exhausted() else 1.0,
        )
        run.log(f"    outline judge round {round_no}: {decision.reason}")
        if decision.stop:
            raise RunFailed(f"outline judge: {decision.reason}")
        previous = signature
        changes = verdict.get("actionable_changes") or []
        issues = [
            f"{item.get('section') or 'paper'}/{item.get('rule')}: {item.get('description')}"
            for item in (verdict.get("blocking_issues") or [])
            if isinstance(item, dict)
        ]
        note = gates.retry_instruction(decision, issues or list(signature))
        if changes:
            note += "\nApply these actionable changes:\n" + "\n".join(f"- {c}" for c in changes)
        current = _draft_valid_outline_with_note(run, note)
        run.write_json("outline.json", current)
    raise RunFailed("outline judge: three rounds exhausted")


def _draft_valid_outline_with_note(run: Run, note: str) -> dict:
    def once(ignored: str) -> dict:
        return _call_outliner(run, note)

    try:
        return attempt(run, kind="outline", do=once)
    except UnitFailed as exc:
        raise RunFailed(str(exc)) from exc


def _finish_outline(run: Run, drafted: dict) -> dict:
    """Stamp, or pause for `--approve`."""
    run.write_json("outline.json", drafted)
    run.file("outline.md").write_text(outlines.to_markdown(drafted), encoding="utf-8")
    judged_path = run.file("outline-judged.json")
    if judged_path.exists():
        judged = json.loads(judged_path.read_text(encoding="utf-8"))
        if outlines.canonical(drafted) != outlines.canonical(judged):
            run.log("    outline.json changed since it was judged; judging once more")
            judge = getattr(run.turns, "judge_outline", None)
            if judge is not None:
                verdict = judge(drafted)
                run.write_json("outline-verdict.json", verdict)
                if not verdict.get("passed"):
                    raise RunFailed("the edited outline did not pass the judge")
            run.write_json("outline-judged.json", drafted)
    else:
        run.write_json("outline-judged.json", drafted)

    if run.require_approval and not run.resume:
        raise AwaitingApproval(run.file("outline.md"))

    approved_by = "operator" if run.resume else "judge"
    run.write_json("outline.approved.json", outlines.stamp(drafted, approved_by=approved_by))
    return {
        "sections": len(drafted.get("sections") or []),
        "questions": len(outlines.questions(drafted)),
        "diagrams": len(outlines.diagrams(drafted)),
        "charts": len(outlines.charts(drafted)),
        "approved_by": approved_by,
        "sha256": outlines.digest(drafted),
    }


def do_outline(run: Run) -> dict:
    """Produce a validated, judged, approved outline.

    Resume after `--approve`: `outline.json` exists, `outline-judged.json`
    exists, `outline.approved.json` does not. Diff, maybe re-judge, stamp.
    """
    existing = run.file("outline.json")
    judged = run.file("outline-judged.json")
    if existing.exists() and judged.exists():
        drafted = run.read_json("outline.json")
        errors = outlines.validate(drafted, word_target_total=run.word_target_total)
        if errors:
            raise RunFailed(outlines.retry_note(errors))
        return _finish_outline(run, drafted)

    drafted = _draft_valid_outline(run)
    run.write_json("outline.json", drafted)
    drafted = _judge_loop(run, drafted)
    run.write_json("outline.json", drafted)
    return _finish_outline(run, drafted)


def approved_outline(run: Run) -> dict:
    """The only outline later phases may read."""
    path = run.file("outline.approved.json")
    if not path.exists():
        raise RunFailed("no approved outline. Later phases read outline.approved.json only.")
    return outlines.load_approved(run.read_json("outline.approved.json"))


def do_research(run: Run) -> dict:
    """Answer every approved key_question, in outline order.

    A claim carries the section it serves so the writer never has to guess, and
    a quote so the verify phase has something to search for. A claim with no
    quote is a claim nobody can check, and it is recorded as such.
    """
    planned = outlines.plan_view(approved_outline(run))
    findings: list[dict] = []
    claims: list[dict] = []
    failed: list[dict] = []
    stopped = None

    for question in planned["questions"]:
        # The ceiling has to be checked here, not only at the gate. The gate
        # runs once per attempt, and this loop can spend the whole budget
        # several times over before the gate ever sees it.
        stopped = run.exhausted()
        if stopped:
            break
        try:
            answer = attempt(
                run,
                kind=f"research:{question['id']}",
                do=lambda note, q=question: run.turns.research(q["text"], note),
            )
        except UnitFailed as exc:
            # One question that will not answer is not a dead run. Record it
            # and move on. The paper is thinner, and the record says why.
            failed.append({"id": question["id"], "text": question["text"], "reason": str(exc)})
            continue
        except research.BudgetExceeded as exc:
            stopped = str(exc)
            break
        answer["question_id"] = question["id"]
        answer["section"] = question["section"]
        findings.append(answer)
        for index, claim in enumerate(answer.get("claims", [])):
            claims.append(
                {
                    "id": f"{question['id']}-c{index + 1}",
                    "text": claim.get("text", ""),
                    "source_url": claim.get("source_url", ""),
                    "quote": claim.get("quote", ""),
                    "question_id": question["id"],
                    "section": question["section"],
                    "status": "unverified",
                }
            )

    sources: list[dict] = []
    seen: set[str] = set()
    for finding in findings:
        for source in finding.get("sources", []):
            if source.get("url") and source["url"] not in seen:
                seen.add(source["url"])
                sources.append(source)

    run.write_json(
        "sources.json",
        {"findings": findings, "sources": sources, "failed": failed, "stopped": stopped},
    )
    run.write_json("claims.json", {"claims": claims})
    if not claims:
        # Two different failures, and the reason is what a person acts on.
        raise RunFailed(
            f"the research phase stopped early ({stopped}) before any claim was found"
            if stopped
            else "no source produced a single claim. There is nothing to write a paper from."
        )
    return {
        "findings": len(findings),
        "claims": len(claims),
        "sources": len(sources),
        "failed": len(failed),
        "stopped": stopped,
    }



def to_verify(claims: list[dict], limit: int) -> list[dict]:
    """Which claims get a second opinion when there is not budget for all.

    Claims carrying a number, a version, or a date go first. They are the ones
    that go stale and the ones a reader can check and find wrong. Order is
    otherwise preserved, so a paper's early sections are not starved by a late
    one that happens to be full of version strings.
    """
    if len(claims) <= limit:
        return claims
    ranked = sorted(
        enumerate(claims), key=lambda pair: (0 if NUMERIC.search(pair[1]["text"]) else 1, pair[0])
    )
    chosen = {index for index, _ in ranked[:limit]}
    return [claim for index, claim in enumerate(claims) if index in chosen]


def verify(run: Run) -> dict:
    """Check each claim against a source the verifier finds on its own.

    The verifier is given the claim text and nothing else. Handing it the
    researcher's source turns an independent check into a reading-comprehension
    exercise, and two models reading one page agree by construction.

    There is no arbiter. A disputed claim in a white paper is a claim you
    soften, not one you settle with a third opinion.
    """
    claims = run.read_json("claims.json")["claims"]
    chosen = {id(claim) for claim in to_verify(claims, run.max_claims)}
    verdicts = []
    stopped = None
    skipped = 0
    for claim in claims:
        if id(claim) not in chosen:
            # Past the cap. Unverified is the honest state: the writer softens
            # it, and the knowledge bundle records that nobody checked it.
            claim["status"] = "unverified"
            claim["verifier_url"] = ""
            claim["verifier_excerpt"] = f"not checked: past the {run.max_claims} claim budget"
            verdicts.append({"claim_id": claim["id"], "status": "unverified", "verdict": None})
            skipped += 1
            continue
        if stopped or (stopped := run.exhausted()):
            # Out of budget mid-verification. Every claim from here stays
            # unverified, which the writer states qualitatively. Marking the
            # rest verified because the money ran out is the lie.
            claim["status"] = "unverified"
            claim["verifier_url"] = ""
            claim["verifier_excerpt"] = f"not checked: {stopped}"
            verdicts.append({"claim_id": claim["id"], "status": "unverified", "verdict": None})
            continue
        try:
            verdict = run.turns.verify(claim["text"])
        except (TurnFailed, research.BudgetExceeded) as exc:
            # Fail open, never fail silent. An unverified claim is written
            # qualitatively, which is a weaker sentence, not a wrong one.
            verdict = {"verdict": "unclear", "source_url": "", "excerpt": f"unavailable: {exc}"}

        if verdict.get("verdict") == "supports":
            status = "verified"
        elif verdict.get("verdict") == "contradicts":
            # Both sides hold a quote, so the disagreement is real and the paper
            # names it. Only the verifier holds one, so the claim goes.
            status = "disputed" if claim.get("quote") else "contradicted"
        else:
            status = "unverified"

        claim["status"] = status
        claim["verifier_url"] = verdict.get("source_url", "")
        claim["verifier_excerpt"] = verdict.get("excerpt", "")
        verdicts.append(
            {"claim_id": claim["id"], "status": status, "verdict": verdict.get("verdict")}
        )

    run.write_json("claims.json", {"claims": claims})
    run.write_json("verdicts.json", {"verdicts": verdicts})
    counts: dict[str, int] = {}
    for verdict in verdicts:
        counts[verdict["status"]] = counts.get(verdict["status"], 0) + 1
    if stopped:
        counts["stopped"] = stopped
    if skipped:
        counts["past_budget"] = skipped
    return counts


def diagram(run: Run) -> dict:
    drafted = approved_outline(run)
    figures = []
    for spec in outlines.diagrams(drafted):
        figure = diagrams.draw(
            run.turns,
            name=spec["name"],
            concept=spec["concept"],
            section=spec.get("section", ""),
            topic=run.topic,
            out_dir=run.file("diagrams"),
            theme=run.theme,
        )
        figures.append(figure.to_dict())
    run.write_json("diagrams.json", {"figures": figures})
    drawn = [f for f in figures if f["path"]]
    return {"figures": len(figures), "rendered": len(drawn)}


def do_charts(run: Run) -> dict:
    """Render `kind: chart` figures from data tables and the ledger.

    A chart with no rows is skipped with `no data`, not with a phase-skip
    log. Python renders. The chartist only returns a spec.
    """
    drafted = approved_outline(run)
    ledger = _ledger(run)
    rendered = []
    skipped = []
    for figure in outlines.charts(drafted):
        name = figure.get("name") or "chart"
        rows = charts.collect(run.work_dir, figure, ledger)
        if not rows:
            run.log(f"    skipping chart {name!r}: no data")
            skipped.append(name)
            continue
        spec = {}
        if hasattr(run.turns, "chart_spec"):
            try:
                spec = run.turns.chart_spec(figure, rows) or {}
            except (TurnFailed, Escalate):
                spec = {}
        if not spec.get("x"):
            spec = charts.default_spec(figure, rows)
        spec.setdefault("section", figure.get("section") or "")
        spec.setdefault("name", name)
        record = charts.render(spec, rows, run.file("charts"))
        record["section"] = figure.get("section") or spec.get("section") or ""
        rendered.append(record)
        run.log(f"    chart {name}: {len(record.get('values') or [])} values")
    run.write_json("charts.json", {"charts": rendered, "skipped": skipped})
    return {"rendered": len(rendered), "skipped": len(skipped)}


def do_sections(run: Run) -> dict:
    """Forward-only section loop. Writes claims.json so assemble still reads it."""
    approved = approved_outline(run)
    drafted_sections = approved.get("sections") or []
    if not drafted_sections:
        raise RunFailed("the approved outline has no sections")
    metas = []
    for section in drafted_sections:
        stopped = run.exhausted()
        if stopped:
            break
        metas.append(section_loop.run_section(run, section))

    findings: list[dict] = []
    claims: list[dict] = []
    verdicts: list[dict] = []
    sources: list[dict] = []
    seen: set[str] = set()
    failed: list[dict] = []
    for section in drafted_sections:
        sid = section["id"]
        fpath = run.file(f"knowledge/{sid}/findings.json")
        if not fpath.exists():
            continue
        try:
            payload = json.loads(fpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        section_findings = payload.get("findings") or []
        findings.extend(section_findings)
        vpath = run.file(f"knowledge/{sid}/verdicts.json")
        by_id: dict[str, dict] = {}
        if vpath.exists():
            try:
                for item in json.loads(vpath.read_text(encoding="utf-8")).get("verdicts") or []:
                    by_id[item.get("finding_id") or ""] = item
                    verdicts.append(item)
            except (OSError, json.JSONDecodeError):
                pass
        number = len(claims)
        for finding in section_findings:
            status = (by_id.get(finding.get("id") or "") or {}).get("state") or "unverified"
            url = (finding.get("source") or {}).get("url_or_path") or ""
            if status != "contradicted":
                number += 1
                claims.append(
                    {
                        "id": finding.get("id") or f"{sid}-c{number}",
                        "text": finding.get("claim") or "",
                        "source_url": url,
                        "quote": finding.get("quote") or "",
                        "question_id": finding.get("answers_question") or "",
                        "section": sid,
                        "status": status,
                        "number": number,
                        "origin": finding.get("origin")
                        or (finding.get("source") or {}).get("kind")
                        or "",
                        "source_kind": (finding.get("source") or {}).get("source_kind")
                        or finding.get("source_kind")
                        or "",
                        "vendor": (finding.get("source") or {}).get("vendor") or "",
                        "epistemic": finding.get("epistemic") or "",
                    }
                )
            if url and url not in seen:
                seen.add(url)
                src = finding.get("source") or {}
                sources.append({"url": url, "title": src.get("title") or ""})
        for gap in payload.get("coverage_gaps") or []:
            failed.append({"id": sid, "text": gap.get("question") or "", "reason": "coverage_gap"})

    run.write_json(
        "sources.json",
        {"findings": findings, "sources": sources, "failed": failed, "stopped": None},
    )
    run.write_json("claims.json", {"claims": claims})
    run.write_json("verdicts.json", {"verdicts": verdicts})
    if not claims:
        raise RunFailed("no source produced a single claim. There is nothing to write a paper from.")
    return {
        "sections": len(metas),
        "findings": len(findings),
        "claims": len(claims),
        "skipped": sum(1 for item in metas if item.get("skipped")),
    }


def maybe_write(run: Run) -> dict:
    """First attempt: the section loop already wrote. Retry: rewrite from claims."""
    planned = outlines.plan_view(approved_outline(run))
    out = run.file("sections")
    have = bool(planned["sections"]) and all(
        (out / f"{section['id']}.md").exists() for section in planned["sections"]
    )
    if have and run.state.iteration <= 1 and not run.file("review.json").exists():
        return {
            "sections": len(planned["sections"]),
            "from_message": 0,
            "retry_notes": False,
            "skipped": True,
        }
    return write_sections(run)


# ---------------------------------------------------------------------------
# Phases 5 to 8. The retry cycle.

USABLE = ("verified", "disputed", "unverified")


def _numbered(claims: list[dict], planned: dict) -> tuple[list[dict], list[dict]]:
    """Assign reference numbers in the order the paper will read.

    Numbering by source, not by claim, so two claims from one page share a
    number. Numbering in section order means reference 1 appears before
    reference 2, which is the only thing a reader notices about a reference
    list.
    """
    order = [section["id"] for section in planned["sections"]]
    usable = [c for c in claims if c["status"] in USABLE]
    usable.sort(key=lambda c: order.index(c["section"]) if c["section"] in order else len(order))

    sources: list[str] = []
    extra: dict[str, dict] = {}
    for claim in usable:
        url = claim.get("source_url") or claim.get("verifier_url") or ""
        if url and url not in sources:
            sources.append(url)
            extra[url] = {
                "origin": claim.get("origin") or "",
                "source_kind": claim.get("source_kind") or "",
                "epistemic": claim.get("epistemic") or "",
            }
        claim["number"] = sources.index(url) + 1 if url else 0
    refs = []
    for index, url in enumerate(sources):
        meta = extra.get(url) or {}
        refs.append(
            {
                "url": url,
                "number": index + 1,
                "origin": meta.get("origin") or "",
                "source_kind": meta.get("source_kind") or "",
                "epistemic": meta.get("epistemic") or "",
                "model_brief": checks.is_model_brief(meta),
            }
        )
    return usable, refs


def write_sections(run: Run) -> dict:
    planned = outlines.plan_view(approved_outline(run))
    # Pass the full approved section (objective, abstract, claims, word_target)
    # through to the writer. plan_view keeps those fields.
    by_id = {section["id"]: section for section in planned["sections"]}
    approved = approved_outline(run)
    for section in approved.get("sections") or []:
        if section["id"] in by_id:
            by_id[section["id"]] = {**by_id[section["id"]], **section}
    claims = run.read_json("claims.json")["claims"]
    figures = run.read_json("diagrams.json")["figures"]
    usable, _ = _numbered(claims, planned)

    notes = ""
    review_path = run.file("review.json")
    if review_path.exists():
        issues = json.loads(review_path.read_text(encoding="utf-8")).get("issues", [])
        blocking = [i for i in issues if i.get("severity") in ("critical", "major")]
        if blocking:
            # Only the current verdict's issues, never the accumulated history.
            # Handing a writer every complaint it has ever received produces
            # over-correction, which reads as a different paper each round and
            # never converges.
            notes = gates.retry_instruction(
                gates.Decision(
                    gates.RETRY, "", final_attempt=run.state.iteration + 1 >= run.max_iterations
                ),
                [f"{i.get('section') or 'paper'}: {i['description']}" for i in blocking],
            )

    out = run.file("sections")
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    from_message = 0
    for section in planned["sections"]:
        if run.exhausted():
            break
        payload = by_id.get(section["id"], section)
        path = out / f"{section['id']}.md"
        path.unlink(missing_ok=True)
        bound = [c for c in usable if c["section"] == section["id"]]
        figures_here = [f for f in figures if f["section"] == section["id"] and f["path"]]
        relative = f"sections/{section['id']}.md"
        instruction = _section_instruction(payload, notes)
        body = run.turns.write(payload, bound, figures_here, instruction, relative)
        # The writer holds `Write` scoped to `sections/**` and is told to use
        # it. Prefer the file, because a long section that round-trips through
        # a message is the one that comes back truncated. Fall back to the
        # message so a writer that only answered still produces a section.
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            path.write_text((body or "").rstrip() + "\n", encoding="utf-8")
            from_message += 1
        if run.enforce_research_policy and not run.exhausted():
            words = checks.word_count(path.read_text(encoding="utf-8"))
            if words < checks.MIN_SECTION_WORDS:
                target = payload.get("word_target") or checks.MIN_SECTION_WORDS
                extra = (
                    f"{_section_instruction(payload)}\n\nThe last draft was {words} words. "
                    "Unpack the bound claims into mechanism, tradeoff, and evidence "
                    f"limit until the section reaches about {target} words. Do not invent facts."
                )
                if notes:
                    extra = f"{extra}\n\n{notes}"
                path.unlink(missing_ok=True)
                body = run.turns.write(payload, bound, figures_here, extra, relative)
                if not path.exists() or not path.read_text(encoding="utf-8").strip():
                    path.write_text((body or "").rstrip() + "\n", encoding="utf-8")
                    from_message += 1
        written += 1
    if not written:
        raise RunFailed("the budget ran out before any section was written")
    return {"sections": written, "from_message": from_message, "retry_notes": bool(notes)}


def assemble(run: Run) -> dict:
    """Stitch the sections and append the reference list.

    Deterministic. Asking a model to re-emit the whole paper to join it is how
    a paper loses a section between two model calls.
    """
    planned = outlines.plan_view(approved_outline(run))
    claims = run.read_json("claims.json")["claims"]
    _, references = _numbered(claims, planned)

    parts = [f"# {planned['title']}", ""]
    if planned.get("abstract") or planned.get("thesis"):
        parts += ["## Abstract", "", (planned.get("abstract") or planned.get("thesis") or "").strip(), ""]
    flags: list[dict] = []
    for section in planned["sections"]:
        path = run.file("sections") / f"{section['id']}.md"
        if not path.exists():
            continue
        # A writer told not to append a reference list will still sometimes
        # append one, and an instruction is not a mechanism. Strip it here.
        text = checks.drop_owned_headings(path.read_text(encoding="utf-8"))
        text, found = checks.take_flags(text)
        flags += [{"section": section["id"], "flag": flag} for flag in found]
        parts += [text.strip(), ""]
        for chart in _charts_for(run, section["id"]):
            rel = f"charts/{Path(chart['path']).name}"
            caption = chart.get("caption") or chart.get("name") or rel
            if rel not in text:
                parts += [f"![{caption}]({rel})", ""]
    if references:
        parts += ["## References", ""]
        parts += [
            f"{ref['number']}. {ref['url']}"
            + (" (model-written brief)" if ref.get("model_brief") else "")
            for ref in references
        ]
        parts.append("")

    body = checks.strip_em_dashes("\n".join(parts))
    body = re.sub(r"\n{3,}", "\n\n", body)
    run.file("paper.md").write_text(body, encoding="utf-8")
    # Always written, empty list included, so a reader can tell "no flags" from
    # "this run never looked".
    run.write_json("unresolved.json", {"flags": flags})
    return {"bytes": len(body), "references": len(references), "flags": len(flags)}


def _charts_for(run: Run, section_id: str) -> list[dict]:
    path = run.file("charts.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [
        item
        for item in payload.get("charts") or []
        if item.get("section") == section_id and item.get("path")
    ]


def _rendered_charts(run: Run) -> list[dict]:
    path = run.file("charts.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in payload.get("charts") or [] if item.get("path")]


def corpus_for(run: Run) -> str:
    """Everything that was actually retrieved, as one blob.

    The `sourced` check searches this for every identifier the paper prints. An
    arXiv id or a DOI that is not in here was not retrieved, whatever the
    sentence around it claims.
    """
    parts = []
    for finding in run.read_json("sources.json")["findings"]:
        parts.append(finding.get("answer") or finding.get("claim") or "")
        parts += [s.get("url", "") + " " + s.get("title", "") for s in finding.get("sources", [])]
        src = finding.get("source") or {}
        parts += [src.get("url_or_path") or "", src.get("title") or "", finding.get("quote") or ""]
    for claim in run.read_json("claims.json")["claims"]:
        parts += [claim.get("quote", ""), claim.get("verifier_excerpt", "")]
    return "\n".join(parts)


def _ledger(run: Run):
    path = run.file("paper_ledger.json")
    if not path.exists():
        return {"entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": []}
    if isinstance(payload, list):
        return {"entries": payload}
    return payload


def _coverage_gaps(run: Run) -> list:
    path = run.file("sources.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(payload.get("failed") or [])


def check(run: Run) -> dict:
    body = run.file("paper.md").read_text(encoding="utf-8")
    planned = outlines.plan_view(approved_outline(run))
    claims = run.read_json("claims.json")["claims"]
    references = [ref["url"] for ref in _numbered(claims, planned)[1]]
    score = checks.check(
        body,
        references,
        base_dir=run.work_dir,
        corpus=corpus_for(run),
        headings=[section["heading"] for section in planned["sections"]],
        outline=approved_outline(run),
        enforce_source_policy=run.enforce_research_policy,
        enforce_loop_doctrine=run.enforce_loop_doctrine,
        min_words=checks.MIN_WORDS if run.enforce_research_policy else 0,
        min_section_words=checks.MIN_SECTION_WORDS if run.enforce_research_policy else 0,
        ledger=_ledger(run) if run.enforce_research_policy else None,
        gaps=_coverage_gaps(run) if run.enforce_research_policy else None,
        claims=claims if run.enforce_research_policy else None,
        charts=_rendered_charts(run),
    )
    run.write_json("check.json", score.to_dict())
    return score.to_dict()


def review(run: Run) -> dict:
    body = run.file("paper.md").read_text(encoding="utf-8")
    report = checks.Score(
        checks=[checks.Check(**c) for c in run.read_json("check.json")["checks"]]
    ).report()
    ledger = _ledger(run)
    try:
        if hasattr(run.turns, "review"):
            try:
                verdict = run.turns.review(body, report, ledger=ledger)
            except TypeError:
                verdict = run.turns.review(body, report)
        else:
            verdict = {"done": True, "summary": "no judge", "issues": []}
    except TurnFailed as exc:
        # A judge that did not answer is not a judge that agreed.
        verdict = {"done": False, "summary": f"the judge failed: {exc}", "issues": []}
    run.write_json("review.json", verdict)
    return verdict


def edit_paper(run: Run) -> dict:
    """One flow-only pass after the first green check. Add no facts.

    Python diffs each section for new specifics. A specific the evidence pack
    does not contain is reverted, so a writer that invented a number cannot
    keep it by talking past `sourced`.
    """
    sentinel = run.file("edit.done.json")
    if sentinel.exists():
        return {"skipped": True}
    planned = outlines.plan_view(approved_outline(run))
    evidence = corpus_for(run)
    reverted: list[str] = []
    edited = 0
    for section in planned["sections"]:
        path = run.file("sections") / f"{section['id']}.md"
        if not path.exists():
            continue
        before = path.read_text(encoding="utf-8")
        relative = f"sections/{section['id']}.md"
        if hasattr(run.turns, "edit_paper"):
            after = run.turns.edit_paper(section, before, relative)
        elif hasattr(run.turns, "edit_section"):
            after = run.turns.edit_section(
                section,
                before,
                {
                    "failed_rows": ["flow"],
                    "notes": ["Do not add new facts. Fix transitions and definitions only."],
                },
                relative,
            )
        else:
            after = before
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            path.write_text((after or before).rstrip() + "\n", encoding="utf-8")
        after = path.read_text(encoding="utf-8")
        novel = checks.new_claims(before, after)
        invented = [token for token in novel if token.lower() not in evidence.lower()]
        if invented:
            path.write_text(before, encoding="utf-8")
            reverted.extend(invented)
        else:
            edited += 1
    run.write_json("edit.done.json", {"edited": edited, "reverted": reverted})
    return {"edited": edited, "reverted": reverted}


# ---------------------------------------------------------------------------
# The driver.

LINEAR = [
    (0, "corpus_pack", "corpus/brain-pack.json", corpus_pack),
    (1, "outline", "outline.approved.json", do_outline),
    (2, "sections", "claims.json", do_sections),
    (4, "diagram", "diagrams.json", diagram),
    (3, "charts", "charts.json", do_charts),
]

CYCLE = [
    (5, "write", maybe_write),
    (6, "assemble", assemble),
    (7, "check", check),
    (8, "review", review),
]

# What a retry throws away, and it is only the section files. `paper.md`,
# `check.json`, and `review.json` are overwritten by the next attempt anyway,
# and deleting `review.json` here was a real bug: `write_sections` reads it to
# build the retry instruction, so wiping it first meant every attempt got the
# same prompt and the loop could only ever stall.
#
# Stale sections do have to go. A re-plan can drop a section, and a file nobody
# rewrites still gets stitched into the paper.
CYCLE_OUTPUT = ("sections",)


def run_paper(run: Run) -> dict:  # noqa: PLR0915  (the phase order, in order)
    work = Path(run.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    run.state.query_timeout_s = adapter.QUERY_TIMEOUT_SECONDS

    for number, name, output, phase in LINEAR:
        if run.file(output).exists():
            run.log(f"  {number} {name:<10} already done")
            run.state.mark(name, "skipped")
            continue
        run.log(f"  {number} {name:<10} ...")
        before = run.state.total_usd
        # Write the in-flight phase before it starts. A run killed here must
        # report the phase it died in, not the last one that finished.
        run.state.phase = name
        run.state.mark(name, "running")
        run.state.save(work)
        try:
            meta = phase(run)
        except AwaitingApproval:
            run.state.mark(name, "awaiting_approval")
            run.state.save(work)
            raise
        except Escalate as exc:
            run.state.mark(name, "escalated", reason=str(exc))
            run.state.save(work)
            raise RunFailed(f"{name}: {exc}") from exc
        except Exception as exc:
            run.state.mark(name, "failed", reason=str(exc))
            run.state.save(work)
            raise
        run.state.mark(name, "complete", usd=round(run.state.total_usd - before, 4), **meta)
        run.state.save(work)
        run.log(f"  {number} {name:<10} {meta}")

    # Out of money before a word is written. Entering the cycle here spends
    # three attempts producing an empty paper, failing the same checks, and
    # escalating on a stall, which reports "the loop is not converging" for a
    # run that never converged because it never started.
    spent = run.exhausted()
    if spent:
        run.state.mark("write", "escalated", reason=spent)
        run.state.save(work)
        raise RunFailed(f"{spent} during research. No budget was left to write the paper.")

    decision = gates.Decision(gates.RETRY, "not started")
    for iteration in range(run.state.iteration + 1, run.max_iterations + 1):
        run.state.iteration = iteration
        run.log(f"  attempt {iteration} of {run.max_iterations}")
        for number, name, phase in CYCLE:
            before = run.state.total_usd
            run.state.phase = name
            run.state.mark(name, "running")
            run.state.save(work)
            meta = phase(run)
            run.state.mark(name, "complete", usd=round(run.state.total_usd - before, 4))
            run.state.save(work)
            run.log(f"  {number} {name:<10} {meta if name != 'check' else meta['signature']}")

        score = run.read_json("check.json")
        verdict = run.read_json("review.json")

        # The judge is a row in the signature, not a separate verdict passed to
        # `judge_done`. In the enhancer loop a judge that disagrees with a green
        # rubric means a person should look, because the rubric is the whole
        # definition of done there. Here the judge scores the rows a script
        # cannot, so its complaint is the loop's own signal and the writer gets
        # a turn to answer it. Escalating on the first disagreement would make
        # the judge advisory, which is the same as not having one.
        #
        # Folding it into the signature also gets stall detection for free: a
        # judge that repeats the same complaint twice is a judge the writer is
        # not converging on.
        judge_done = bool(verdict.get("done"))
        signature = tuple(score["signature"]) + (() if judge_done else ("judge",))
        previous = tuple(run.state.previous_signature) if run.state.previous_signature else None

        decision = gates.decide(
            passed=score["passed"] and judge_done,
            iteration=iteration,
            budget=run.max_iterations,
            signature=signature,
            previous_signature=previous,
            usd_left=0.0 if run.exhausted() else 1.0,
        )
        run.state.previous_signature = list(signature)
        run.state.save(work)

        # The edit pass runs once after the first green check, then the cycle
        # re-enters at assemble. A new specific the evidence does not contain
        # is reverted in edit_paper; if anything else broke, write retries.
        if (
            decision.gate == gates.PASS
            and not run.file("edit.done.json").exists()
            and not run.exhausted()
        ):
            run.log("  8 edit      ...")
            before = run.state.total_usd
            meta = edit_paper(run)
            run.state.mark("edit", "complete", usd=round(run.state.total_usd - before, 4), **meta)
            run.state.save(work)
            run.log(f"  8 edit      {meta}")
            assemble(run)
            check_meta = check(run)
            review(run)
            run.log(f"  6 assemble  after edit")
            run.log(f"  7 check     {check_meta['signature']}")
            score = run.read_json("check.json")
            verdict = run.read_json("review.json")
            judge_done = bool(verdict.get("done"))
            signature = tuple(score["signature"]) + (() if judge_done else ("judge",))
            decision = gates.decide(
                passed=score["passed"] and judge_done,
                iteration=iteration,
                budget=run.max_iterations,
                signature=signature,
                previous_signature=previous,
                usd_left=0.0 if run.exhausted() else 1.0,
            )
            run.state.previous_signature = list(signature)
            run.state.save(work)

        if decision.stop:
            break
        for name in CYCLE_OUTPUT:
            target = run.file(name)
            shutil.rmtree(target, ignore_errors=True) if target.is_dir() else target.unlink(
                missing_ok=True
            )

    # The knowledge bundle is written whatever the gate said. A run that
    # escalated still found sources and checked claims, and throwing that away
    # means the next attempt pays for it again.
    counts = rkc.write_bundle(
        run.file("knowledge"),
        topic=run.topic,
        area=run.area,
        plan=outlines.plan_view(approved_outline(run)),
        findings=run.read_json("sources.json")["findings"],
        claims=run.read_json("claims.json")["claims"],
        ledger=_ledger(run),
    )
    valid, note = rkc.validate(run.file("knowledge"))
    run.state.mark(
        "knowledge",
        "complete",
        valid=valid,
        **{k: v for k, v in counts.items() if k != "subject_id"},
    )
    run.state.save(work)

    ingest = None
    if run.ingest_brain is not None:
        ingest = rkc.ingest_brain(run.file("knowledge"), run.ingest_brain)
        run.state.mark("ingest", "complete" if ingest.get("ok") else "skipped", **ingest)
        run.log(f"  9 ingest    {ingest}")
        run.state.save(work)

    gist = None
    if run.should_publish:
        if decision.gate != gates.PASS:
            run.log("  9 publish    skipped. The paper did not pass.")
            run.state.mark("publish", "skipped", reason=decision.reason)
        else:
            gist = publisher.publish(work, topic=run.topic)
            run.state.mark("publish", "complete", url=gist["url"])
            run.log(f"  9 publish    {gist['url']}")
    run.state.save(work)

    return {
        "gate": decision.gate,
        "reason": decision.reason,
        "paper": str(run.file("paper.md")),
        "usd": round(run.state.total_usd, 4),
        "turns": run.state.turns,
        "iterations": run.state.iteration,
        "knowledge": counts,
        "knowledge_valid": valid,
        "knowledge_note": note,
        "ingest": ingest,
        "gist": gist,
        "report": checks.Score(
            checks=[checks.Check(**c) for c in run.read_json("check.json")["checks"]]
        ).report(),
    }
