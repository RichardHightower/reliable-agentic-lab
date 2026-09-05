"""Hard gates on a finished white paper. No model call, no negotiation.

`brief.py` already does the citation arithmetic for a short brief. A white paper
adds structure, figures, and a claim ledger, so this file adds the checks those
bring and reuses `brief` for the three it already owns.

Everything here is a check that can be settled without asking. That is the whole
selection rule. "Is the argument convincing" is a judgment and belongs to the
reviewer subagent. "Does reference [7] exist" is arithmetic and belongs here,
where no amount of confident prose can talk its way past it.

A failing gate blocks the publish. `publish.py` refuses to push a paper that did
not pass, which is the difference between a gate and a warning.

    python3 paper_check.py --demo
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import brief
import evidence
import source_policy

# The sections a technical white paper has. A reader looking for limitations
# should not have to guess whether the author considered them.
REQUIRED_SECTIONS = ("abstract", "introduction", "references")
RECOMMENDED_SECTIONS = ("limitations",)

# How a single-source claim announces itself in the prose. The verifier could
# not corroborate it, and the reader is entitled to know that.
CAVEAT = re.compile(r"single source|one source|not corroborated|unconfirmed", re.I)

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
REFERENCE_ROW = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[.)])\s+(.*\S)\s*$", re.M)
URL = re.compile(r"https?://[^\s)\]<>\"']+")

# Source syntax that must never survive into a published figure or body.
SOURCE_SYNTAX = re.compile(
    r"^\s*(flowchart|graph\s+[A-Z]{2}|sequenceDiagram|classDiagram|stateDiagram|erDiagram|@startuml)",
    re.M,
)

MIN_WORDS = 2000

# The fewest words a section can carry and still count as written.
#
# 80 words is a real paragraph, not a heading with one sentence under it.
# Whether a section says enough past that is still a reviewer judgment, but a
# paper of two-sentence sections is a brief, and this gate exists to stop
# calling that a paper.
MIN_SECTION_WORDS = 80
EXIT_TERMS = (re.compile(r"\bdone\b", re.I), re.compile(r"\bcost\b", re.I), re.compile(r"\bmax\s+turns\b", re.I))

SECTION_HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.M)

# Sections that legitimately carry no prose. References is a generated list, and
# a Figures appendix is images with their alt text.
PROSE_EXEMPT = ("references", "figures")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    hard: bool = True


@dataclass
class PaperScore:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Every hard gate is green. A soft check can fail and still ship."""
        return bool(self.checks) and all(c.passed for c in self.checks if c.hard)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def signature(self) -> tuple[str, ...]:
        """What blocked, not how it was worded. `gates.decide` compares these.

        Hard gates only. A soft check that keeps warning would look like a
        stable failure and escalate a run that is actually converging, and it
        would put a warning into the retry instruction as if it blocked.
        """
        return tuple(sorted(c.name for c in self.checks if not c.passed and c.hard))

    def warnings(self) -> tuple[str, ...]:
        return tuple(sorted(c.name for c in self.checks if not c.passed and not c.hard))

    def report(self) -> str:
        rows = []
        for check in self.checks:
            mark = "PASS" if check.passed else ("FAIL" if check.hard else "WARN")
            rows.append(f"{mark}  {check.name:<22} {check.detail}")
        return "\n".join(rows)


def sections(body: str) -> list[str]:
    return [heading.strip().lower() for heading in HEADING.findall(body)]


def figures(body: str) -> list[tuple[str, str]]:
    return IMAGE.findall(body)


