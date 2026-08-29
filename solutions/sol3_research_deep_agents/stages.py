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
import re
from dataclasses import dataclass, field
from pathlib import Path

import diagrams
import evidence
import paper_check

# A plan that asks fewer than this is not research, it is a lookup.
MIN_QUESTIONS = 3
MAX_QUESTIONS = 8

# Sections that bind to no claims of their own. The abstract restates what the
# body already cited, so binding it would mean listing every claim twice and
# keeping the two lists in step. References is generated from the ledger.
UNBOUND_SECTIONS = ("abstract", "references")

FENCED_JSON = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
CITATION = re.compile(r"\[(\d+)\]")

STAGE_ORDER = (
    "plan",
    "search",
    "verify",
    "outline",
    "diagram",
    "write",
    "review",
    "assemble",
    "publish",
)


class GateFailed(Exception):
    """The stage produced something unusable. The message is the retry prompt."""

    def __init__(self, message: str, signature: tuple[str, ...] = ()):
        super().__init__(message)
        self.signature = signature or (message.split(".", maxsplit=1)[0][:40],)


class RendererMissing(RuntimeError):
    """No diagram renderer on this machine. Not a gate failure, so never a retry.

    A gate failure means the model produced something a better attempt could
    fix. `mmdc is not installed` is not that. Asking the diagrammer to redraw is
    asking it to solve a problem it cannot see and cannot reach, and the only
    thing three attempts buy is three times the bill.
    """


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


# -- 1. plan --------------------------------------------------------------


def plan_gate(plan: dict) -> None:
    """Count what a plan must have. No opinion about whether it is a good plan."""
    misses = []
    questions = plan.get("questions") or []
    if not MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS:
        misses.append(
            f"there are {len(questions)} questions. "
            f"Write between {MIN_QUESTIONS} and {MAX_QUESTIONS}."
        )
    seen = set()
    for index, question in enumerate(questions):
        label = question.get("id") or f"question {index + 1}"
        if not question.get("question", "").strip():
            misses.append(f"{label} has no question text.")
        if not question.get("check", "").strip():
            misses.append(f"{label} has no check. Name the observable fact that answers it.")
        if label in seen:
            misses.append(f"{label} is used twice. Every question needs its own id.")
        seen.add(label)
    if not any(question.get("important") for question in questions):
        misses.append("no question is marked important. The verifier would check nothing.")
    if not plan.get("sections"):
        misses.append("the plan names no sections.")
    for figure in plan.get("diagrams") or []:
        if figure.get("kind") not in ("mermaid", "plantuml"):
            misses.append(f"diagram {figure.get('name')!r} has no kind of mermaid or plantuml.")
    if misses:
        raise GateFailed(" ".join(misses), tuple(sorted({m.split()[0] for m in misses})))


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
    sections = [s for s in plan.get("sections", []) if s.strip()]
    # Every white paper opens with an abstract and an introduction and closes
    # with references. A plan that omits one produces a paper that fails the
    # section gate at stage 8, four stages and several dollars too late.
    #
    # Position matters as much as presence. Inserting a missing Introduction at
    # the front of a plan that already has an Abstract puts the introduction
    # first, which is a different paper.
    lowered = [s.lower() for s in sections]
    if "abstract" not in lowered:
        sections.insert(0, "Abstract")
        lowered.insert(0, "abstract")
    if "introduction" not in lowered:
        sections.insert(lowered.index("abstract") + 1, "Introduction")
    if "references" not in lowered:
        sections.append("References")
    plan["sections"] = sections
    return plan


# -- 2. search ------------------------------------------------------------


