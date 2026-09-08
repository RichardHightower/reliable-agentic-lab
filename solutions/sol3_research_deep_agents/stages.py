"""The nine stages, each with a gate Python owns.

A stage is a function plus a gate. The function asks a model for something. The
gate decides, without asking anyone, whether what came back is usable. When the
gate fails, `paper.py` retries with the gate's own complaint as the instruction,
and `gates.decide` decides when to stop trying.

The split is the lesson. `plan_gate` does not ask whether the plan is good, it
counts questions and checks. `outline_gate` does not read for coherence, it
verifies every section names a claim that exists. Judgment stays with the
reviewer subagent, where it can be wrong without corrupting the run.

Stage 8 and stage 9 call no model at all. Assembling markdown and pushing a gist
are things a program does correctly every time, and handing either to a model
buys a new failure mode and no new capability.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import diagrams
import brief
import evidence
import metadata
import paper_check
import roleplan
import source_policy

# #479. The byline names this port's own harness, never a hand-written guess.
HARNESS_NAME = "LangChain Deep Agents"
# The Taskfile overrides this through the `CONFLICTS` variable, read as an
# environment variable at assemble time so a test's `monkeypatch.setenv`
# takes effect with no module reload.
DEFAULT_CONFLICTS = "No funding. No conflicts declared."

# A plan that asks fewer than this is not research, it is a lookup.
MIN_QUESTIONS = 3
MAX_QUESTIONS = 12
# Verification cost scales with this count, not with the prose length. Four
# to six load-bearing questions are enough for a focused paper; marking every
# speculative question important made one unavailable standards host block an
# otherwise well-sourced run.
MAX_IMPORTANT_QUESTIONS = 6
EXIT_DOCTRINE_QUESTION = "What three exits does this repo's paper loop check, and in what order?"

# Sections that bind to no claims of their own. The abstract restates what the
# body already cited, so binding it would mean listing every claim twice and
# keeping the two lists in step. References is generated from the ledger.
# Methods is Python-written from the run record, never bound to a claim at
# all. The conclusion restates the body the same way the abstract does. #478
UNBOUND_SECTIONS = ("abstract", "conclusion", "methods", "references")

FENCED_JSON = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
CITATION = re.compile(r"\[(\d+)\]")

# A domain-shaped token inside a `check` string. Deliberately narrow: it wants
# a compound host like `arxiv.org` or `pubmed.ncbi.nlm.nih.gov`, not an
# abbreviation like `e.g.` or a version number. #469
HOST_LIKE = re.compile(
    r"\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\."
    r"(?:com|org|net|gov|edu|int|io|ai|co|biz|info)\b",
    re.IGNORECASE,
)


def _evidence_requirements_problem(reqs) -> str | None:
    """What is wrong with a question's `evidence_requirements` block, or
    `None`. Copied from the Agent SDK port's `outline._evidence_requirements_problem`,
    never imported: two standalone folders. #475

    Checked only when `plan_gate` is asked to enforce it: an older plan
    that carries no block at all still parses here, it just names the
    missing field, never a crash.
    """
    if not isinstance(reqs, dict) or not reqs:
        return "is missing evidence_requirements (study_types, min_count, recency_years, populations)"
    study_types = reqs.get("study_types")
    if not isinstance(study_types, list) or not study_types:
        return "evidence_requirements needs a non-empty study_types list"
    unknown = [t for t in study_types if t not in source_policy.STUDY_TYPES]
    if unknown:
        return f"evidence_requirements study_types names unknown type(s) {unknown}"
    min_count = reqs.get("min_count")
    if not isinstance(min_count, int) or isinstance(min_count, bool) or min_count < 1:
        return "evidence_requirements needs a positive integer min_count"
    recency_years = reqs.get("recency_years")
    if not isinstance(recency_years, int) or isinstance(recency_years, bool) or recency_years < 0:
        return "evidence_requirements needs a non-negative integer recency_years"
    if not isinstance(reqs.get("populations"), list):
        return "evidence_requirements needs populations as an array of strings"
    return None


def check_names_host(text: str) -> str:
    """The host a `check` names, or "".

    A `check` states the observable fact that answers a question. The source
    boundary is Python's admitted allowlist, decided after the plan exists;
    a `check` that names a host turns the plan into that boundary instead,
    which is what let one scout's single admitted host become the paper's
    only source. #469
    """
    match = HOST_LIKE.search(str(text or ""))
    return match.group(0).rstrip(".").lower() if match else ""

STAGE_ORDER = (
    "corpus",
    "scout",
    "plan",
    "sources",
    "search",
    "verify",
    "outline",
    "charts",
    "write",
    # `diagram` moved here from right after `outline` (#476): a figure is
    # commissioned from the bound claims of the section that carries it, and
    # those claims do not exist until the section is written.
    #
    # #464 moved `diagram` ahead of `trim`, the opposite of its #476 order:
    # `trim` now also adds an in-text `Figure N` mention for every figure a
    # section carries, which it cannot do before a figure has a number, and
    # a figure has no number until `diagram` renders it. `stage_diagram`
    # re-stamps `diagrams.json`'s own `sections_sha` after `trim` finishes
    # (`_restamp_diagram_guard`), so a caveat cut or an added mention does
    # not make a future resume's cache look stale and re-spend a render it
    # does not need.
    "diagram",
    # P9, #477. Between diagram and review, not after assemble: `stage_review`
    # is the reviewer the creatine run's `no_filler` complaint named, and it
    # grades `self.written` directly, before assembly exists. A repeat
    # caught after assembly would leave the reviewer grading a body that
    # already failed this row.
    "trim",
    "review",
    "assemble",
    "publish",
)


class GateFailed(Exception):
    """The stage produced something unusable. The message is the retry prompt."""

    def __init__(
        self,
        message: str,
        signature: tuple[str, ...] = (),
        *,
        score: float | None = None,
    ):
        super().__init__(message)
        self.signature = signature or (message.split(".", maxsplit=1)[0][:40],)
        # Set only by `review_gate`, when the reviewer's reply carried one.
        # `_run_stage` reads it to tell a converging draft from a stalled one.
        self.score = score


@dataclass
class StageResult:
    name: str
    usd: float = 0.0
    calls: int = 0
    artifacts: dict[str, str] = field(default_factory=dict)
    summary: str = ""


def parse_json(text: str) -> dict:
    """Read JSON out of a model reply, fenced or bare.

    A model that was asked for JSON returns JSON about nine times in ten, and
    prose wrapped around JSON the tenth. Failing the whole stage on the wrapper
    would spend a retry on punctuation.
    """
    fenced = FENCED_JSON.search(text)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise GateFailed("the reply held no JSON object.", ("not_json",))
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise GateFailed(f"the JSON did not parse: {exc}.", ("bad_json",)) from exc


def reply_was_truncated(text: str) -> bool:
    """A reply that stopped mid-object rather than one that was never JSON.

    `parse_json` raises the same error for both: a model that answered in
    prose, and a model that hit its output ceiling three sections into a
    JSON object. The two need different retries, so tell them apart by
    counting braces. A generation cut off mid-object always leaves more `{`
    than `}`; a reply that was simply never JSON, or one with a stray typo,
    almost never does. An opening fence with no closing fence is the other
    tell: the model stopped before it could close its own code block.
    """
    fenced = FENCED_JSON.search(text)
    body = fenced.group(1) if fenced else text
    if body.find("{") < 0:
        return False
    # A brace inside a quoted string value is not structural. Blank out every
    # string literal first, or a claim's own prose ("the loop uses { and }")
    # reads as an unclosed object.
    stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', body)
    return stripped.count("{") > stripped.count("}")


# -- 1. plan --------------------------------------------------------------


def plan_gate(
    plan: dict, *, loop_doctrine: bool = True, require_evidence_requirements: bool = True
) -> None:
    """Count what a plan must have. No opinion about whether it is a good plan.

    `loop_doctrine` is the seminar's own topic, not a property every paper has.
    Off, any topic's own first question is fine. On, question one is bound to
    this repository's exit order, unchanged from before the flag existed.

    `require_evidence_requirements` names every important question missing
    its `evidence_requirements` block. #475
    """
    misses = []
    questions = plan.get("questions") or []
    if not MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS:
        misses.append(
            f"there are {len(questions)} questions. "
            f"Write between {MIN_QUESTIONS} and {MAX_QUESTIONS}."
        )
    if (
        loop_doctrine
        and questions
        and questions[0].get("question", "").strip() != EXIT_DOCTRINE_QUESTION
    ):
        misses.append(
            "the first question must ask what three exits this repo's paper loop checks, in order."
        )
    seen = set()
    for index, question in enumerate(questions):
        label = question.get("id") or f"question {index + 1}"
        if not question.get("question", "").strip():
            misses.append(f"{label} has no question text.")
        if not question.get("check", "").strip():
            misses.append(f"{label} has no check. Name the observable fact that answers it.")
        named_host = check_names_host(question.get("check", ""))
        if named_host:
            misses.append(
                f"{label}'s check names {named_host!r}. A check may not name a host; the "
                "source boundary is Python's admitted allowlist, decided after the plan "
                "exists, never the plan itself."
            )
        if label in seen:
            misses.append(f"{label} is used twice. Every question needs its own id.")
        seen.add(label)
    important = [question for question in questions if question.get("important")]
    if not important:
        misses.append("no question is marked important. The verifier would check nothing.")
    if len(important) > MAX_IMPORTANT_QUESTIONS:
        misses.append(
            f"there are {len(important)} important questions. Mark at most "
            f"{MAX_IMPORTANT_QUESTIONS} load-bearing questions important; the rest may still "
            "contribute sources without blocking the paper."
        )
    if require_evidence_requirements:
        for question in important:
            label = question.get("id") or "an important question"
            problem = _evidence_requirements_problem(question.get("evidence_requirements"))
            if problem:
                misses.append(f"{label} {problem}")
    if not plan.get("sections"):
        misses.append("the plan names no sections.")
    for figure in plan.get("diagrams") or []:
        if figure.get("kind") not in ("mermaid", "plantuml"):
            misses.append(f"diagram {figure.get('name')!r} has no kind of mermaid or plantuml.")
    if misses:
        raise GateFailed(" ".join(misses), tuple(sorted({m.split()[0] for m in misses})))


# What the structural sections are for. A planner does not write these,
# because `normalize_plan` is what puts them there. Methods is Python-written
# at assemble time (`Paper.stage_assemble`), never by the writer, so its
# objective here is never read as a writing instruction; it exists only so
# `outline_gate` and `stage_outline`'s prompt see a named section like any
# other. #478
STRUCTURAL = {
    "abstract": "State the thesis, the evidence behind it, and the limit, in one paragraph.",
    "introduction": "Name the problem, who has it, and what this paper settles about it.",
    "methods": "Python-written from the run record. No model turn.",
    "conclusion": "Restate the body's own findings, from the body, with no new citation.",
    "references": "List every source the body cites, in citation order.",
}


def plan_heading(item) -> str:
    """A plan section is an object with a heading. An older plan is a string."""
    if isinstance(item, dict):
        return str(item.get("heading") or "").strip()
    return str(item or "").strip()


def as_section(item, objective: str = "") -> dict:
    """One plan section, in object form.

    A string still parses, and carries no objective. The outline validator then
    names the missing field, which is a readable failure rather than a crash on
    an old plan.
    """
    if isinstance(item, dict):
        entry = dict(item)
        entry["heading"] = plan_heading(item)
        return entry
    return {"heading": plan_heading(item), "objective": objective}


def normalize_plan(plan: dict) -> dict:
    """Fill the defaults a later stage relies on, so it never reads a missing key."""
    plan.setdefault("title", "Untitled")
    plan.setdefault("audience", "practicing engineers")
    plan.setdefault("notes", [])
    plan.setdefault("diagrams", [])
    for index, question in enumerate(plan.get("questions", [])):
        question.setdefault("id", f"q{index + 1}")
        question.setdefault("subject", evidence.slug(question.get("question", "topic"), 30))
        question.setdefault("important", False)
    sections = [entry for entry in map(as_section, plan.get("sections", [])) if entry["heading"]]
    # Every white paper opens with an abstract and an introduction and closes
    # with references. A plan that omits one produces a paper that fails the
    # section gate at stage 8, four stages and several dollars too late.
    #
    # Position matters as much as presence. Inserting a missing Introduction at
    # the front of a plan that already has an Abstract puts the introduction
    # first, which is a different paper.
    #
    # Python inserts these three, so Python states their objective. Leaving it
    # blank would make the outline validator report a missing field against a
    # section the planner never wrote.
    lowered = [entry["heading"].lower() for entry in sections]
    if "abstract" not in lowered:
        sections.insert(0, as_section("Abstract", STRUCTURAL["abstract"]))
        lowered.insert(0, "abstract")
    if "introduction" not in lowered:
        sections.insert(
            lowered.index("abstract") + 1, as_section("Introduction", STRUCTURAL["introduction"])
        )
        lowered.insert(lowered.index("abstract") + 1, "introduction")
    # #478. Methods sits right after Introduction, the frozen heading
    # order's own position for it. Conclusion sits right before Next step,
    # the paper's own last prose heading (P4): second to last, never last.
    # A plan with no Next step section (an old fixture, or a test outline
    # that never calls `validate`) puts Conclusion right before References
    # instead, still ahead of Glossary and References.
    if "methods" not in lowered:
        sections.insert(
            lowered.index("introduction") + 1, as_section("Methods", STRUCTURAL["methods"])
        )
        lowered.insert(lowered.index("introduction") + 1, "methods")
    if "conclusion" not in lowered:
        if "next step" in lowered:
            insert_at = lowered.index("next step")
        elif "references" in lowered:
            insert_at = lowered.index("references")
        else:
            insert_at = len(sections)
        sections.insert(insert_at, as_section("Conclusion", STRUCTURAL["conclusion"]))
        lowered.insert(insert_at, "conclusion")
    if "references" not in lowered:
        sections.append(as_section("References", STRUCTURAL["references"]))
    plan["sections"] = sections
    return plan


# -- 2. search ------------------------------------------------------------

# A claim describes the world. These phrases describe the search instead, and
# a claim built out of one is a narrated retrieval miss, not a finding. The
# creatine paper this ticket names put two such sentences in the body, each
# `important: true`: "No arxiv.org source was found that reports a specific
# quantitative rate/magnitude of lean mass loss...". #469
RETRIEVAL_PHRASES = (
    "source was found",
    "could not be located",
    "via the search boundary",
    "search protocol",
)


def is_retrieval_claim(text: str) -> bool:
    """Whether a claim's text is about the search rather than the topic."""
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in RETRIEVAL_PHRASES)