def word_count(body: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", FENCE.sub("", body)))


def missing_sections(body: str, required=REQUIRED_SECTIONS) -> list[str]:
    found = sections(body)
    return [name for name in required if not any(name in heading for heading in found)]


def figures_without_alt(body: str) -> list[str]:
    """A figure with no alt text is a figure a screen reader cannot report."""
    return [target for alt, target in figures(body) if not alt.strip()]


def non_publication_figures(body: str) -> list[str]:
    """Diagrams must be judged `*_imagen.png`. Charts live under `charts/`."""
    bad = []
    for _alt, target in figures(body):
        if target.endswith("_imagen.png"):
            continue
        normalized = target.replace("\\", "/")
        if normalized.startswith("charts/") or "/charts/" in normalized:
            continue
        bad.append(target)
    return bad


def visible_source_syntax(body: str) -> list[str]:
    """Diagram source left in the paper. The figure is the artifact, not the code."""
    found = []
    for language, block in FENCE.findall(body):
        if language.lower() in ("mermaid", "plantuml", "puml") or SOURCE_SYNTAX.search(block):
            found.append(language or block.strip().split("\n", 1)[0][:40])
    return found


def sections_without_prose(body: str, min_words: int = MIN_SECTION_WORDS) -> list[str]:
    """Headings with no real prose under them.

    Every other check on this page is a check on content that exists. Grounding
    passes when there are no citations to dangle, `cited` passes when there are
    no claim paragraphs to be uncited, and style passes when there is no text to
    hold an em dash. A paper of nothing but headings and a reference list
    therefore passed every hard gate, and only the soft word count noticed.

    A gate suite that a hollow document satisfies is measuring the wrong thing,
    so this is the check that says the paper has a body.
    """
    thin = []
    matches = list(SECTION_HEADING.finditer(body))
    for index, match in enumerate(matches):
        heading = match.group(2).strip()
        if heading.lower() in PROSE_EXEMPT:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        chunk = body[match.end() : end]
        # Images and fenced code are not prose. A section that is one figure and
        # nothing else still owes the reader an explanation.
        chunk = IMAGE.sub("", FENCE.sub("", chunk))
        words = re.findall(r"\b[\w'-]+\b", chunk)
        if len(words) < min_words:
            thin.append(f"{heading} ({len(words)} words)")
    return thin


def reference_rows(body: str) -> list[str]:
    """The reference list, read out of the references section only.

    Scanning the whole paper would count every numbered list as a reference, and
    a paper with a five-step procedure would report five sources it never had.
    """
    lowered = body.lower()
    start = lowered.rfind("\n# references")
    if start < 0:
        start = lowered.rfind("\n## references")
    if start < 0:
        return []
    tail = body[start:]
    rows = []
    for marker, number, text in REFERENCE_ROW.findall(tail):
        rows.append(f"[{marker or number}] {text}")
    return rows


def reference_urls(body: str) -> list[str]:
    """Every URL rendered in the bibliography, rather than model prose."""
    urls: list[str] = []
    for row in reference_rows(body):
        for url in URL.findall(row):
            clean = url.rstrip(".,;")
            if clean not in urls:
                urls.append(clean)
    return urls


def has_exit_doctrine(body: str) -> bool:
    """A body paragraph states done, then cost, then max turns in order.

    Searching the first occurrence in the whole paper is wrong: an abstract
    can discuss cost before a later case study states the complete doctrine.
    The ordering is a local claim, so evaluate it within one prose paragraph.
    """
    for section in body_sections(body):
        for paragraph in re.split(r"\n\s*\n", section):
            found = [term.search(paragraph) for term in EXIT_TERMS]
            if all(found) and [match.start() for match in found] == sorted(
                match.start() for match in found
            ):
                return True
    return False


def false_langgraph_limitation(body: str, urls: list[str]) -> bool:
    """Do not claim no official LangGraph page while citing one."""
    phrase = "no official langgraph page"
    if phrase not in body.lower():
        return False
    return any(source_policy.host(url) in {"docs.langchain.com", "reference.langchain.com"} for url in urls)


STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "than",
        "then",
        "when",
        "what",
        "which",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "as",
        "at",
        "by",
        "of",
        "on",
        "to",
        "in",
        "not",
        "no",
    ]
)
# How much of a claim's vocabulary a section must carry before we say the
# section states that claim. Too low and every section matches every claim.
CLAIM_MATCH = 0.6

SECTION_SPLIT = re.compile(r"^##\s+", re.M)