def record_findings(ledger: evidence.Ledger, question: dict, reply: dict) -> evidence.Finding:
    """Turn one researcher reply into source, claim, and finding records.

    A claim with no source id is dropped here rather than carried forward. It
    cannot be corroborated, it cannot be cited, and keeping it only lets it
    reach the writer as something that looks like evidence.
    """
    subject = question.get("subject", "topic")
    source_ids = []
    for item in reply.get("sources", []):
        url = str(item.get("url", "")).strip()
        if not url.startswith("http"):
            continue
        source = ledger.add_source(
            evidence.SourceDocument(
                title=item.get("title") or url,
                url=url,
                subject=subject,
                vendor=item.get("vendor", ""),
                body=item.get("quote", ""),
            )
        )
        source_ids.append(source.id)

    claim_ids = []
    for item in reply.get("claims", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        # A claim may name its own subset of sources. When it names none, it
        # inherits every source this answer produced.
        wanted = item.get("source_urls") or []
        ids = [
            sid
            for sid in source_ids
            if not wanted or any(ledger.sources[sid].url == url for url in wanted)
        ]
        if not ids:
            continue
        claim = ledger.add_claim(
            evidence.Claim(
                text=text,
                subject=subject,
                source_ids=ids,
                confidence=float(item.get("confidence", 0.5)),
                important=bool(question.get("important")),
            )
        )
        evidence.corroborate(claim)
        claim_ids.append(claim.id)

    return ledger.add_finding(
        evidence.Finding(
            question=question.get("question", ""),
            subject=subject,
            claim_ids=claim_ids,
            summary=reply.get("answer", ""),
        )
    )


def search_gate(ledger: evidence.Ledger, plan: dict) -> None:
    """Every question produced at least one cited claim, or the paper has no evidence."""
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
            "Search again with narrower wording, or report that no source exists.",
            ("unanswered_important",),
        )


# How many claims one verify stage will cross-check.
#
# The verifier searches for each claim it is handed, so the size of this list is
# the size of the work. Handing it every important claim is how four research
# questions became a hundred and eleven verification turns in a live run: the
# stage had no upper bound at all, and neither the money cap nor the turn cap
# was checked until it finished.
#
# Twelve is a working default, not a discovered constant. Raise it with
# `--max-verify` when a paper genuinely rests on more than twelve load-bearing
# facts, and expect the bill to scale with it.
MAX_VERIFY_CLAIMS = 12


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


