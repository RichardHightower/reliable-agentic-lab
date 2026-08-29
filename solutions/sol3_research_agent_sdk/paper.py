"""The white paper driver. Python owns the phases, the budget, and the exits.

Ten phases, in a list, in order. The list is the dispatch order and the number
is only a state key, which is what lets a phase slot in later without
renumbering the run records that already exist on disk.

    0 prior_art   read the second brain     -> prior-art.md
    1 plan        sections and questions    -> plan.json
    2 research    answers and claims        -> sources.json, claims.json
    3 verify      an independent second look-> verdicts.json
    4 diagram     figures, rendered         -> diagrams.json
    5 write       one section at a time     -> sections/*.md
    6 assemble    stitch and reference      -> paper.md
    7 check       deterministic rows        -> check.json
    8 review      the judge, on what is left-> review.json
    9 publish     a private gist, on request-> gist.json

Phases 0 to 4 run once. Phases 5 to 8 are the retry cycle, because the only
thing worth redoing on a failed check is the writing. Re-running the research
because a paragraph lost its citation marker buys a bill, not a better paper.

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

import checks
import diagrams
import gates
import publish as publisher
import research
import rkc
from turns import Escalate, TurnFailed, slugify

FOLDER = Path(__file__).resolve().parent

# The second brain is a sibling repo, not part of this one. It is read-only
# prior art, and a run must not need it.
BRAIN = FOLDER.parents[2] / "loop_eng_2nd_brain" / "knowledge"

DEFAULT_AREA = "loop-engineering"
MAX_ITERATIONS = 3
MAX_PRIOR_ART_HITS = 12

# A ceiling on the plan, not on the planner's ambition. Asked to plan a paper on
# a broad topic it will return thirty good questions, and thirty questions is
# thirty research turns plus thirty verification turns. The cap is what keeps a
# well-planned paper from being an expensive one.
MAX_QUESTIONS = 12
MAX_DIAGRAMS = 4

# A ceiling on verification, for the same reason. Four good questions produced
# a hundred and eleven claims on one live run, and every claim is a turn. The
# cap decides how many get a second opinion; the rest stay `unverified`, which
# the writer states qualitatively.
MAX_CLAIMS = 24

# Which claims get the budget when there is not enough for all of them. A claim
# with a number, a version, or a date is the one most worth a second look: it is
# the kind that goes stale, and the kind a reader can check and find wrong.
NUMERIC = re.compile(r"\d")


class RunFailed(RuntimeError):
    """A person has to look at this. The run stopped."""


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
    theme: str = diagrams.DEFAULT_THEME
    brain: Path | None = BRAIN
    brief: str = ""
    should_publish: bool = False
    # The workshop entry point enables these hard gates.  Keeping synthetic
    # phase tests opt-in lets them exercise one phase at a time without having
    # to manufacture the whole loop-control paper contract.
    enforce_research_policy: bool = False
    log: object = print

    # -- files -------------------------------------------------------------

    def file(self, name: str) -> Path:
        return Path(self.work_dir) / name

    def read_json(self, name: str) -> dict:
        return json.loads(self.file(name).read_text(encoding="utf-8"))

    def write_json(self, name: str, payload: dict) -> None:
        path = self.file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def spend(self, usd: float) -> None:
        self.state.total_usd += float(usd or 0.0)
        self.state.turns += 1

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


def prior_art(run: Run) -> dict:
    """Read the second brain for established terminology and earlier conclusions.

    Read-only, and optional. The brain is a sibling repository that an attendee
    will not have. A missing brain is a thinner plan, not a failed run.

    Nothing here is treated as verified. It tells the planner what words this
    body of work already uses, so the paper does not rename a concept that
    already has a name. Anything time-sensitive still goes on the question list.
    """
    brain = Path(run.brain) if run.brain else None
    if brain is None or not brain.exists():
        run.file("prior-art.md").write_text(
            "No second brain was found. Planned from the topic alone.\n", encoding="utf-8"
        )
        return {"hits": 0, "brain": str(brain) if brain else ""}

    words = [w for w in slugify(run.topic).split("-") if len(w) > 3]
    hits: list[str] = []
    seen: set[str] = set()
    for path in sorted((brain / "research").rglob("*.md")) if (brain / "research").exists() else []:
        if len(hits) >= MAX_PRIOR_ART_HITS:
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lowered = text.lower()
        if not all(word in lowered for word in words[:2]) or path.stem in seen:
            continue
        seen.add(path.stem)
        title = next(
            (
                line[7:].strip().strip('"')
                for line in text.splitlines()
                if line.startswith("title:")
            ),
            path.stem,
        )
        body = "\n".join(
            line for line in text.split("---", 2)[-1].strip().splitlines() if line.strip()
        )
        hits.append(f"- **{title}** ({path.parent.name})\n  {body[:280]}")

    run.file("prior-art.md").write_text(
        f"# Prior art on {run.topic}\n\n"
        "Read for terminology and for what was already concluded. Not verified.\n\n"
        + ("\n".join(hits) if hits else "Nothing in the brain matched this topic.\n"),
        encoding="utf-8",
    )
    return {"hits": len(hits), "brain": str(brain)}


def plan(run: Run) -> dict:
    """Plan the paper, then hold the plan to a budget.

    Python writes `plan.json` from the planner's schema-checked answer. Letting
    the planner write it too would give the run two plans that can disagree.

    The truncation is not tidying. Every question is a research turn and a
    verification turn, so an uncapped plan is an uncapped bill, and the planner
    has no idea what a turn costs.
    """
    prior = run.file("prior-art.md")
    prior_text = prior.read_text(encoding="utf-8") if prior.exists() else ""

    def once(note: str) -> dict:
        args = (
            run.topic,
            prior_text,
            {"questions": run.max_questions, "diagrams": run.max_diagrams},
            note,
        )
        # A commissioning brief is optional. Keep the normal turn call exactly
        # as it was so an attendee's minimal runtime only needs the six base
        # methods; the Agent SDK path receives the extra context when an E2E
        # scenario needs a specific deliverable.
        drafted = run.turns.plan(*args, brief=run.brief) if run.brief else run.turns.plan(*args)
        if not drafted.get("sections") or not drafted.get("questions"):
            raise RunFailed("the planner returned no sections or no questions")
        return drafted

    try:
        result = attempt(run, kind="plan", do=once)
    except UnitFailed as exc:
        # The plan is the one unit with no partial success to keep. Nothing
        # downstream has anything to work from.
        raise RunFailed(str(exc)) from exc

    asked, drawn = len(result["questions"]), len(result.get("diagrams", []))
    # A section the planner never asked a question about is a section it meant
    # to write from the topic alone. Work that set out before truncating, or
    # every orphan the cut creates looks like one of them.
    never_asked = {section["id"] for section in result["sections"]} - {
        question["section"] for question in result["questions"]
    }
    result["questions"] = result["questions"][: run.max_questions]
    result["diagrams"] = result.get("diagrams", [])[: run.max_diagrams]
    served = {question["section"] for question in result["questions"]}
    result["sections"] = [
        section
        for section in result["sections"]
        if section["id"] in served or section["id"] in never_asked
    ]

    run.write_json("plan.json", result)
    return {
        "sections": len(result["sections"]),
        "questions": len(result["questions"]),
        "diagrams": len(result["diagrams"]),
        "trimmed": {
            "questions": asked - len(result["questions"]),
            "diagrams": drawn - len(result["diagrams"]),
        },
    }


def do_research(run: Run) -> dict:
    """Answer every planned question, and split each answer into atomic claims.

    A claim carries the section it serves so the writer never has to guess, and
    a quote so the verify phase has something to search for. A claim with no
    quote is a claim nobody can check, and it is recorded as such.
    """
    planned = run.read_json("plan.json")
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
    planned = run.read_json("plan.json")
    figures = []
    for spec in planned.get("diagrams", []):
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
    for claim in usable:
        url = claim.get("source_url") or claim.get("verifier_url") or ""
        if url and url not in sources:
            sources.append(url)
        claim["number"] = sources.index(url) + 1 if url else 0
    return usable, [{"url": url, "number": index + 1} for index, url in enumerate(sources)]


def write_sections(run: Run) -> dict:
    planned = run.read_json("plan.json")
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
        target = out / f"{section['id']}.md"
        target.unlink(missing_ok=True)
        body = run.turns.write(
            section,
            [c for c in usable if c["section"] == section["id"]],
            [f for f in figures if f["section"] == section["id"] and f["path"]],
            notes,
            f"sections/{section['id']}.md",
        )
        # The writer holds `Write` scoped to `sections/**` and is told to use
        # it. Prefer the file, because a long section that round-trips through
        # a message is the one that comes back truncated. Fall back to the
        # message so a writer that only answered still produces a section.
        if not target.exists() or not target.read_text(encoding="utf-8").strip():
            target.write_text((body or "").rstrip() + "\n", encoding="utf-8")
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
    planned = run.read_json("plan.json")
    claims = run.read_json("claims.json")["claims"]
    _, references = _numbered(claims, planned)

    parts = [f"# {planned['title']}", ""]
    if planned.get("abstract"):
        parts += ["## Abstract", "", planned["abstract"].strip(), ""]
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
    if references:
        parts += ["## References", ""]
        parts += [f"{ref['number']}. {ref['url']}" for ref in references]
        parts.append("")

    body = checks.strip_em_dashes("\n".join(parts))
    body = re.sub(r"\n{3,}", "\n\n", body)
    run.file("paper.md").write_text(body, encoding="utf-8")
    # Always written, empty list included, so a reader can tell "no flags" from
    # "this run never looked".
    run.write_json("unresolved.json", {"flags": flags})
    return {"bytes": len(body), "references": len(references), "flags": len(flags)}


def corpus_for(run: Run) -> str:
    """Everything that was actually retrieved, as one blob.

    The `sourced` check searches this for every identifier the paper prints. An
    arXiv id or a DOI that is not in here was not retrieved, whatever the
    sentence around it claims.
    """
    parts = []
    for finding in run.read_json("sources.json")["findings"]:
        parts.append(finding.get("answer", ""))
        parts += [s.get("url", "") + " " + s.get("title", "") for s in finding.get("sources", [])]
    for claim in run.read_json("claims.json")["claims"]:
        parts += [claim.get("quote", ""), claim.get("verifier_excerpt", "")]
    return "\n".join(parts)


def check(run: Run) -> dict:
    body = run.file("paper.md").read_text(encoding="utf-8")
    planned = run.read_json("plan.json")
    references = [
        ref["url"] for ref in _numbered(run.read_json("claims.json")["claims"], planned)[1]
    ]
    score = checks.check(
        body,
        references,
        base_dir=run.work_dir,
        corpus=corpus_for(run),
        headings=[section["heading"] for section in planned["sections"]],
        enforce_source_policy=run.enforce_research_policy,
        enforce_loop_doctrine=run.enforce_research_policy,
    )
    run.write_json("check.json", score.to_dict())
    return score.to_dict()


def review(run: Run) -> dict:
    body = run.file("paper.md").read_text(encoding="utf-8")
    report = checks.Score(
        checks=[checks.Check(**c) for c in run.read_json("check.json")["checks"]]
    ).report()
    try:
        verdict = run.turns.review(body, report)
    except TurnFailed as exc:
        # A judge that did not answer is not a judge that agreed.
        verdict = {"done": False, "summary": f"the judge failed: {exc}", "issues": []}
    run.write_json("review.json", verdict)
    return verdict


# ---------------------------------------------------------------------------
# The driver.

LINEAR = [
    (0, "prior_art", "prior-art.md", prior_art),
    (1, "plan", "plan.json", plan),
    (2, "research", "claims.json", do_research),
    (3, "verify", "verdicts.json", verify),
    (4, "diagram", "diagrams.json", diagram),
]

CYCLE = [
    (5, "write", write_sections),
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

    for number, name, output, phase in LINEAR:
        if run.file(output).exists():
            run.log(f"  {number} {name:<10} already done")
            run.state.mark(name, "skipped")
            continue
        run.log(f"  {number} {name:<10} ...")
        before = run.state.total_usd
        try:
            meta = phase(run)
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
        plan=run.read_json("plan.json"),
        findings=run.read_json("sources.json")["findings"],
        claims=run.read_json("claims.json")["claims"],
    )
    valid, note = rkc.validate(run.file("knowledge"))
    run.state.mark(
        "knowledge",
        "complete",
        valid=valid,
        **{k: v for k, v in counts.items() if k != "subject_id"},
    )
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
        "gist": gist,
        "report": checks.Score(
            checks=[checks.Check(**c) for c in run.read_json("check.json")["checks"]]
        ).report(),
    }