def content_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z_][\w_]{3,}", text.lower()) if word not in STOPWORDS}


def body_sections(body: str) -> list[str]:
    """The paper's sections, minus references.

    References is excluded on purpose. Every source URL appears there, so a
    check that scanned it would test whether the bibliography carries a caveat,
    which it never does and never should.
    """
    parts = SECTION_SPLIT.split(body)
    return [part for part in parts if not part.strip().lower().startswith("references")]


def uncaveated_single_source(body: str, ledger: evidence.Ledger | None) -> list[str]:
    """Single-source claims stated in a section that does not admit it.

    Locality is the point. A caveat in the abstract does not cover a claim on
    page nine, so the check runs per section and matches a claim to a section by
    vocabulary overlap.

    Matching by URL instead would be simpler and wrong: the paper cites by
    number, so the only place a URL appears is the reference list.
    """
    if ledger is None:
        return []
    singles = [
        claim
        for claim in ledger.claims.values()
        if claim.truth_state == evidence.SINGLE_SOURCE and claim.important
    ]
    if not singles:
        return []
    sections = [(section, content_words(section)) for section in body_sections(body)]
    loose = []
    for claim in singles:
        wanted = content_words(claim.text)
        if not wanted:
            continue
        for section, words in sections:
            if len(wanted & words) / len(wanted) < CLAIM_MATCH:
                continue
            if not CAVEAT.search(section):
                loose.append(claim.text[:70])
            break
    return loose


def contradicted_in_body(body: str, ledger: evidence.Ledger | None) -> list[str]:
    """A contradicted claim that reached the paper anyway."""
    if ledger is None:
        return []
    found = []
    for claim in ledger.claims.values():
        if claim.truth_state != evidence.CONTRADICTED:
            continue
        if claim.id in body or claim.text[:40] in body:
            found.append(claim.text[:70])
    return found


