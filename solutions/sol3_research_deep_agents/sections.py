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
STOP = {
    "a", "an", "the", "is", "are", "of", "in", "on", "to", "and", "or", "for",
    "what", "how", "why", "does", "do", "this", "that", "with", "from",
}

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


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


def section_check(
    body: str,
    *,
    section: dict | None = None,
    findings: list | None = None,
    evidence_blob: str = "",
    word_target: int = 0,
) -> PaperScore:
    """Eight deterministic rows on one section, before any judge.

    `stub` is hard. Length, coverage, and figures are recorded but soft on
    this port so the existing writer fixtures still finish; the SDK port
    enforces them against a writer that was fitted to `word_target`.
    """
    section = section or {}
    findings = findings or []
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
        if terms and len(terms & body_terms) < min(2, len(terms)):
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
    if any(RHETORICAL.search(p.splitlines()[-1]) for p in _paragraphs(body) if p):
        style_hits.append("rhetorical question")
    checks.append(
        Check("style", not style_hits, "clean" if not style_hits else ", ".join(style_hits))
    )
    return PaperScore(checks=checks)


def findings_from_claims(paper, section: dict, index: dict) -> list[dict]:
    """Turn the section's bound claims into the finding shape the writer already cites."""
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
    score = section_check(body, section=section, findings=findings, evidence_blob=blob)
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
        f"Body:\n{body[:6000]}",
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
        f"section_id: {sid}\nheading: {heading}\n\n{body[:6000]}",
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