def record_findings(
    ledger: evidence.Ledger,
    question: dict,
    reply: dict,
    *,
    seed: tuple[str, ...] | None = None,
    backend=None,
) -> evidence.Finding:
    """Turn one researcher reply into source, claim, and finding records.

    A claim with no source id is dropped here rather than carried forward. It
    cannot be corroborated, it cannot be cited, and keeping it only lets it
    reach the writer as something that looks like evidence.

    `backend` is the run's research backend, the same object `Paper.backend`
    holds. Passing it fetches the source's real title, authors, year, and
    venue through `metadata.fetch_record` before the source is admitted,
    which is what replaces the model's word with the record's. Leaving it
    `None`, as every test that does not care about metadata does, skips the
    fetch entirely and keeps the model's title exactly as before. #470

    A claim is also checked here against the text that fetch retrieved:
    `evidence.attributed()` requires the source's own quote (`body`, that
    source's entry in the researcher's reply) or every one of the claim's
    numbers to appear in it. A binding whose source text says something else
    is dropped; a claim left with no binding is dropped and recorded as a
    gap. A source with no fetched text (no `backend`, or the fetch found
    nothing) keeps every binding and the claim is noted `unattributed`,
    because there is nothing here to contradict, only nothing checked. #471
    """
    subject = question.get("subject", "topic")
    supplied_urls = [str(item.get("url", "")) for item in reply.get("sources", [])]
    # The allowlist has nothing to say about these, so the claim filter below
    # would drop every reference to one, and a claim that named only its
    # cabinet source would silently inherit every other source in the answer.
    located_urls = {
        str(item.get("url", "")).strip()
        for item in reply.get("sources", [])
        if str(item.get("located_from", "") or "")
    }
    allowlist = source_policy.merge_allowlist(
        supplied_urls, seed=seed if seed is not None else source_policy.SEED_ALLOWLIST
    )
    source_ids = []
    for item in reply.get("sources", []):
        url = str(item.get("url", "")).strip()
        located_from = str(item.get("located_from", "") or "")
        if located_from:
            # `paper._locate_cabinet_sources` cross-referenced a source the
            # cabinet already held. The librarian never admitted a domain for
            # it, because nobody asked the web for it, so the allowlist has
            # nothing to say. The bar is only that a reader can open it.
            if not (url.lower().startswith(("http://", "https://")) and source_policy.host(url)):
                continue
        elif not source_policy.url_allowed(url, allowlist):
            continue
        # `add_source` already dedupes by url, so a source this run already
        # admitted is also a fetch this run already paid for. One fetch per
        # unique URL per run falls out of the ledger's own dedup, no separate
        # cache required.
        existing = ledger.source_for_url(url)
        if existing is not None:
            source_ids.append(existing.id)
            continue
        model_title = item.get("title") or url
        fetched = (
            metadata.fetch_record(url, backend, model_title=model_title)
            if backend is not None
            else {}
        )
        source = ledger.add_source(
            evidence.SourceDocument(
                title=fetched.get("title") or model_title,
                url=url,
                subject=subject,
                vendor=item.get("vendor", ""),
                body=item.get("quote", ""),
                located_from=located_from,
                authors=fetched.get("authors") or [],
                year=fetched.get("year") or "",
                venue=fetched.get("venue") or "",
                note=fetched.get("note") or "",
                text=fetched.get("text") or "",
                # A dict lookup on the record's own publication type, never a
                # model's opinion. `{}` (no backend) tiers `other`, the same
                # as a fetch that found nothing. #473
                tier=source_policy.tier_for(fetched),
            )
        )
        source_ids.append(source.id)

    claim_ids = []
    gaps: list[str] = []
    for item in reply.get("claims", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if is_retrieval_claim(text):
            # Refused, not carried forward as a single-source claim about
            # nothing. The question this answer was for still has no finding,
            # which is a coverage gap, not evidence. #469
            gaps.append(text)
            continue
        # A claim may name its own subset of sources. When it names none, it
        # inherits every source this answer produced.
        named = [str(url).strip() for url in (item.get("source_urls") or [])]
        wanted = source_policy.filter_urls(named, allowlist)
        wanted += [url for url in named if url in located_urls and url not in wanted]
        ids = [
            sid
            for sid in source_ids
            if not wanted or any(ledger.sources[sid].url == url for url in wanted)
        ]
        if not ids:
            continue
        claim = evidence.Claim(
            text=text,
            subject=subject,
            source_ids=list(ids),
            confidence=float(item.get("confidence", 0.5)),
            important=bool(question.get("important")),
            study=item.get("study") or {},
        )
        # #471: a binding is only as good as the text fetched for its source.
        # A source with no fetched text (no backend, or the fetch found
        # nothing) keeps its binding unchecked rather than dropped.
        kept_ids: list[str] = []
        attributed_ids: list[str] = []
        unattributed_kept = False
        for sid in ids:
            source = ledger.sources[sid]
            if not source.text:
                kept_ids.append(sid)
                unattributed_kept = True
            # `source.body` is the researcher's own quote for this specific
            # binding, not a `"..."` substring pulled out of the claim's own
            # text: #471, finding 3.
            elif evidence.attributed(claim, source.text, quote=source.body):
                kept_ids.append(sid)
                attributed_ids.append(sid)
            # else: the source text does not back this claim. The binding is
            # dropped, silently at the binding level; only a claim left with
            # no binding at all is logged, below.
        if not kept_ids:
            gaps.append(f"dropped, no source attributes this claim: {text[:80]}")
            continue
        claim.source_ids = kept_ids
        claim.attributed_source_ids = attributed_ids
        if unattributed_kept:
            claim.note = "unattributed: attribution not checked"
        ledger.add_claim(claim)
        evidence.corroborate(claim)
        claim_ids.append(claim.id)

    return ledger.add_finding(
        evidence.Finding(
            question=question.get("question", ""),
            subject=subject,
            claim_ids=claim_ids,
            summary=reply.get("answer", ""),
            gaps=gaps,
        )
    )


def search_gate(ledger: evidence.Ledger, plan: dict, *, unmet: dict[str, str] | None = None) -> None:
    """Every question produced at least one cited claim, or the paper has no evidence.

    `unmet`, when given, is `Paper.evidence_shortfall_unmet`: question ids
    whose one `evidence_requirements` turn is already spent and the block
    is still short. Judge revision on #520, blocking finding 1: a question
    in `unmet` is accepted as a named gap, not failed again here, or a
    shortfall that survives its one turn would end the run instead of
    travelling as a gap the way the ticket and the plan both require.
    """
    if not ledger.claims:
        raise GateFailed(
            "no question produced a cited claim. Every claim needs a source URL.",
            ("no_claims",),
        )
    uncited = [claim.text[:50] for claim in ledger.claims.values() if not claim.cited]
    if uncited:
        raise GateFailed(
            f"these claims name no source: {uncited[:3]}. Drop them or find a source.",
            ("uncited_claim",),
        )
    important = [q for q in plan.get("questions", []) if q.get("important")]
    answered = {finding.subject for finding in ledger.findings.values() if finding.claim_ids}
    missing = [q["id"] for q in important if q.get("subject") not in answered]
    if missing:
        raise GateFailed(
            f"these important questions produced nothing: {missing}. "
            "Search again with narrower wording. A claim that no source exists "
            "is refused; name the coverage gap instead.",
            ("unanswered_important",),
        )
    unmet = unmet or {}
    shortfalls = []
    for question in important:
        if (question.get("id") or "") in unmet:
            continue
        # The doctrine question is a fact read from checked-in Python, not a
        # researched claim, whatever `evidence_requirements` a plan gives
        # it; `_research_shortfalls` already exempts it from a turn for the
        # same reason `stage_search`'s own repository shortcut does.
        if str(question.get("question", "")).strip() == EXIT_DOCTRINE_QUESTION:
            continue
        reason = evidence_shortfall(ledger, question)
        if reason:
            shortfalls.append(f"{question.get('id')}: {reason}")
    if shortfalls:
        raise GateFailed(
            f"evidence_requirements shortfall: {'; '.join(shortfalls)}. "
            "Search again for what is named missing.",
            ("evidence_requirements_met",),
        )


# -- 1b. evidence requirements, graded against the bound sources ----------
#
# #475. `search_gate` names the shortfall; `Paper._research_shortfalls`
# spends the one extra turn against it before the gate ever sees it.


def evidence_shortfall(ledger: evidence.Ledger, question: dict) -> str:
    """What a question's `evidence_requirements` block still needs against
    its own bound sources, or `""` when it is met. #475

    `study_types`/`min_count`: how many distinct sources bound to this
    question's own claims carry a tier (`source.tier`, from
    `source_policy.tier_for()`, never a note) in the required set. A
    source that is only there because a follow hit appended the primary
    study a review or preprint summarizes does not count on its own:
    `claim.via_source_ids` names it, excluded here the same way
    `evidence.corroborate` excludes it, so a review plus the primary it
    routes to is one source, not two. Judge revision on #520, blocking
    finding 4.

    `recency_years`, when given: a source with a year counts only inside
    the window. A source with no year does not satisfy a window: there is
    nothing here to confirm it is recent, so it is dropped from the count
    rather than assumed to qualify. Judge revision on #520, follow-up 2.

    `populations`: each named term must appear, word-bounded, in the
    pooled text of only the claims whose sources counted toward
    `min_count` -- a population named solely by a claim resting on a
    source the wrong tier, or outside the window, does not satisfy the
    requirement. Judge revision on #520, follow-up 4.

    An absent or empty block needs nothing: this is a grading function, not
    the hard requirement, which is `plan_gate`'s job.
    """
    reqs = question.get("evidence_requirements") or {}
    study_types = [str(t) for t in (reqs.get("study_types") or [])]
    min_count = int(reqs.get("min_count") or 0)
    if not study_types or min_count < 1:
        return ""
    subject = question.get("subject")
    claim_ids = {
        cid
        for finding in ledger.findings.values()
        if finding.subject == subject
        for cid in finding.claim_ids
    }
    claims = [ledger.claims[cid] for cid in claim_ids if cid in ledger.claims]
    via = {sid for claim in claims for sid in claim.via_source_ids}
    source_ids = {sid for claim in claims for sid in claim.source_ids} - via
    sources = [ledger.sources[sid] for sid in source_ids if sid in ledger.sources]

    recency_years = reqs.get("recency_years")
    this_year = datetime.now(timezone.utc).year

    def counts(source: evidence.SourceDocument) -> bool:
        if (source.tier or "") not in study_types:
            return False
        if not recency_years:
            return True
        year = str(source.year or "").strip()
        return year.isdigit() and int(year) >= this_year - int(recency_years)

    matched = [source for source in sources if counts(source)]
    if len(matched) < min_count:
        return f"needs {min_count} {'/'.join(sorted(set(study_types)))}, has {len(matched)}"

    matched_ids = {source.id for source in matched}
    pooled = " ".join(claim.text for claim in claims if set(claim.source_ids) & matched_ids)
    missing_populations = [
        population
        for population in (reqs.get("populations") or [])
        if not re.search(rf"\b{re.escape(str(population))}\b", pooled, re.I)
    ]
    if missing_populations:
        return f"no evidence found for population(s): {', '.join(missing_populations)}"
    return ""


# -- 2b. follow the summary to its primary ---------------------------------
#
# #473. A preprint's number is the least trustworthy citation in the paper; a
# systematic review's is closest to a primary trial's own. Lower sorts
# first, so a run past `--max-follow` spends its turns on the shakiest
# claims.
FOLLOW_TIER_ORDER = {
    "preprint_or_compilation": 0,
    "narrative_review": 1,
    "meta_analysis_or_systematic_review": 2,
}


def claims_needing_a_primary(ledger: evidence.Ledger) -> list[evidence.Claim]:
    """Numeric claims bound only to a review, a preprint, or a compilation.

    Shakiest tier first. A claim `apply_follow_result` already marked
    `secondary` is skipped, so a resumed run does not spend a second follow
    turn on the same miss.
    """
    candidates = []
    for claim in ledger.claims.values():
        if claim.secondary:
            continue
        if not re.search(r"\d", claim.text):
            continue
        tiers = [ledger.sources[sid].tier for sid in claim.source_ids if sid in ledger.sources]
        if tiers and all(tier in source_policy.SECONDARY_TIERS for tier in tiers):
            candidates.append(claim)
    return sorted(
        candidates,
        key=lambda c: min(
            FOLLOW_TIER_ORDER.get(ledger.sources[sid].tier, 9)
            for sid in c.source_ids
            if sid in ledger.sources
        ),
    )


def apply_follow_result(ledger: evidence.Ledger, claim: evidence.Claim, result: dict, *, backend=None) -> bool:
    """Rebind a claim to the primary a follow turn found, or mark it secondary.

    A hit only counts when the found source's own tier is not itself
    secondary: the same review answering twice, or a different review, must
    not clear the caveat (#473 item 2). `ledger.source_for_url` may hand
    back a source this run already tiered elsewhere; that existing tier is
    consulted the same way a freshly fetched one is.

    A hit whose fetched text contradicts the claim is treated the same as a
    miss: a primary study's own URL is not a licence to skip the check #471
    already runs on every other binding. The primary is appended to
    `source_ids`, never substituted, so a claim two secondaries already
    corroborated stays corroborated (item 5); `claim.note` is left alone,
    and a record with no fetched text is never marked attributed (item 4).

    The reviews already bound before this append are recorded on
    `claim.via_source_ids`: a review and the primary it was found to
    summarize are one investigation, and `evidence.corroborate` must not
    count both as independent of each other. #474 item 10
    """
    url = str(result.get("url") or "").strip()
    if result.get("found") and url.lower().startswith(("http://", "https://")):
        source = ledger.source_for_url(url)
        if source is None:
            model_title = result.get("title") or url
            fetched = metadata.fetch_record(url, backend, model_title=model_title) if backend is not None else {}
            source = ledger.add_source(
                evidence.SourceDocument(
                    title=fetched.get("title") or model_title,
                    url=url,
                    subject=claim.subject,
                    body=result.get("quote", ""),
                    authors=fetched.get("authors") or [],
                    year=fetched.get("year") or "",
                    venue=fetched.get("venue") or "",
                    note=fetched.get("note") or "",
                    text=fetched.get("text") or "",
                    tier=source_policy.tier_for(fetched),
                )
            )
        if source.tier not in source_policy.SECONDARY_TIERS and (
            not source.text or evidence.attributed(claim, source.text, quote=result.get("quote", ""))
        ):
            route = [sid for sid in claim.source_ids if sid != source.id]
            if source.id not in claim.source_ids:
                claim.source_ids.append(source.id)
            if source.text:
                if source.id not in claim.attributed_source_ids:
                    claim.attributed_source_ids.append(source.id)
            else:
                marker = "unattributed: attribution not checked"
                if marker not in (claim.note or ""):
                    claim.note = f"{claim.note}; {marker}" if claim.note else marker
            # Only when the primary traces to exactly one prior source: with
            # two or more already bound, which one this primary "is the
            # route of" is not something a claim-level follow turn ever
            # asked, and item 5's own claim (two secondaries already
            # corroborated stays corroborated) must not be disturbed by
            # excluding one of them from the count on a guess.
            if len(route) == 1 and route[0] not in claim.via_source_ids:
                claim.via_source_ids.append(route[0])
            claim.secondary = False
            evidence.corroborate(claim)
            return True
    claim.secondary = True
    return False


# -- 2c. the counter-evidence pass ------------------------------------------
#
# #474. A lever was ruled out from one datapoint (#474's own example:
# "protein alone did not prevent lean-mass loss" is true of one no-training
# protocol, not the literature). Word-bounded, so "alone" does not fire
# inside "standalone" and "never" does not fire inside "nevertheless": both
# words sit right against the boundary the regex tests, with no space or
# punctuation to trip it, and both correctly stay unmatched.
GENERALIZING = re.compile(r"\b(did not|does not|alone|fails to|no effect|always|never)\b", re.I)

# #474. What `claim_brief` shows a claim whose counter-evidence turn never
# ran: the cap reached it first, so the writer must hedge it the way a
# single-source claim already is, rather than stating it as settled.
CAPPED_NOTE = "counter-evidence not searched, run cap reached"


def generalizing_claims(ledger: evidence.Ledger) -> list[evidence.Claim]:
    """Claims whose text generalizes, shakiest first. #474

    A claim that already carries a `counter` state ("hit", "miss", or
    "capped") is excluded: the pass already reached a verdict on it, and a
    `stage_search` retry re-entering `Paper._counter_evidence` from the top
    must not ask it again.

    Single-source and secondary-tier claims sort first, then by fewest
    bindings (`len(claim.source_ids)`), the measure `verify_batch` already
    uses for its own shakiest-first order.

    No `claims_to_support` cross-reference here: this pass runs during
    `stage_search`, before the outline -- and its section-level
    `claims_to_support` -- exists. Port asymmetry, stated not hidden: the
    SDK twin runs its counter-evidence pass after its outline is approved
    and adds that second selection criterion, a claim that is the sole
    support for one of its section's `claims_to_support` entries.
    """
    candidates = [
        claim
        for claim in ledger.claims.values()
        if not claim.counter and GENERALIZING.search(claim.text)
    ]

    def sort_key(claim: evidence.Claim) -> tuple:
        single = claim.truth_state == evidence.SINGLE_SOURCE
        tiers = [ledger.sources[sid].tier for sid in claim.source_ids if sid in ledger.sources]
        secondary = bool(tiers) and all(tier in source_policy.SECONDARY_TIERS for tier in tiers)
        return (0 if single else 1, 0 if secondary else 1, len(set(claim.source_ids)))

    return sorted(candidates, key=sort_key)


def counter_evidence_for(ledger: evidence.Ledger, claim_id: str) -> evidence.Claim | None:
    """The claim that contradicts `claim_id`, or `None` when no counter
    turn found one. #474"""
    return next(
        (claim for claim in ledger.claims.values() if claim.counterargument_to == claim_id), None
    )


def apply_counter_result(
    ledger: evidence.Ledger, claim: evidence.Claim, result: dict, *, backend=None
) -> bool:
    """Record a counter-evidence turn's outcome on `claim.counter`. #474

    A dedicated field, not `note`: `apply_verification` overwrites `note` on
    its `disagreed` and `not_found` branches, and the verifier runs right
    after this pass on the live `STAGE_ORDER`, so a text marker in `note`
    was gone before the writer ever saw it. `apply_verification` never
    touches `counter` or `counter_note`.

    A hit adds a new claim, bound to its own source, `counterargument_to`
    pointing at the claim it contradicts. The original claim is left exactly
    as it stood: this is evidence for a condition, not a rebinding of it, the
    way `apply_follow_result` rebinds a claim to a primary it found.

    A hit whose fetched text does not back the model's own contrary claim,
    or whose contrary claim is itself a narrated retrieval miss ("no source
    was found", the same screen #469 already runs on the research path), is
    treated as a miss: a claim about the search is not evidence about the
    subject, and a primary study's own URL is not a licence to skip the
    check #471 already runs on every other binding.
    """
    url = str(result.get("url") or "").strip()
    counter_text = str(result.get("counter_claim") or "").strip()
    if (
        result.get("found")
        and counter_text
        and not is_retrieval_claim(counter_text)
        and url.lower().startswith(("http://", "https://"))
    ):
        source = ledger.source_for_url(url)
        if source is None:
            model_title = result.get("title") or url
            fetched = metadata.fetch_record(url, backend, model_title=model_title) if backend is not None else {}
            source = ledger.add_source(
                evidence.SourceDocument(
                    title=fetched.get("title") or model_title,
                    url=url,
                    subject=claim.subject,
                    body=result.get("quote", ""),
                    authors=fetched.get("authors") or [],
                    year=fetched.get("year") or "",
                    venue=fetched.get("venue") or "",
                    note=fetched.get("note") or "",
                    text=fetched.get("text") or "",
                    tier=source_policy.tier_for(fetched),
                )
            )
        counter_claim = evidence.Claim(
            text=counter_text,
            subject=claim.subject,
            source_ids=[source.id],
            counterargument_to=claim.id,
        )
        if not source.text or evidence.attributed(counter_claim, source.text, quote=result.get("quote", "")):
            counter_claim.attributed_source_ids = [source.id] if source.text else []
            ledger.add_claim(counter_claim)
            evidence.corroborate(counter_claim)
            claim.counter = "hit"
            return True
    claim.counter = "miss"
    claim.counter_note = "no contrary evidence found in this search"
    return False


# How many claims one verify stage will cross-check.
#
# The verifier searches for each claim it is handed, so the size of this list is
# the size of the work. Handing it every important claim is how four research
# questions became a hundred and eleven verification turns in a live run: the
# stage had no upper bound at all, and neither the money cap nor the turn cap
# was checked until it finished.
#
# Twenty-four is a working default, not a discovered constant. Raise it with
# `--max-verify` when a paper genuinely rests on more than that many load-bearing
# facts, and expect the bill to scale with it.
#
# This cap bounds the model verifier turn only. `attributed()` in
# `record_findings` runs on every claim, `important` or not, because it is a
# fetch and a substring check, not a search: the creatine bug's references 18
# and 20 were `important: false` and never reached this list at all. #471
MAX_VERIFY_CLAIMS = 24


def verify_batch(ledger: evidence.Ledger, limit: int = MAX_VERIFY_CLAIMS):
    """Split important claims into the ones to check and the ones to skip.

    The shakiest go first: lowest confidence, then fewest sources. A cap that
    took claims in whatever order the dictionary held them would spend the
    budget confirming the facts nobody doubted.
    """
    pending = [claim for claim in ledger.important() if not claim.cross_checked]
    ranked = sorted(pending, key=lambda claim: (claim.confidence, len(set(claim.source_ids))))
    return ranked[:limit], ranked[limit:]


def note_uncrosschecked(skipped: list) -> None:
    """Say in the record that these were never looked at twice.

    Silence would read as a pass. The truth state still reflects the sources the
    claim has, because that count did not change, but `cross_checked` stays
    false and the note says why.
    """
    for claim in skipped:
        evidence.corroborate(claim)
        if not claim.note:
            claim.note = (
                f"Not cross-checked. This run verified the {MAX_VERIFY_CLAIMS} least "
                "certain claims and this was not among them."
            )


# A recorded reply cannot name a claim id, because ids are minted at run time.
# It names `*subject*N` instead, meaning the Nth claim recorded for that subject.
PLACEHOLDER = re.compile(r"\*([\w-]+)\*(\d+)")


def resolve_placeholders(data, ledger: evidence.Ledger):
    """Swap `*subject*N` for the real claim id, anywhere in a recorded reply.

    Only the fixture runner produces these. A live model names real ids, which
    contain no asterisks, so this is a no-op on a live run rather than a branch
    the live path has to know about.
    """
    by_subject: dict[str, list[str]] = {}
    for claim in ledger.claims.values():
        by_subject.setdefault(claim.subject, []).append(claim.id)

    def swap(text: str) -> str:
        def one(match: re.Match) -> str:
            ids = by_subject.get(match.group(1), [])
            index = int(match.group(2))
            return ids[index] if index < len(ids) else match.group(0)

        return PLACEHOLDER.sub(one, text)

    if isinstance(data, str):
        return swap(data)
    if isinstance(data, list):
        return [resolve_placeholders(item, ledger) for item in data]
    if isinstance(data, dict):
        return {key: resolve_placeholders(value, ledger) for key, value in data.items()}
    return data


# -- 3. verify ------------------------------------------------------------


def apply_verification(ledger: evidence.Ledger, report: dict, *, backend=None) -> dict:
    """Fold the verifier's report into truth states. Python counts, not the model.

    The verifier says `agreed`, `disagreed`, or `not_found`. This function turns
    that into a truth state by counting attributed source ids (`corroborate()`,
    #471), which is why a verifier that says `agreed` twice about the same URL
    cannot promote a claim.

    `backend` is the run's research backend, the same object `stage_search`
    already passes to `record_findings`. An `agreed` verdict's second source
    is fetched through it, same as any other source, so its title, authors,
    year, and venue come from the record rather than sixty characters of the
    verifier's own quote. Leaving it `None` keeps the old behaviour. #471
    """
    counts = {"corroborated": 0, "single_source": 0, "contradicted": 0, "unknown": 0}
    for row in report.get("checked", []):
        claim = ledger.claim(row.get("claim_id", ""))
        if claim is None:
            counts["unknown"] += 1
            continue
        claim.cross_checked = True
        status = row.get("corroborate_status")
        if status == "agreed":
            url = str(row.get("second_source_url", "")).strip()
            if url.lower().startswith(("http://", "https://")):
                source = ledger.source_for_url(url)
                if source is None:
                    model_title = row.get("quote", "")[:60] or url
                    fetched = (
                        metadata.fetch_record(url, backend, model_title=model_title)
                        if backend is not None
                        else {}
                    )
                    source = ledger.add_source(
                        evidence.SourceDocument(
                            title=fetched.get("title") or model_title,
                            url=url,
                            subject=claim.subject or "verification",
                            body=row.get("quote", ""),
                            authors=fetched.get("authors") or [],
                            year=fetched.get("year") or "",
                            venue=fetched.get("venue") or "",
                            note=fetched.get("note") or "",
                            text=fetched.get("text") or "",
                            tier=source_policy.tier_for(fetched),
                        )
                    )
                if source.id not in claim.source_ids:
                    claim.source_ids.append(source.id)
                # The verifier independently searched for and quoted this
                # source. That is the second, independent look `attributed()`
                # exists to stand in for when nobody else already gave one.
                if source.id not in claim.attributed_source_ids:
                    claim.attributed_source_ids.append(source.id)
            evidence.corroborate(claim)
        elif status == "disagreed":
            claim.note = row.get("quote", "a second source disagreed")
            evidence.corroborate(claim, contradicted=True)
        else:
            # Silence is not a result. `not_found` still names what was
            # tried, so a reader sees a search happened rather than nothing
            # at all. #471
            queries = list(row.get("queries_used") or []) or [claim.text[:80]]
            claim.note = f"not_found: the verifier searched {queries} and found no second source."
            evidence.corroborate(claim)
        counts[claim.truth_state] = counts.get(claim.truth_state, 0) + 1
    return counts


def verify_gate(ledger: evidence.Ledger) -> None:
    """Every important claim carries a decided truth state.

    A contradicted claim is not a gate failure. It is a result, and the writer
    is simply not allowed to use it. What fails the gate is an important claim
    the verifier never looked at, because that is silence being read as consent.
    """
    undecided = [
        claim.text[:50] for claim in ledger.important() if claim.truth_state == evidence.PROPOSED
    ]
    if undecided:
        raise GateFailed(
            f"these important claims were never checked: {undecided[:3]}. "
            "Check each one against a second, independent source.",
            ("unchecked_important",),
        )
    # A claim past the cap may go through, but only because the record says
    # nobody looked at it twice. A silent skip reads exactly like a pass.
    silent = [claim.text[:50] for claim in ledger.unchecked() if not claim.note]
    if silent:
        raise GateFailed(
            f"these important claims were skipped without a note: {silent[:3]}. "
            "A skipped check must say it was skipped.",
            ("silent_skip",),
        )
    if not any(claim.usable for claim in ledger.claims.values()):
        raise GateFailed(
            "every claim is contradicted or uncited. There is nothing to write.",
            ("nothing_usable",),
        )


# -- 4. outline -----------------------------------------------------------


def outline_gate(outline: dict, ledger: evidence.Ledger, plan: dict) -> None:
    """Every section names claim ids that exist and may be used."""
    misses = []
    sections = outline.get("sections") or []
    if not sections:
        raise GateFailed("the outline has no sections.", ("no_sections",))

    required = {plan_heading(item).lower() for item in plan.get("sections", [])}
    present = {str(section.get("heading", "")).lower() for section in sections}
    for name in ("abstract", "introduction", "methods", "conclusion", "references"):
        if name in required and not any(name in heading for heading in present):
            misses.append(f"the outline is missing the {name} section.")

    for section in sections:
        heading = section.get("heading", "?")
        ids = section.get("claim_ids") or []
        # References is generated from the ledger, and the abstract summarizes
        # claims the body already cites. Neither needs its own binding.
        if heading.lower() in UNBOUND_SECTIONS:
            continue
        if not ids:
            misses.append(f"section {heading!r} names no claim ids.")
            continue
        for claim_id in ids:
            claim = ledger.claim(claim_id)
            if claim is None:
                misses.append(f"section {heading!r} names {claim_id}, which does not exist.")
            elif not claim.usable:
                misses.append(
                    f"section {heading!r} names {claim_id}, which is contradicted or uncited."
                )
    if misses:
        raise GateFailed(" ".join(misses[:6]), ("outline_binding",))


# -- 5. diagram -----------------------------------------------------------


# #514: the exact text `stage_diagram` matches to tell a live-call failure,
# on an available renderer, apart from every other complaint this loop can
# produce.
BACKEND_FAILURE_MARK = "image backend unavailable: "


def render_figures(src_dir: Path, out_dir: Path, topic: str, **kwargs) -> tuple[list, list[str]]:
    """Render every source through imagen-diagrams and its fidelity judge.

    A complexity failure is not an exception here. It is a message for the
    diagrammer, and the caller feeds it straight back as the retry prompt.

    A renderer that is genuinely absent propagates immediately: `available()`
    already said no, every figure would fail the identical way, and there is
    no SVG fallback to ship instead (#409's `test_a_missing_image_backend_
    blocks_the_paper`). A renderer that reported itself available and then
    had one live call fail (auth, quota, a transient error) is different:
    #514 traced a whole run crashing over one bad live call, so that one
    complaint is marked with the caller's own text and this loop keeps
    going. `stage_diagram` reads the mark and drops just that figure.
    """
    figures, complaints = [], []
    if not src_dir.is_dir():
        return figures, ["no diagram sources were written."]
    for path in sorted(src_dir.iterdir()):
        if path.suffix.lower() not in diagrams.MERMAID_SUFFIXES + diagrams.PLANTUML_SUFFIXES:
            continue
        try:
            figure = diagrams.render(path, out_dir, topic=topic, **kwargs)
            figures.append(figure)
            if figure.misses:
                complaints.append(
                    f"{path.name}: imagen-diagrams fidelity miss: {'; '.join(figure.misses)}"
                )
        except diagrams.DiagramTooComplex as exc:
            complaints.append(f"{path.name}: {exc}")
        except diagrams.ImageBackendUnavailable as exc:
            if not diagrams.available():
                raise
            complaints.append(f"{path.name}: {BACKEND_FAILURE_MARK}{exc}")
    return figures, complaints


def diagram_gate(figures: list, complaints: list[str], planned: list[dict]) -> None:
    if complaints and any("nodes. A figure carries at most" in c for c in complaints):
        raise GateFailed(" ".join(complaints), ("too_complex",))
    if planned and not figures:
        raise GateFailed(
            f"the plan asked for {len(planned)} figures and none rendered. "
            + " ".join(complaints[:3]),
            ("no_figures",),
        )
    expected = {evidence.slug(str(item.get("name", ""))) for item in planned}
    actual = {figure.name for figure in figures}
    missing = sorted(expected - actual)
    if missing:
        raise GateFailed(
            f"the plan asked for figures that did not render: {', '.join(missing)}. "
            + " ".join(complaints[:3]),
            ("missing_figures",),
        )
    missing_alt = [figure.name for figure in figures if not figure.alt.strip()]
    if missing_alt:
        raise GateFailed(f"these figures have no alt text: {missing_alt}.", ("no_alt",))
    rejected = [figure.name for figure in figures if figure.best is None]
    if rejected:
        raise GateFailed(
            f"imagen-diagrams did not approve these publication PNGs: {rejected}. "
            + " ".join(complaints[:3]),
            ("figure_fidelity",),
        )


# -- 6. write -------------------------------------------------------------


def numbering(ledger: evidence.Ledger) -> tuple[dict[str, int], list[str]]:
    """Map every cited source to a stable reference number.

    Assigned once, in bibliography order, before the writer sees anything. A
    number that shifts between sections is how `[3]` ends up pointing at the
    wrong paper.
    """
    urls: list[str] = []
    index: dict[str, int] = {}
    for source in ledger.bibliography():
        urls.append(source.url)
        index[source.id] = len(urls)
    return index, urls


def claim_brief(ledger: evidence.Ledger, claim_id: str, index: dict[str, int]) -> str:
    """One claim, rendered for the writer, with its numbers already resolved."""
    claim = ledger.claim(claim_id)
    if claim is None:
        return ""
    markers = "".join(f"[{index[sid]}]" for sid in claim.source_ids if sid in index)
    caveat = ""
    if claim.truth_state == evidence.SINGLE_SOURCE:
        caveat = "  (SINGLE SOURCE. Say so in the paragraph that uses this.)"
    if claim.secondary:
        # #473. A follow turn found no primary, so the writer is told
        # outright: this number is as summarized by the review or preprint
        # bound here, not the primary study's own report. A dedicated field,
        # not `note`: `apply_verification` still owns that one.
        caveat += f"  (as summarized by {markers}. Say so in the paragraph that uses this.)"
    # #474. A hit names the contrary claim and its own numbers, so the
    # writer sees claim and counter-evidence together in one brief line. A
    # miss says so outright. A claim the run cap reached before its turn is
    # told to hedge, the same instruction a single-source claim already
    # gets. The writer card carries the one instruction to state the
    # condition a hit holds under, so that is not repeated here.
    if claim.counter == "hit":
        countered = counter_evidence_for(ledger, claim.id)
        if countered is not None:
            counter_markers = "".join(f"[{index[sid]}]" for sid in countered.source_ids if sid in index)
            caveat += f"  (Contrary evidence {counter_markers}: {countered.text})"
    elif claim.counter == "miss":
        caveat += f"  ({claim.counter_note or 'no contrary evidence found in this search'}.)"
    elif claim.counter == "capped":
        caveat += (
            f"  ({claim.counter_note or CAPPED_NOTE}. "
            "Hedge this the way a single-source claim is hedged.)"
        )
    return f"- {claim.id}: {claim.text} {markers}{caveat}"


def write_gate(section: str, body: str, allowed: list[int]) -> None:
    """Every factual paragraph cites only the numbers its claims gave it."""
    if not body.strip():
        raise GateFailed(f"section {section!r} came back empty.", ("empty_section",))
    used = {int(marker) for marker in CITATION.findall(body)}
    stray = sorted(used - set(allowed))
    if stray:
        raise GateFailed(
            f"section {section!r} cites {stray}, which its claims do not support. "
            f"Use only these markers: {sorted(allowed)}.",
            ("stray_citation",),
        )
    if allowed and not used:
        raise GateFailed(
            f"section {section!r} cites nothing. Every paragraph that asserts a "
            "fact carries a marker.",
            ("no_citation",),
        )
    uncited = brief.uncited_claims(body)
    if uncited:
        raise GateFailed(
            f"section {section!r} has uncited prose paragraphs: {uncited[:2]}. "
            "Put an allowed marker in every paragraph that makes a factual claim.",
            ("uncited_paragraph",),
        )
    words = len(re.findall(r"\b[\w'-]+\b", body))
    if words < paper_check.MIN_SECTION_WORDS:
        raise GateFailed(
            f"section {section!r} is {words} words. Unpack the bound claims into "
            f"at least {paper_check.MIN_SECTION_WORDS} words of mechanism, tradeoff, "
            "and evidence limit. Do not invent facts.",
            ("thin_section",),
        )


def drop_uncited_prose(body: str) -> str:
    """Remove model-added prose that has no traceable source.

    This never invents a marker or attaches a convenient source to unsupported
    framing. The raw writer response is preserved in diagnostics before this
    filter runs, and the remaining body still has to pass every paper gate.
    """
    return "\n\n".join(
        block.strip()
        for block in body.split("\n\n")
        if block.strip() and not brief.uncited_claims(block)
    )


def define_acronym_once(sections: dict[str, str], phrase: str, acronym: str) -> dict[str, str]:
    """Define an acronym at its first use and collapse later redefinitions."""
    definition = f"{phrase} ({acronym})"
    definition_re = re.compile(rf"\b{re.escape(phrase)}\s*\({re.escape(acronym)}\)", re.I)
    acronym_re = re.compile(rf"\b{re.escape(acronym)}\b")
    seen = False
    normalized: dict[str, str] = {}
    for heading, body in sections.items():
        if seen:
            normalized[heading] = definition_re.sub(acronym, body)
            continue
        defined = definition_re.search(body)
        used = acronym_re.search(body)
        if defined is not None and (used is None or defined.start() <= used.start()):
            end = defined.end()
            normalized[heading] = body[:end] + definition_re.sub(acronym, body[end:])
            seen = True
        elif used is not None:
            expanded = body[: used.start()] + definition + body[used.end() :]
            first_end = used.start() + len(definition)
            normalized[heading] = expanded[:first_end] + definition_re.sub(acronym, expanded[first_end:])
            seen = True
        else:
            normalized[heading] = body
    return normalized


# -- 7. review ------------------------------------------------------------


def _split_verdict(verdict: dict) -> tuple[list[str], list[str], float | None]:
    """Read either reply shape the reviewer skill may hand back.

    Paired: `{"failed_rows": [{"row": "no_filler", "note": "..."}], "score": 0.7}`.
    The row and its note travel together, so they can never drift apart the
    way the flat shape's two parallel lists could (#411).

    Legacy: `{"failed_rows": ["no_filler"], "notes": ["..."]}`, with no score.
    Still accepted, so an older recorded reply still parses.
    """
    raw_rows = verdict.get("failed_rows")
    # A schema violation from a live model, not a Python type Python chose.
    # Treat anything that is not a list as no failing rows rather than crash.
    raw_rows = raw_rows if isinstance(raw_rows, list) else []
    score = verdict.get("score")
    try:
        score = None if score is None else max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        score = None
    # Checked per item, not by peeking at the first one: a reviewer that
    # names one row in the paired shape and one in the legacy shape in the
    # same reply must not crash `_run_stage` with an `AttributeError` on the
    # bare string or a `KeyError` on the dict.
    if any(isinstance(item, dict) for item in raw_rows):
        rows = [
            str(item.get("row", "")).strip() if isinstance(item, dict) else str(item).strip()
            for item in raw_rows
        ]
        notes = [
            str(item.get("note", "")).strip() if isinstance(item, dict) else ""
            for item in raw_rows
        ]
        return rows, notes, score
    rows = [str(row) for row in raw_rows]
    notes = [str(note) for note in (verdict.get("notes") or []) if str(note).strip()]
    return rows, notes, score


def review_gate(verdict: dict) -> None:
    """Fail the draft on the reviewer's rows, and never mislabel one.

    This string becomes the writer's revision instruction, so a wrong pairing
    is not cosmetic: the writer is told a row failed for a reason belonging to
    another row, the real defect is described to nobody, and the row fails
    again. A live run stalled that way with `scope_honest` labelled
    "evidence_matches is now fixed" (#326).

    The paired reply shape pairs every row with its note by construction. The
    legacy flat shape does not, so pair its two lists only when the counts
    agree; when they do not, report both lists plainly rather than guessing
    which sentence belongs to which row.
    """
    rows, notes, score = _split_verdict(verdict)
    if not rows:
        return
    if len(notes) == len(rows):
        detail = " ".join(f"{row}: {note}" for row, note in zip(rows, notes, strict=True))
    else:
        listed = ", ".join(rows)
        detail = f"failed rows: {listed}."
        if notes:
            detail += (
                f" The reviewer returned {len(notes)} notes for {len(rows)} rows, so"
                " they are not matched up. All of them: " + " ".join(notes)
            )
    raise GateFailed(f"the reviewer failed these rows. {detail}", tuple(sorted(rows)), score=score)


# -- 8. assemble ----------------------------------------------------------


def figure_block(figure, number: int, figures_dir: str = "figures") -> str:
    """The image line and its `Figure N.` caption, from the figure's own
    alt text. #413, #464.
    """
    target = figure.best
    if target is None or not target.name.endswith("_imagen.png"):
        raise GateFailed(
            f"figure {figure.name!r} has no judged imagen-diagrams PNG.",
            ("figure_asset",),
        )
    return f"![{figure.alt}]({figures_dir}/{target.name})\n\nFigure {number}. {figure.alt}"


def render_reference(source: evidence.SourceDocument) -> str:
    """One reference line: "Authors (year). Title. Venue. URL."

    Every field is optional and falls back field by field, down to the bare
    URL when `metadata.fetch_record` found nothing at all. #470
    """
    title = source.title.strip() or ""
    authors = [str(a).strip() for a in (source.authors or []) if str(a).strip()]
    year = str(source.year or "").strip()
    venue = str(source.venue or "").strip()

    lead = ", ".join(authors)
    if year:
        lead = f"{lead} ({year})" if lead else f"({year})"

    parts = [part for part in (lead, title, venue) if part]
    if not parts:
        return source.url
    text = ". ".join(parts)
    if not text.endswith("."):
        text += "."
    return f"{text} {source.url}"


def references_block(urls: list[str], sources: list) -> str:
    rows = ["## References", ""]
    for number, source in enumerate(sources, start=1):
        rows.append(f"{number}. {render_reference(source)}")
    if not sources:
        rows += [f"{n}. {url}" for n, url in enumerate(urls, start=1)]
    return "\n".join(rows) + "\n"


def front_matter_block(
    ledger: evidence.Ledger,
    *,
    prepared_at: str,
    conflicts: str | None = None,
) -> str:
    """Byline, date, provenance, and conflicts, written above the Abstract.

    The byline names every role's own model straight from `roleplan`, so a
    reader never sees a name this run did not actually use. The provenance
    counts come from the same ledger `Paper._methods_lines` reads: sources
    retrieved, sources cited (the bibliography this run actually built), and
    claims a verifier actually cross-checked (`Claim.cross_checked`, set
    only by a real second look, distinct from a corroborated truth state).
    #479
    """
    roles = roleplan.plan(None, "paper")
    models = ", ".join(f"{name}: {role.model}" for name, role in roles.items())
    retrieved = len(ledger.sources)
    cited = len(ledger.bibliography())
    checked = sum(1 for claim in ledger.claims.values() if claim.cross_checked)
    conflicts = conflicts if conflicts is not None else (os.environ.get("CONFLICTS") or DEFAULT_CONFLICTS)
    return "\n\n".join(
        [
            f"Prepared by: {HARNESS_NAME} ({models}).",
            f"Date: {prepared_at}.",
            f"Generated by an automated research loop. Sources: {retrieved} retrieved, "
            f"{cited} cited. Verification: {checked} claims cross-checked. See Methods.",
            conflicts,
        ]
    )


def study_table(
    ledger: evidence.Ledger, index: dict[str, int], written: dict[str, str] | None = None
) -> str:
    """The Evidence summary table, or "" when the ledger holds no
    human-study claim. Python from the ledger: one row per usable claim
    that carries E3's `study` object, reading E4's `SourceDocument.tier`
    for its own source. Not deduped by study identity: two claims about
    the same trial are two citations already, the same way the reference
    list treats them. #478

    `written`, when given, is `self.written`: every body section's own
    final text, already carrying the writer's own `[N]` markers. A claim
    with a reference number is not proof any section's prose used it,
    PR #535 judge revision F7, so a claim renders here only when at least
    one of its own source numbers is a marker some section actually wrote.
    `None` skips the filter, for a caller with no written body yet.
    """
    cited_numbers = (
        {int(n) for n in re.findall(r"\[(\d+)\]", "\n".join(written.values()))}
        if written is not None
        else None
    )
    rows = [
        claim
        for claim in ledger.claims.values()
        if claim.usable
        and claim.study
        and (
            cited_numbers is None
            or any(index.get(sid) in cited_numbers for sid in claim.source_ids)
        )
    ]
    if not rows:
        return ""
    lines = [
        "## Evidence summary",
        "",
        "| Participants | Duration | Deficit | Training | Assay | Result | Tier |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for claim in rows:
        study = claim.study or {}
        participants = study.get("participants") or {}
        n = participants.get("n")
        population = str(participants.get("population") or "").strip()
        who = f"{n} ({population})" if n and population else str(n or population or "not reported")
        duration = str(study.get("duration") or "not reported")
        deficit = str(study.get("deficit") or "not reported")
        training = study.get("training")
        training_cell = "yes" if training is True else "no" if training is False else "not reported"
        assay = str(study.get("assay") or "not reported")
        result = str(study.get("result") or claim.text or "not reported")
        tier = "other"
        for source_id in claim.source_ids:
            source = ledger.sources.get(source_id)
            if source is not None and source.tier:
                tier = source.tier
                break
        markers = "".join(f"[{index[sid]}]" for sid in claim.source_ids if sid in index)
        lines.append(
            f"| {who} | {duration} | {deficit} | {training_cell} | {assay} | "
            f"{result} {markers} | {tier} |"
        )
    lines.append("")
    return "\n".join(lines)


def assemble(
    plan: dict,
    outline: dict,
    written: dict[str, str],
    figures: list,
    ledger: evidence.Ledger,
    charts: list | None = None,
    skipped_figures: list[dict] | None = None,
    front_matter: str = "",
) -> str:
    """Stitch the paper. Pure Python, deterministic, no model call.

    Figures land under the section that asked for them, after its prose. The
    glossary and the references section are both generated, never written by
    the model: a generated bibliography cannot cite a source that was not
    retrieved, and a generated glossary cannot list a term the body never
    marked.
    """
    index, urls = numbering(ledger)
    # #478. Python, from the ledger: one row per human-study claim, spliced
    # in right after Methods, below. "" when the ledger holds none, and the
    # note that says so lives in Methods' own body, `Paper.stage_assemble`.
    table_block = study_table(ledger, index, written)
    by_name = {figure.name: figure for figure in figures}
    used_figures: set[str] = set()
    charts = [item for item in (charts or []) if item.get("path")]
    glossary: dict[str, str] = {}
    # #464. One counter, spent as charts and diagrams are placed, body
    # order, contiguous from one. A chart and a diagram share the same
    # sequence: a reader counts figures on the page, not by kind.
    figure_number = 0
    skips = list(skipped_figures or [])
    noted_skips: set[int] = set()
    # #464 B1. A rendered figure no planned section names can never receive
    # an in-text mention: the whole-paper pass only edits a planned
    # section's own text. That figure is a named skip, not an orphan
    # `## Figures` block the pass cannot write into. Attributed to the
    # first planned section, or "methods" when the outline has none.
    all_names = {
        name for section in outline.get("sections", []) for name in (section.get("figures") or [])
    }
    sections_list = outline.get("sections", [])
    fallback_section = (
        str(sections_list[0].get("id") or sections_list[0].get("heading") or "")
        if sections_list
        else "methods"
    )
    for name, figure in by_name.items():
        if name not in all_names:
            skips.append({"name": figure.name, "section": fallback_section, "reason": "no owning section"})

    parts = [f"# {plan.get('title', 'Untitled')}", ""]
    if front_matter:
        # #479. The byline, date, provenance, and conflicts, above the Abstract.
        parts.append(front_matter)
        parts.append("")
    for section in outline.get("sections", []):
        heading = str(section.get("heading", "")).strip()
        if heading.lower() == "references":
            continue
        parts.append(f"## {heading}")
        parts.append("")
        body = written.get(heading, "").strip()
        # First use wins. A term marked twice keeps the sentence that
        # introduced it, not a later restatement.
        body, term_hits = paper_check.take_terms(body)
        body = body.strip()
        for term, definition in term_hits:
            glossary.setdefault(term, definition)
        if body:
            parts.append(body)
            parts.append("")
        if heading.lower() == "methods" and table_block:
            parts.append(table_block)
            parts.append("")
        sid = str(section.get("id") or "")
        for chart in charts:
            owner = chart.get("section") or ""
            if owner not in (sid, heading):
                continue
            rel = f"charts/{Path(chart['path']).name}"
            caption = chart.get("caption") or chart.get("name") or rel
            # #464 B2. The number is spent for every placed figure, whether
            # this call writes the image line fresh or the line already
            # sits in `body` from a persisted trim: a slot the counter
            # does not charge is a slot the next figure duplicates.
            figure_number += 1
            if rel not in (body or ""):
                parts.append(f"![{caption}]({rel})")
                parts.append("")
                parts.append(f"Figure {figure_number}. {caption}")
                parts.append("")
        for name in section.get("figures", []) or []:
            figure = by_name.get(name)
            if figure is not None and name not in used_figures:
                figure_number += 1
                parts.append(figure_block(figure, figure_number))
                parts.append("")
                used_figures.add(name)
        # #386, #464. A skip is not silence: it is named, with its reason,
        # under the section that asked for it. A blockquote so `cited`
        # never reads it as an unsourced claim, the same free ride an
        # image's own caption paragraph already gets.
        for skip in skips:
            if skip.get("section") not in (sid, heading) or id(skip) in noted_skips:
                continue
            noted_skips.add(id(skip))
            parts.append(f"> {skip['name']} was not shown: {skip['reason']}.")
            parts.append("")

    # A skip with no owning section (an empty `section`, or one that never
    # matched a planned section id) still gets a note, not silence, just
    # not one a specific section can claim.
    for skip in skips:
        if id(skip) in noted_skips:
            continue
        parts.append(f"> {skip['name']} was not shown: {skip['reason']}.")
        parts.append("")

    # No captured term means no section, not an empty one. Alphabetical, case
    # insensitive, so "Loop" and "loop" do not sort by accident of case.
    if glossary:
        parts.append("## Glossary")
        parts.append("")
        for term in sorted(glossary, key=str.casefold):
            parts.append(f"**{term}.** {glossary[term]}")
            parts.append("")

    parts.append(references_block(urls, ledger.bibliography()))
    return "\n".join(parts).replace("\n\n\n", "\n\n")


def assemble_gate(
    body: str,
    ledger: evidence.Ledger,
    charts: list | None = None,
    allowed_domains: tuple[str, ...] | None = None,
    *,
    loop_doctrine: bool = True,
    outline: dict | None = None,
    skipped_figures: list[dict] | None = None,
) -> paper_check.PaperScore:
    _, urls = numbering(ledger)
    score = paper_check.check(
        body,
        urls,
        ledger=ledger,
        charts=charts,
        allowed_domains=allowed_domains,
        enforce_structure=True,
        located=[source.url for source in ledger.bibliography() if source.located_from],
        loop_doctrine=loop_doctrine,
        # The plan carries `key_questions` per section, the same shape the
        # SDK's `approved_outline(run)` hands to `checks.check`. #463: with
        # no outline, `question_heading` only catches a heading ending in
        # "?"; this lets it also catch a heading that repeats a key
        # question verbatim without the question mark.
        outline=outline,
        skipped_figures=skipped_figures,
    )
    if not score.passed:
        raise GateFailed(
            "the paper failed its hard gates.\n" + score.report(),
            score.signature(),
        )
    return score
