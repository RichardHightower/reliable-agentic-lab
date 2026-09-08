"""Per-section write, check, judge, and ledger.

Python holds the loop. Search and verify stay bulk stages; this module
closes each written section: findings from the bound claims, a deterministic
check, a read-only section judge, and a ledger entry. A finished section's
files are the skip key.

The writer is the only role that writes prose. Findings, verdicts, and the
ledger are Python-written files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import evidence
import paper_check
from paper_check import Check, PaperScore

STUB = re.compile(r"\bTODO\b|\[placeholder\]|lorem ipsum", re.I)
CITATION = re.compile(r"\[(\d+)\]")
EM_DASH = re.compile(r"\s*—\s*")
SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.I)
RHETORICAL = re.compile(r"\?\s*$")
# #510. A judge on PR #508 scored the #385 gist question "Which trace
# counts were reported by the MAST taxonomy paper?" as answered by a body
# that shares only "paper" with it, because this list missed ordinary
# function words: `was`, `were`, `which`, `when`, `has`, `not`, `also`,
# `more`, `should`. `paper_check.STE_FUNCTION_WORDS` already names every
# one of those.
#
# It also names `run`, `calls`, `names`, `uses`, and `holds`, the STE-S5
# noun-stack row's own verb-suffix exceptions, not a question's function
# words. This repo's own papers are about a loop that runs, a section that
# calls a turn, a term a glossary names: a coverage row that stops those
# words scores a question about them on almost nothing. A judge on PR #529
# found exactly that on the SDK twin: "How many tool calls does a run use
# before it holds?" fell to one content term. `_COVERAGE_VERB_EXCEPTIONS`
# is that verb block, subtracted back out, so a domain verb stays a
# content word here even though it is not one for the noun-stack row it
# was written for. Copied from the SDK port, not imported.
_COVERAGE_VERB_EXCEPTIONS = frozenset(
    """
    run runs use uses need needs want wants show shows name names hold holds
    take takes give gives get gets know knows see sees say says call calls
    make makes made
    """.split()
)
STOP = paper_check.STE_FUNCTION_WORDS - _COVERAGE_VERB_EXCEPTIONS

SLOT_BUDGETS = (
    ("register", 2500),
    ("outline", 8000),
    ("ledger", 4000),
    ("previous", 4000),
    ("findings", 8000),
    ("retry", 1500),
)

REGISTER = """Write like a specification, not like a blog post.
Lead with the finding. Mechanism, alternative and its cost, then the limit
of the evidence. Three to eight paragraphs per key question.
No second person. No metaphor. No em dash. Cite by number.
"""


def _cut(text: str, budget: int) -> tuple[str, int]:
    if len(text) <= budget:
        return text, 0
    return text[:budget].rsplit("\n", 1)[0] or text[:budget], len(text) - budget


def assemble_context(
    *,
    outline: dict,
    ledger: list,
    previous: str,
    findings: list,
    retry: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Named slots with per-slot character budgets. Returns slots and cut log."""
    raw = {
        "register": REGISTER,
        "outline": json.dumps(outline, indent=2),
        "ledger": json.dumps(ledger, indent=2) if ledger else "(empty)",
        "previous": previous or "(none)",
        "findings": json.dumps(findings, indent=2),
        "retry": retry or "",
    }
    slots: dict[str, str] = {}
    cuts: list[str] = []
    for name, budget in SLOT_BUDGETS:
        kept, dropped = _cut(raw.get(name, ""), budget)
        slots[name] = kept
        if dropped:
            cuts.append(f"cut {name} by {dropped} chars (budget {budget})")
    return slots, cuts


def load_ledger(work_dir: Path) -> list:
    path = Path(work_dir) / "paper_ledger.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return payload
    return list(payload.get("entries") or [])