def check(
    body: str,
    sources: list[str],
    *,
    ledger: evidence.Ledger | None = None,
    required=REQUIRED_SECTIONS,
    min_words: int | None = None,
    min_section_words: int | None = None,
    charts=None,
    allowed_domains=None,
) -> PaperScore:
    """Score a white paper. Every check here is arithmetic."""
    words_needed = MIN_WORDS if min_words is None else min_words
    section_needed = MIN_SECTION_WORDS if min_section_words is None else min_section_words
    checks: list[Check] = []

    # The three brief.py already owns, reused rather than restated.
    inner = brief.check(body, sources)
    checks.extend(Check(c.name, c.passed, c.detail) for c in inner.checks)

    absent = missing_sections(body, required)
    checks.append(
        Check(
            "sections",
            not absent,
            "every required section is present" if not absent else f"missing: {absent}",
        )
    )

    soft = missing_sections(body, RECOMMENDED_SECTIONS)
    checks.append(
        Check(
            "limitations",
            not soft,
            "the paper states its limitations" if not soft else f"missing: {soft}",
            hard=False,
        )
    )

    no_alt = figures_without_alt(body)
    checks.append(
        Check(
            "figure_alt",
            not no_alt,
            f"{len(figures(body))} figures, all with alt text"
            if not no_alt
            else f"no alt text: {no_alt}",
        )
    )

    wrong_assets = non_publication_figures(body)
    checks.append(
        Check(
            "figure_assets",
            not wrong_assets,
            "every figure is a judged *_imagen.png publication asset"
            if not wrong_assets
            else f"non-publication figures: {wrong_assets}",
        )
    )

    raw = visible_source_syntax(body)
    checks.append(
        Check(
            "no_diagram_source",
            not raw,
            "no diagram source in the body" if not raw else f"visible source: {raw}",
        )
    )

    rows = reference_rows(body)
    checks.append(
        Check(
            "references",
            len(rows) >= len(sources) and bool(rows),
            f"{len(rows)} rows for {len(sources)} sources"
            if rows
            else "the references section lists nothing",
        )
    )

    urls = list(dict.fromkeys([*sources, *reference_urls(body)]))
    allowlist = (
        tuple(allowed_domains)
        if allowed_domains is not None
        else source_policy.merge_allowlist(urls)
    )
    blocked = source_policy.unallowed_urls(urls, allowlist)
    checks.append(
        Check(
            "reference_hosts",
            not blocked,
            "every reference host is on the approved allowlist"
            if not blocked
            else f"unapproved: {blocked}",
        )
    )

    checks.append(
        Check(
            "exit_doctrine",
            has_exit_doctrine(body),
            "the body names done, then cost, then max turns"
            if has_exit_doctrine(body)
            else "name done, then cost, then max turns in that order",
        )
    )

    checks.append(
        Check(
            "langgraph_limitations",
            not false_langgraph_limitation(body, urls),
            "limitations do not contradict an official LangGraph reference"
            if not false_langgraph_limitation(body, urls)
            else "the limitations deny an official LangGraph page that the references cite",
        )
    )

    loose = uncaveated_single_source(body, ledger)
    checks.append(
        Check(
            "single_source_caveat",
            not loose,
            "every single-source claim admits it" if not loose else f"uncaveated: {loose}",
        )
    )

    bad = contradicted_in_body(body, ledger)
    checks.append(
        Check(
            "no_contradicted",
            not bad,
            "no contradicted claim reached the paper" if not bad else f"present: {bad}",
        )
    )

    thin = sections_without_prose(body, min_words=section_needed)
    checks.append(
        Check(
            "has_body",
            not thin,
            "every section carries prose" if not thin else f"empty or near empty: {thin[:3]}",
        )
    )

    words = word_count(body)
    checks.append(
        Check(
            "length",
            words >= words_needed,
            f"{words} words (need {words_needed})",
            hard=True,
        )
    )

    rendered = [item for item in (charts or []) if item.get("path")]
    if rendered:
        import charts as charts_mod  # noqa: PLC0415

        blob = _ledger_blob(ledger) + "\n" + "\n".join(sources or [])
        failures = charts_mod.charted_failures(body, rendered, blob)
        checks.append(
            Check(
                "charted",
                not failures,
                "every plotted value is in the corpus"
                if not failures
                else f"charted: {failures[:3]}",
            )
        )

    return PaperScore(checks=checks)


def _ledger_blob(ledger) -> str:
    if ledger is None:
        return ""
    parts = []
    claims = getattr(ledger, "claims", None)
    if isinstance(claims, dict):
        for claim in claims.values():
            parts.append(getattr(claim, "text", "") or "")
    if hasattr(ledger, "bibliography"):
        for source in ledger.bibliography():
            parts.append(getattr(source, "title", "") or "")
            parts.append(getattr(source, "url", "") or "")
    return "\n".join(parts)