def apply_verification(ledger: evidence.Ledger, report: dict) -> dict:
    """Fold the verifier's report into truth states. Python counts, not the model.

    The verifier says `agreed`, `disagreed`, or `not_found`. This function turns
    that into a truth state by counting distinct source ids, which is why a
    verifier that says `agreed` twice about the same URL cannot promote a claim.
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
            if url.startswith("http"):
                source = ledger.add_source(
                    evidence.SourceDocument(
                        title=row.get("quote", "")[:60] or url,
                        url=url,
                        subject=claim.subject or "verification",
                        body=row.get("quote", ""),
                    )
                )
                if source.id not in claim.source_ids:
                    claim.source_ids.append(source.id)
            evidence.corroborate(claim)
        elif status == "disagreed":
            claim.note = row.get("quote", "a second source disagreed")
            evidence.corroborate(claim, contradicted=True)
        else:
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

    required = {name.lower() for name in plan.get("sections", [])}
    present = {str(section.get("heading", "")).lower() for section in sections}
    for name in ("abstract", "introduction", "references"):
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


def render_figures(src_dir: Path, out_dir: Path, topic: str, **kwargs) -> tuple[list, list[str]]:
    """Render every diagram source. Too-complex ones come back as instructions.

    A complexity failure is not an exception here. It is a message for the
    diagrammer, and the caller feeds it straight back as the retry prompt.

    A renderer that is not on this machine is the opposite. Nothing the
    diagrammer writes will fix it, so it raises `RendererMissing` and the stage
    stops rather than paying for two more identical attempts.
    """
    figures, complaints, unrenderable = [], [], []
    if not src_dir.is_dir():
        return figures, ["no diagram sources were written."]
    for path in sorted(src_dir.iterdir()):
        if path.suffix.lower() not in diagrams.MERMAID_SUFFIXES + diagrams.PLANTUML_SUFFIXES:
            continue
        try:
            figures.append(diagrams.render(path, out_dir, topic=topic, **kwargs))
        except diagrams.DiagramTooComplex as exc:
            complaints.append(f"{path.name}: {exc}")
        except RuntimeError as exc:
            unrenderable.append(f"{path.name}: {exc}")
    if unrenderable and not figures:
        raise RendererMissing(
            "no diagram source could be rendered on this machine. "
            + " ".join(unrenderable[:2])
            + " Install mermaid-cli for .mmd and plantuml for .puml."
        )
    complaints.extend(unrenderable)
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
    return f"- {claim.id}: {claim.text} {markers}{caveat}"


def write_gate(section: str, body: str, allowed: list[int]) -> None:
    """The section cites only the numbers its claims gave it."""
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


# -- 7. review ------------------------------------------------------------


def review_gate(verdict: dict) -> None:
    rows = verdict.get("failed_rows") or []
    if rows:
        notes = verdict.get("notes") or []
        pairs = zip(rows, notes, strict=False)
        detail = " ".join(f"{row}: {note}" for row, note in pairs) or ", ".join(rows)
        raise GateFailed(f"the reviewer failed these rows. {detail}", tuple(sorted(rows)))


# -- 8. assemble ----------------------------------------------------------


def figure_block(figure, figures_dir: str = "figures") -> str:
    target = figure.best
    name = target.name if target else f"{figure.name}.svg"
    return f"![{figure.alt}]({figures_dir}/{name})"


def references_block(urls: list[str], sources: list) -> str:
    rows = ["## References", ""]
    for number, source in enumerate(sources, start=1):
        title = source.title.strip() or source.url
        rows.append(f"{number}. {title}. {source.url}")
    if not sources:
        rows += [f"{n}. {url}" for n, url in enumerate(urls, start=1)]
    return "\n".join(rows) + "\n"


def assemble(
    plan: dict,
    outline: dict,
    written: dict[str, str],
    figures: list,
    ledger: evidence.Ledger,
) -> str:
    """Stitch the paper. Pure Python, deterministic, no model call.

    Figures land under the section that asked for them, after its prose. The
    references section is generated from the ledger, never written by the model,
    because a generated bibliography cannot cite a source that was not retrieved.
    """
    _, urls = numbering(ledger)
    by_name = {figure.name: figure for figure in figures}
    used_figures: set[str] = set()

    parts = [f"# {plan.get('title', 'Untitled')}", ""]
    for section in outline.get("sections", []):
        heading = str(section.get("heading", "")).strip()
        if heading.lower() == "references":
            continue
        parts.append(f"## {heading}")
        parts.append("")
        body = written.get(heading, "").strip()
        if body:
            parts.append(body)
            parts.append("")
        for name in section.get("figures", []) or []:
            figure = by_name.get(name)
            if figure is not None and name not in used_figures:
                parts.append(figure_block(figure))
                parts.append("")
                used_figures.add(name)

    # A rendered figure the outline never placed still belongs in the paper. It
    # cost a render, and dropping it silently hides that the outline drifted.
    orphans = [f for name, f in by_name.items() if name not in used_figures]
    if orphans:
        parts.append("## Figures")
        parts.append("")
        for figure in orphans:
            parts.append(figure_block(figure))
            parts.append("")

    parts.append(references_block(urls, ledger.bibliography()))
    return "\n".join(parts).replace("\n\n\n", "\n\n")


def assemble_gate(body: str, ledger: evidence.Ledger) -> paper_check.PaperScore:
    _, urls = numbering(ledger)
    score = paper_check.check(body, urls, ledger=ledger)
    if not score.passed:
        raise GateFailed(
            "the paper failed its hard gates.\n" + score.report(),
            score.signature(),
        )
    return score