def save_ledger(work_dir: Path, entries: list) -> None:
    path = Path(work_dir) / "paper_ledger.json"
    path.write_text(json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")


def section_done(work_dir: Path, section_id: str) -> bool:
    body = Path(work_dir) / "sections" / f"{section_id}.md"
    findings = Path(work_dir) / "knowledge" / section_id / "findings.json"
    if not body.exists() or not findings.exists():
        return False
    return any(entry.get("section_id") == section_id for entry in load_ledger(work_dir))


BODY_PROMPT_CHARS = 24000


def whole(body: str, limit: int | None = None) -> str:
    """A section body a gate can grade, and a ledger can read.

    Both call sites used `body[:6000]`. The only section in a live run over
    that ceiling was the only one the judge rejected, on `depth`,
    `objective_met`, and `no_filler`, which is precisely how a section cut
    mid-sentence reads. The judge graded what it was handed (#324).

    The ledger call was worse. It is not a gate, so every claim, number, and
    term past the cut vanished from `paper_ledger.json` with no error, and
    `ledger_consistency` is a hard row that reads that ledger.

    When a ceiling is unavoidable, cut on a paragraph boundary and say how much
    went, so a reader knows the text ended early rather than inferring that the
    writer stopped there.

    The limit is read at call time, never as a default argument. A default binds
    once at definition, and a test that lowers it would change nothing.
    """
    limit = BODY_PROMPT_CHARS if limit is None else limit
    if len(body) <= limit:
        return body

    kept = body[:limit].rsplit("\n\n", 1)[0] or body[:limit]
    dropped = len(body) - len(kept)
    return (
        f"{kept}\n\n[The section continues for {dropped} more characters, "
        "withheld for length. It is not truncated in the paper. Do not fail "
        "depth, objective_met, or no_filler for the withheld text.]"
    )


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


def _coverage_needed(terms: set[str]) -> int:
    """A third of the question's content terms, floored at two, and never
    more than the question actually has to give. #510

    A fifteen-term question used to need two incidental matches, the same
    floor a two-term question needed. Scaling the requirement with the
    question closes that gap while a short question still only has to name
    what it actually asks: `min(2, len(terms))` was already the answer for
    `len(terms) <= 2`, and stays that answer here. Copied from the SDK
    port's `checks.py`, not imported.
    """
    if not terms:
        return 0
    return min(len(terms), max(2, -(-len(terms) // 3)))


# #473. What names a section's own topic as safety, dosing, or protocol.
GUIDELINE_TOPIC_WORDS = ("safety", "dosing", "protocol")


def _is_guideline_topic(section: dict) -> bool:
    heading = str(section.get("heading") or "").lower()
    parts = [heading]
    for item in section.get("key_questions") or []:
        text = item if not isinstance(item, dict) else item.get("text") or item.get("question") or ""
        parts.append(str(text))
    return any(word in " ".join(parts).lower() for word in GUIDELINE_TOPIC_WORDS)


def guideline_ledger_sources(ledger, index: dict[str, int]) -> list[dict]:
    """Every `position_stand_or_guideline`-tier source in the whole run's
    ledger, not only this section's own findings. #517

    `index` is `stages.numbering(ledger)`'s own map, source id to reference
    number: a source no claim has cited yet (`stages.numbering` only
    numbers `ledger.bibliography()`) carries `number: 0` here rather than
    being dropped, so `guideline_cited` can still see it exists and the
    brief can still name it, even with nothing yet to cite it by.
    """
    out = []
    for source in ledger.sources.values():
        if source.tier != "position_stand_or_guideline":
            continue
        out.append(
            {
                "url": source.url,
                "title": source.title,
                "abstract": source.text,
                "tier": source.tier,
                "number": index.get(source.id) or 0,
            }
        )
    return out


def guideline_ledger_matches(ledger_sources: list[dict], section: dict, topic: str = "") -> list[dict]:
    """The run's ledger-wide guideline sources this section must reckon with. #517

    #473's own wiring graded a section against its own evidence alone, so a
    position stand retrieved for the introduction and never cited by the
    safety section it actually answers passed unnoticed. `ledger_sources`
    (`guideline_ledger_sources`, above) is every such source the whole run
    has retrieved, whichever section's research found it.

    A source only counts here when the section itself is about safety,
    dosing, or protocol (`_is_guideline_topic`) and its title or abstract
    shares at least two content terms, `STOP` applied the same way `_terms`
    already applies it, with the paper topic or this section's own key
    questions. One shared word is not on topic.

    Called from `section_check`'s `guideline_cited` and `grounded` rows, and
    from `guideline_brief`'s writer hint, so the row that requires a
    citation and the row that would otherwise call it dangling never
    disagree about which sources are in play.
    """
    if not ledger_sources or not _is_guideline_topic(section):
        return []
    parts = [str(topic or "")]
    for item in section.get("key_questions") or []:
        text = item if not isinstance(item, dict) else item.get("text") or item.get("question") or ""
        if str(text).strip():
            parts.append(str(text))
    target_terms = _terms(" ".join(parts))
    if not target_terms:
        return []
    matches = []
    for source in ledger_sources:
        if not isinstance(source, dict) or source.get("tier") != "position_stand_or_guideline":
            continue
        source_terms = _terms(f"{source.get('title') or ''} {source.get('abstract') or ''}")
        if len(source_terms & target_terms) >= 2:
            matches.append(source)
    return matches


def guideline_brief(ledger, section: dict, topic: str, index: dict[str, int], allowed: list[int]) -> tuple[str, list[int]]:
    """The writer's ledger-guideline hint, and `allowed` widened to name it. #517

    `allowed` already lists every reference number this section's own bound
    claims may cite; `stages.write_gate` rejects any other number before
    this section's own `section_check` ever runs. A ledger guideline this
    function tells the writer to cite has to be added here too, or the row
    that requires the citation and the gate that would call it stray
    disagree.
    """
    matches = guideline_ledger_matches(guideline_ledger_sources(ledger, index), section, topic)
    already = set(allowed)
    lines = [
        f"- {source['title'] or source['url']} [{source['number']}]"
        for source in matches
        if source["number"] and source["number"] not in already
    ]
    widened = sorted(already | {source["number"] for source in matches if source["number"]})
    if not lines:
        return "", widened
    note = (
        "The ledger already holds these guideline or position-stand sources, "
        "retrieved while researching another section. Cite the one(s) this "
        "section actually discusses, by their reference number:\n" + "\n".join(lines)
    )
    return note, widened


def section_check(
    body: str,
    *,
    section: dict | None = None,
    findings: list | None = None,
    evidence_blob: str = "",
    word_target: int = 0,
    ledger_sources: list[dict] | None = None,
    topic: str = "",
) -> PaperScore:
    """Ten deterministic rows on one section, before any judge.

    `stub` is hard. Length, coverage, and figures are recorded but soft on
    this port so the existing writer fixtures still finish; the SDK port
    enforces them against a writer that was fitted to `word_target`.
    """
    section = section or {}
    findings = findings or []
    # #517. Computed once, reused by `grounded` (so a citation `guideline_cited`
    # demands below is never also read back as a dangling marker) and by
    # `guideline_cited` itself.
    ledger_guidelines = guideline_ledger_matches(ledger_sources or [], section, topic)
    checks: list[Check] = []
    target = int(word_target or section.get("word_target") or 0)
    words = paper_check.word_count(body)
    if target:
        low = int(0.6 * target)
        high = int(1.25 * target)
        checks.append(
            Check(
                "length",
                low <= words <= high,
                f"{words} words (need {low}-{high} for target {target})",
                hard=False,
            )
        )
    else:
        checks.append(Check("length", True, f"{words} words", hard=False))

    stub = STUB.findall(body)
    checks.append(
        Check("stub", not stub, "no stub markers" if not stub else f"stub: {stub[:3]}")
    )

    questions = []
    for item in section.get("key_questions") or []:
        text = item if not isinstance(item, dict) else item.get("text") or item.get("question") or ""
        if str(text).strip():
            questions.append(str(text).strip())
    missing_q = []
    body_terms = _terms(body)
    for question in questions:
        terms = _terms(question)
        if terms and len(terms & body_terms) < _coverage_needed(terms):
            missing_q.append(question)
    checks.append(
        Check(
            "coverage",
            not missing_q,
            "every key question is named" if not missing_q else f"unnamed: {missing_q[:2]}",
            hard=False,
        )
    )

    uncited = []
    for para in _paragraphs(body):
        if para.startswith(("#", "!", ">", "|", "-", "*")):
            continue
        if re.search(r"\d", para) and not CITATION.search(para):
            uncited.append(para.splitlines()[0][:80])
    checks.append(
        Check(
            "cited",
            not uncited,
            "every specific is cited" if not uncited else f"uncited: {uncited[:2]}",
        )
    )

    numbers = {str(f.get("number") or "") for f in findings if f.get("number")}
    # #517. A ledger guideline `guideline_cited` requires below is a real,
    # run-wide reference number even when it never reached this section's
    # own findings. Without this, citing it here read as dangling.
    numbers |= {str(source.get("number")) for source in ledger_guidelines if source.get("number")}
    dangling = [f"[{m}]" for m in CITATION.findall(body) if m not in numbers and numbers]
    checks.append(
        Check(
            "grounded",
            not dangling,
            "every citation resolves" if not dangling else f"dangling: {dangling[:3]}",
            hard=False,
        )
    )

    blob = (evidence_blob or "").lower()
    unknown = []
    if blob:
        for token in re.findall(r"\b[A-Z][A-Za-z0-9._-]{3,}\b", body):
            if token.lower() not in blob and token.lower() not in body.lower()[:40]:
                unknown.append(token)
    checks.append(
        Check(
            "sourced",
            not unknown[:3] or not blob,
            "every identifier is in the evidence" if not unknown else f"ungrounded: {unknown[:3]}",
            hard=False,
        )
    )

    planned = [
        fig.get("name")
        for fig in (section.get("figures") or [])
        if isinstance(fig, dict) and fig.get("name")
    ]
    missing_fig = []
    for name in planned:
        needle = name.replace("-", " ")
        if name not in body and needle not in body:
            missing_fig.append(name)
    checks.append(
        Check(
            "figures",
            not missing_fig,
            "planned figures referenced" if not missing_fig else f"missing: {missing_fig}",
            hard=False,
        )
    )

    style_hits = []
    if EM_DASH.search(body):
        style_hits.append("em dash")
    if SECOND_PERSON.search(body):
        style_hits.append("second person")
    # A heading is a paragraph, and the outline hands the writer key questions
    # that the coverage row then demands it name. The writer names them as
    # subheadings, and this row read those as rhetoric. Remove the heading and
    # coverage fails, keep it and style fails.
    if any(
        RHETORICAL.search(p.splitlines()[-1])
        for p in _paragraphs(body)
        if p and not p.startswith("#")
    ):
        style_hits.append("rhetorical question")
    checks.append(
        Check("style", not style_hits, "clean" if not style_hits else ", ".join(style_hits))
    )

    # #473 #517. A section about safety, dosing, or protocol re-derives from
    # primaries exactly what a position stand or guideline already answers,
    # unless it is made to cite one. Graded against `findings` (this call's
    # own evidence) and, since #517, `ledger_guidelines`: every on-topic
    # `position_stand_or_guideline` source the whole run has retrieved so
    # far, whichever section's research found it. A guideline retrieved for
    # the introduction and never cited by the safety section it actually
    # answers now fails here, naming the source and its number. A section
    # with neither kind of guideline source passes, as before.
    named_guidelines: dict[int, str] = {}
    for f in findings:
        if f.get("evidence_tier") != "position_stand_or_guideline" or not f.get("number"):
            continue
        try:
            number = int(f["number"])
        except (TypeError, ValueError):
            # A truthy, non-numeric `number` is not this row's problem to
            # raise on; every current producer supplies an int. #473
            continue
        named_guidelines.setdefault(number, str(f.get("title") or ""))
    for source in ledger_guidelines:
        number = source.get("number")
        if not number:
            # Not yet in the run's bibliography. The writer brief
            # (`guideline_brief`) still names it; nothing here can fail a
            # section on a number that does not exist yet. #517
            continue
        try:
            number = int(number)
        except (TypeError, ValueError):
            continue
        named_guidelines.setdefault(number, str(source.get("title") or ""))
    missing_guideline = (
        sorted((number, title) for number, title in named_guidelines.items() if f"[{number}]" not in body)
        if named_guidelines and _is_guideline_topic(section)
        else []
    )
    checks.append(
        Check(
            "guideline_cited",
            not missing_guideline,
            "every position stand is cited"
            if not missing_guideline
            else "missing: " + ", ".join(f"{title or 'untitled'} [{number}]" for number, title in missing_guideline),
        )
    )

    # #474. `findings_from_claims` below sets `generalizing` from
    # `stages.GENERALIZING`, and `counter` from `claim.counter`: "hit",
    # "miss", or "capped", the counter-evidence pass's own three possible
    # outcomes. A finding left with none of those, and no
    # `counterargument_to` of its own, is a generalizing claim the pass
    # never reached at all, not one the run cap simply priced out. A
    # `capped` claim passes: the pass did look at it, and its brief
    # (`stages.claim_brief`) already tells the writer to hedge it.
    uncountered = [
        f.get("claim") or f.get("id") or ""
        for f in findings
        if f.get("generalizing") and not f.get("counter") and not f.get("counterargument_to")
    ]
    checks.append(
        Check(
            "counterweighed",
            not uncountered,
            "every generalizing claim was checked for counter-evidence"
            if not uncountered
            else f"missing: {uncountered[:2]}",
        )
    )
    return PaperScore(checks=checks)


def findings_from_claims(paper, section: dict, index: dict) -> list[dict]:
    """Turn the section's bound claims into the finding shape the writer already cites."""
    import stages as stages_mod  # noqa: PLC0415  (avoids a sections<->stages cycle)

    claim_ids = list(section.get("claim_ids") or [])
    heading = (section.get("heading") or "").lower()
    if heading in ("abstract", "references"):
        claim_ids = [c.id for c in paper.ledger.claims.values() if c.usable]
    out = []
    number = 1
    for cid in claim_ids:
        claim = paper.ledger.claim(cid)
        if claim is None or not claim.usable:
            continue
        source_id = next((sid for sid in claim.source_ids if sid in index), None)
        source = paper.ledger.sources.get(source_id) if source_id else None
        out.append(
            {
                "id": claim.id,
                "section_id": evidence.slug(section.get("heading") or cid),
                "answers_question": section.get("purpose") or "",
                "claim": claim.text,
                "quote": (source.body if source is not None else "") or "",
                "source": {
                    "kind": "web",
                    "ref": source.url if source is not None else "",
                    "title": source.title if source is not None else "",
                    "url_or_path": source.url if source is not None else "",
                    "vendor": source.vendor if source is not None else "",
                    "tier": 1,
                },
                "evidence_strength": float(claim.confidence or 0.5),
                "numbers": [],
                "number": index.get(source_id) if source_id in index else number,
                "status": claim.truth_state,
                # `source.tier` (#473), not `source["tier"]` above: that key
                # already means "corpus vs web citation weight" and predates
                # this ticket. Read by `section_check`'s `guideline_cited` row.
                "evidence_tier": source.tier if source is not None else "",
                # Read by `section_check`'s `counterweighed` row. #474
                "generalizing": bool(stages_mod.GENERALIZING.search(claim.text)),
                "counter": claim.counter,
                "counterargument_to": claim.counterargument_to or "",
            }
        )
        number += 1
    return out


def close_section(paper, section: dict, body: str, *, force: bool = False) -> float:
    """Write findings, check, judge, and ledger for one accepted section.

    Returns USD spent on the judge and ledger turns. Stub failures raise
    GateFailed so a retry rewrites only this section.
    """
    import stages as stages_mod  # noqa: PLC0415
    from stages import GateFailed  # noqa: PLC0415

    heading = section.get("heading") or ""
    sid = evidence.slug(heading)
    work = paper.work_dir
    if not force and section_done(work, sid):
        return 0.0

    dest = work / "sections"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{sid}.md").write_text(body.rstrip() + "\n", encoding="utf-8")

    index, _ = stages_mod.numbering(paper.ledger)
    findings = findings_from_claims(paper, section, index)
    knowledge = work / "knowledge" / sid
    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "findings.json").write_text(
        json.dumps({"section_id": sid, "findings": findings, "coverage_gaps": []}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    blob = "\n".join(
        [(f.get("quote") or "") + " " + (f.get("claim") or "") for f in findings]
    )
    pack = work / "corpus" / "brain-pack.md"
    if pack.exists():
        blob += "\n" + pack.read_text(encoding="utf-8")
    # #517. Every on-topic guideline this run has already retrieved for a
    # different section, so `guideline_cited` can require it here too.
    ledger_sources = guideline_ledger_sources(paper.ledger, index)
    score = section_check(
        body,
        section=section,
        findings=findings,
        evidence_blob=blob,
        ledger_sources=ledger_sources,
        topic=paper.topic,
    )
    (knowledge / "section-check.json").write_text(
        json.dumps(
            {
                "passed": score.passed,
                "signature": list(score.signature()),
                "report": score.report(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if "stub" in score.signature():
        raise GateFailed(score.report(), ("stub",))

    usd = 0.0
    reply = paper._ask(
        "section_judge",
        "Grade this section against its outline row. Do not re-litigate Python's check.\n"
        f"Heading: {heading}\nPurpose: {section.get('purpose') or section.get('objective') or ''}\n"
        f"Body:\n{whole(body)}",
    )
    usd += reply.usd
    verdict = paper._json_reply("section_judge", reply)
    (knowledge / "section-verdict.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
    )
    if not verdict.get("passed", True):
        raise GateFailed(
            "section judge rejected " + heading,
            tuple(verdict.get("failed_rows") or ("section_judge",)),
        )

    ledger_reply = paper._ask(
        "ledger",
        "Extract the ledger entry from this finished section. Add no facts.\n"
        f"section_id: {sid}\nheading: {heading}\n\n{whole(body)}",
    )
    usd += ledger_reply.usd
    try:
        entry = ledger_reply.json()
    except Exception:
        entry = {}
    if not isinstance(entry, dict):
        entry = {}
    entry["section_id"] = sid
    entry.setdefault("heading", heading)
    entry.setdefault("claims", [{"claim": f["claim"], "ref": str(f.get("number") or ""), "confidence": 0.5} for f in findings])
    entry.setdefault("numbers", [])
    entry.setdefault("decisions", [])
    entry.setdefault("terms_defined", [])
    entry.setdefault("open_questions", [])
    entry.setdefault("forward_refs", [])
    entries = [item for item in load_ledger(work) if item.get("section_id") != sid]
    entries.append(entry)
    save_ledger(work, entries)
    return usd