def demo() -> None:
    good = (
        "# Exit conditions in agent loops\n\n"
        "## Abstract\n\n"
        "A loop without an exit spends until someone notices. [1]\n\n"
        "## Introduction\n\n"
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
        "![A flowchart of the three exits](figures/exits_imagen.png)\n\n"
        "## Limitations\n\n"
        "This paper measures two runtimes only. [2]\n\n"
        "## References\n\n"
        "1. https://docs.langchain.com/one\n"
        "2. https://docs.claude.com/two\n"
    )
    urls = ["https://docs.langchain.com/one", "https://docs.claude.com/two"]

    def gate(body, *a, **kw):
        kw.setdefault("min_words", 0)
        kw.setdefault("min_section_words", 5)
        return check(body, *a, **kw)

    score = gate(good, urls)
    assert score.passed, score.report()

    # Length is a hard gate. A structurally green short paper does not ship.
    assert "length" in check(good, urls).signature()

    # A paper of headings and a reference list satisfies every other gate,
    # because each of them checks content that is not there.
    hollow = (
        "# Exit conditions\n\n## Abstract\n\ndone, then cost, then max turns. [1]\n\n## Introduction\n\n"
        "## Limitations\n\n## References\n\n"
        "1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
    )
    score = gate(hollow, urls)
    assert not score.passed, score.report()
    assert score.signature() == ("has_body",), score.signature()

    # One sentence under a heading is not a section either.
    thin = good.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]", "Yes. [1]"
    )
    assert "has_body" in gate(thin, urls).signature()

    # A Figures appendix is images and alt text, and owes no prose.
    appendix = good.replace(
        "## References",
        "## Figures\n\n![A flowchart of the three exits](figures/exits_imagen.png)\n\n## References",
    )
    assert "has_body" not in gate(appendix, urls).signature(), check(appendix, urls).report()

    # A dangling citation is not a style opinion.
    score = gate(good.replace("[2]", "[9]"), urls)
    assert not score.passed
    assert "grounded" in score.signature()

    # A missing section blocks.
    score = gate(good.replace("## Abstract", "## Overview"), urls)
    assert not score.passed
    assert "sections" in score.signature()

    # A figure with no alt text blocks.
    score = gate(good.replace("[A flowchart of the three exits]", "[]"), urls)
    assert not score.passed
    assert "figure_alt" in score.signature()

    # Mermaid source in the body blocks. The figure is the artifact.
    leaked = good.replace(
        "![A flowchart", "```mermaid\nflowchart TB\n  A --> B\n```\n\n![A flowchart"
    )
    score = gate(leaked, urls)
    assert not score.passed
    assert "no_diagram_source" in score.signature()

    # A numbered procedure elsewhere is not a reference list.
    assert reference_rows("## Steps\n\n1. do this\n2. do that\n") == []
    assert len(reference_rows(good)) == 2

    # Missing limitations warns, it does not block, and it never reaches the
    # signature the retry loop reads.
    trimmed = good.replace("## Limitations\n\nThis paper measures two runtimes only. [2]\n\n", "")
    score = gate(trimmed, urls)
    assert score.passed, score.report()
    assert "limitations" in score.warnings()
    assert "limitations" not in score.signature()

    # A single-source important claim must admit it in its own paragraph.
    ledger = evidence.Ledger("/nonexistent")
    src = evidence.SourceDocument(title="One", url="https://docs.langchain.com/one", subject="exits")
    claim = evidence.Claim(
        text="Three exits cover the observed cases",
        subject="exits",
        source_ids=[src.id],
        important=True,
    )
    evidence.corroborate(claim)
    ledger.add_source(src)
    ledger.add_claim(claim)

    body = good.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]",
        "Three exits cover the observed cases: done, then cost, then max turns. [1] https://docs.langchain.com/one",
    )
    score = gate(body, urls, ledger=ledger)
    assert not score.passed
    assert "single_source_caveat" in score.signature()

    caveated = body.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1]",
        "Three exits cover the observed cases: done, then cost, then max turns, on a single source. [1]",
    )
    score = gate(caveated, urls, ledger=ledger)
    assert "single_source_caveat" not in score.signature(), score.report()

    # A contradicted claim never reaches the paper.
    evidence.corroborate(claim, contradicted=True)
    score = gate(caveated, urls, ledger=ledger)
    assert not score.passed
    assert "no_contradicted" in score.signature()

    print("paper_check: all demo assertions passed")


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Gate a finished white paper.")
    parser.add_argument("paper", help="the markdown file to check")
    parser.add_argument("--sources", default=None, help="a JSON list of source URLs")
    parser.add_argument("--evidence", default=None, help="the evidence directory")
    args = parser.parse_args(argv)

    body = Path(args.paper).read_text(encoding="utf-8")
    ledger = evidence.Ledger(args.evidence).load() if args.evidence else None
    if args.sources:
        urls = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    elif ledger is not None:
        # Match the in-process assemble gate. The evidence directory is a
        # complete post-run input, so callers should not also have to rebuild
        # the bibliography as a separate JSON sidecar.
        urls = [source.url for source in ledger.bibliography()]
    else:
        urls = []
    score = check(body, urls, ledger=ledger)
    print(score.report())
    return 0 if score.passed else 1


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        raise SystemExit(main())
