"""Deterministic checks on a written paper.

These come from articles v3, and every one of them is a check a model does not
get a vote on. Check what you can check without asking, and save the model for
what needs judgement.

    complete      every section the plan named is actually in the paper
    grounded      every citation marker resolves to a source that was retrieved
    cited         every claim paragraph names a source
    sourced       every identifier in the text appears in the retrieved evidence
    images        every figure the paper references is a file on disk
    style         an em dash is replaced, not argued about
    has_body      every named section carries real prose, not a heading
    length        the paper clears the 1800-word floor (opt-in on paper runs)

`complete` looks redundant and is not. Without it a paper with no body at all
passes every other row: the abstract is exempt from `cited`, the reference list
is intact, and there are no figures to break and no prose to hold an em dash. A
live run produced exactly that, and the rubric called it green.

`sourced` is the one that matters most and is the least obvious. A web search
cannot refute a citation that was never published. Asking a model "is this real"
gets you a confident yes. The only thing that catches a fabricated reference is
checking its identifier against the corpus that was actually retrieved.

    python3 checks.py --demo
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import source_policy

CITATION = re.compile(r"\[(\d+)\]")
EM_DASH = re.compile(r"\s*—\s*")
EN_DASH = re.compile(r"(?<=\w)–(?=\w)")  # noqa: RUF001  (the dash is the target)
CODE_SPAN = re.compile(r"`[^`]*`|```.*?```", re.S)
LIST_ITEM = re.compile(r"^\d+[.)]\s")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)  # re.M so finditer sees every heading

# Sections where a paragraph without a citation is correct, not sloppy. An
# abstract summarizes material that is cited below it, and a reference list is
# the citation. Demanding a marker in either produces a paper that cites its own
# bibliography.
UNCITED_SECTIONS = {"abstract", "references", "summary"}

# Opt-in floors. Unit tests of other rows stay short. The pipeline passes
# these when it is producing a paper rather than exercising one phase.
# Abstract is assembler-owned from the outline thesis, so the section floor
# does not apply to it. The whole-paper floor still does.
MIN_WORDS = 1800
MIN_SECTION_WORDS = 80
PROSE_EXEMPT = {"references", "figures", "abstract"}
SECTION_HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.M)
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
EXIT_ORDER = re.compile(r"\bdone\b[\s\S]{0,240}?\bcost\b[\s\S]{0,240}?\bmax(?:imum)?\s+turns?\b", re.I)
WHICHEVER_FIRST = re.compile(r"\bwhichever\s+(?:comes|fires)\s+first\b", re.I)

# A section the writer appended that assembly owns. Two "References" headings in
# one paper is the visible symptom; the cause is a writer doing the harness's
# job. Matched case-insensitively, with or without a trailing colon.
OWNED_HEADING = re.compile(
    r"^#{1,6}\s+(references|bibliography|sources|works cited)\s*:?\s*$", re.I | re.M
)

# The grounding contract tells a writer to flag an untraceable specific rather
# than guess one. The flag is a note to a person, not part of the paper.
NEEDS_SOURCE = re.compile(r"<!--\s*NEEDS-SOURCE:\s*(.*?)\s*-->", re.S)

# Identifiers a reader can look up, and therefore identifiers a paper can
# fabricate. A bare URL is deliberately excluded: they are too common in
# retrieved text to be signal, and a dead link is a different problem.
ARXIV = re.compile(r"\barXiv[:\s]*(\d{4}\.\d{4,5})", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
AUTHOR_YEAR = re.compile(r"\[([A-Z][^\[\]\n]{2,60}?,\s*(?:19|20)\d{2})\]")
PERCENT = re.compile(r"\b\d+(?:\.\d+)?%")
VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
BIG_INT = re.compile(r"\b([1-9]\d{2,})\b")
QUOTED = re.compile(r'"([^"]{3,})"')
PROPER = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.I)
RHETORICAL = re.compile(r"\?\s*$")
STUB = re.compile(r"\bTODO\b|\[placeholder\]|lorem ipsum", re.I)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Score:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def signature(self) -> tuple[str, ...]:
        """What failed, not how it was worded.

        Two equal signatures mean the last attempt changed nothing, which is the
        stall the gate stops on.
        """
        return tuple(sorted(c.name for c in self.checks if not c.passed))

    def report(self) -> str:
        return "\n".join(
            f"{'PASS' if c.passed else 'FAIL'}  {c.name:<10} {c.detail}" for c in self.checks
        )

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "signature": list(self.signature()),
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def _mask_code(text: str) -> str:
    """Blank code regions but keep every character offset.

    A version number inside a fenced block is an example, not a claim, and a
    citation-shaped string in a code sample is not a citation.
    """
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), text)


def strip_em_dashes(text: str) -> str:
    """Replace em dashes deterministically. Code spans are left alone.

    A comma-heavy sentence takes a colon, a light one takes a semicolon. The
    rule matters less than the fact that it is a rule and not a negotiation.
    """
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = CODE_SPAN.sub(stash, text)

    out_lines = []
    for raw_line in masked.split("\n"):
        line = raw_line
        while EM_DASH.search(line):
            replacement = ": " if line.count(",") >= 2 else "; "
            line = EM_DASH.sub(replacement, line, count=1)
        out_lines.append(line)
    masked = "\n".join(out_lines)
    masked = EN_DASH.sub("-", masked)

    for index, span in enumerate(spans):
        masked = masked.replace(f"\x00{index}\x00", span)
    return masked


def ungrounded_citations(body: str, sources: list[str]) -> list[str]:
    """Citation markers that point at a source which was never retrieved."""
    available = set(range(1, len(sources) + 1))
    used = {int(marker) for marker in CITATION.findall(_mask_code(body))}
    return [f"[{n}]" for n in sorted(used - available)]


def uncited_claims(body: str) -> list[str]:
    """Body paragraphs that assert something and cite nothing.

    Crude on purpose: a paragraph with no citation marker is a claim with no
    source. The check is cheap, it never argues, and it catches the failure that
    matters, which is a confident sentence nobody can trace.
    """
    loose = []
    section = ""
    after_image = False
    for block in body.split("\n\n"):
        text = block.strip()
        if not text:
            continue
        heading = HEADING.match(text)
        if heading:
            section = heading.group(1).strip().lower()
            after_image = False
            continue
        if text.startswith("!["):
            # The paragraph after a figure is its caption. A caption explains
            # the image above it and cites nothing, which is correct.
            after_image = True
            continue
        if section in UNCITED_SECTIONS or after_image:
            after_image = False
            continue
        if text.startswith(("-", "*", ">", "|", "```")):
            continue
        # A numbered list is the reference list itself, or a set of steps.
        # Neither is a claim, and demanding a citation on the bibliography is
        # silly.
        if LIST_ITEM.match(text):
            continue
        if not CITATION.search(text):
            loose.append(text.splitlines()[0][:80])
    return loose


def ungrounded_identifiers(body: str, corpus: str, *, extended: bool = False) -> list[str]:
    """Lookup identifiers that appear nowhere in the retrieved evidence.

    Ported from `v3/article_pipeline/util/verified_facts.py`. A fabricated
    arXiv id or DOI reads exactly like a real one and survives every check that
    asks a model whether it is real. It does not survive being looked for in
    the text that was actually retrieved.

    `extended` adds percentages, versions, years, and integers above 100. The
    section check uses that set. The paper-level `sourced` row stays on the
    original three so a unit test of citations is not a census of every digit.
    """
    if not corpus:
        return []
    text = _mask_code(body)
    found: list[str] = []
    patterns = (ARXIV, DOI, AUTHOR_YEAR)
    if extended:
        patterns = patterns + (PERCENT, VERSION, YEAR, BIG_INT)
    for pattern in patterns:
        for match in pattern.findall(text):
            token = match if isinstance(match, str) else match[0]
            if token and token not in corpus and token not in found:
                found.append(token)
    return found


def take_flags(body: str) -> tuple[str, list[str]]:
    """Pull every NEEDS-SOURCE flag out of the text, and return both.

    The flag is an HTML comment, so it is invisible in rendered markdown and
    very visible to anyone reading the source. Leaving it in ships a paper with
    the author's margin notes still in it. Dropping it silently loses the one
    place the writer said "I could not trace this".
    """
    flags = [flag.strip() for flag in NEEDS_SOURCE.findall(body) if flag.strip()]
    return NEEDS_SOURCE.sub("", body), flags


def drop_owned_headings(body: str) -> str:
    """Remove a reference list a section wrote for itself.

    Assembly owns the one reference list, numbered across the whole paper. A
    section that appends its own leaves the reader with two headings and two
    numbering schemes.
    """
    out: list[str] = []
    skipping = False
    for line in body.split("\n"):
        if OWNED_HEADING.match(line):
            skipping = True
            continue
        if skipping:
            # The stray list runs until the next heading of any level.
            if line.startswith("#"):
                skipping = False
            else:
                continue
        out.append(line)
    return "\n".join(out)


def outline_coverage_gaps(body: str, outline: dict | None) -> list[str]:
    """Approved sections missing from the paper, or key questions never named.

    A key question is named when its text appears in the section body, case
    insensitive. The writer is handed the questions; this row checks they
    reached the page.
    """
    if not outline:
        return []
    matches = list(HEADING.finditer(body))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        bodies[heading] = body[start:end]
    gaps = []
    for section in outline.get("sections") or []:
        heading = (section.get("heading") or "").strip()
        key = heading.lower()
        if key not in bodies:
            gaps.append(f"section {heading!r} never written")
            continue
        text = bodies[key].lower()
        for question in section.get("key_questions") or []:
            named = question if not isinstance(question, dict) else question.get("text") or ""
            if str(named).strip().lower() not in text:
                gaps.append(f"section {heading!r} never names {named!r}")
    return gaps


def missing_sections(body: str, headings: list[str]) -> list[str]:
    """Sections the plan named that are not in the paper.

    Matched on the heading text, because that is what the writer was told to
    emit and what a reader looks for in a table of contents.
    """
    present = {match.group(1).strip().lower() for match in HEADING.finditer(body)}
    return [heading for heading in headings if heading.strip().lower() not in present]


def unresolved_images(body: str, base_dir: Path | str | None) -> list[str]:
    """Figures the paper references that are not files on disk.

    A white paper whose diagram is a broken image is worse than one with no
    diagram, because the caption still promises a figure that is not there.
    Remote images are skipped: this check owns the local ones.
    """
    if base_dir is None:
        return []
    root = Path(base_dir)
    missing = []
    for target in IMAGE.findall(body):
        if target.startswith(("http://", "https://", "data:")):
            continue
        if not (root / target).exists() and target not in missing:
            missing.append(target)
    return missing


def non_publication_images(body: str) -> list[str]:
    """Diagram publication accepts only imagen-diagrams' named PNG output."""
    return [
        target
        for target in IMAGE.findall(body)
        if not target.startswith(("http://", "https://", "data:"))
        and not target.endswith("_imagen.png")
    ]


def doctrine_failure(body: str) -> str | None:
    """Return the first reason the paper teaches the wrong exit doctrine.

    The control order is deliberate: a completed result exits before the cost
    ceiling, which exits before the maximum-turn safety stop.  "Whichever fires
    first" teaches a different loop and is not an acceptable paraphrase.
    """
    if WHICHEVER_FIRST.search(body):
        return "must not teach 'whichever comes first'"
    if not EXIT_ORDER.search(body):
        return "must name done, then cost, then max turns in that order"

    first = IMAGE.search(body)
    if first is None:
        return "Figure 1 must show done, then cost, then max turns"
    # The figure's alt text plus its immediate caption are the source-visible
    # representation of Figure 1.  Requiring those labels keeps a polished but
    # semantically wrong diagram from clearing the paper gate.
    # Markdown normally separates a block image and its caption with a blank
    # line. Skip that separator, then include the first caption paragraph.
    after_image = body[first.end() :].lstrip("\n")
    caption = after_image.split("\n\n", 1)[0]
    nearby = f"{first.group(0)}\n{caption}"
    if not EXIT_ORDER.search(nearby):
        return "Figure 1 must label done, then cost, then max turns"
    return None


def disallowed_reference_hosts(sources: list[str]) -> list[str]:
    """References from blogs and DeepWiki never become a paper's bibliography."""
    return [url for url in sources if not source_policy.is_allowed_url(url)]


def word_count(body: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", FENCE.sub("", body)))


def sections_without_prose(body: str, min_words: int) -> list[str]:
    if min_words <= 0:
        return []
    thin = []
    matches = list(SECTION_HEADING.finditer(body))
    for index, match in enumerate(matches):
        heading = match.group(2).strip()
        if heading.lower() in PROSE_EXEMPT:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        chunk = IMAGE.sub("", FENCE.sub("", body[match.end() : end]))
        words = re.findall(r"\b[\w'-]+\b", chunk)
        if len(words) < min_words:
            thin.append(f"{heading} ({len(words)} words)")
    return thin


def check(
    body: str,
    sources: list[str],
    *,
    base_dir: Path | str | None = None,
    corpus: str = "",
    headings: list[str] | None = None,
    outline: dict | None = None,
    enforce_source_policy: bool = False,
    enforce_loop_doctrine: bool = False,
    min_words: int = 0,
    min_section_words: int = 0,
) -> Score:
    """Score a paper. No model call."""
    checks: list[Check] = []

    checks.append(Check("sources", bool(sources), f"{len(sources)} sources retrieved"))

    if enforce_source_policy:
        rejected = disallowed_reference_hosts(sources)
        checks.append(
            Check(
                "hosts",
                not rejected,
                "every reference host is allowed" if not rejected else f"not allowed: {rejected[:3]}",
            )
        )

    if enforce_loop_doctrine:
        failure = doctrine_failure(body)
        checks.append(Check("doctrine", failure is None, "exit order and Figure 1 agree" if failure is None else failure))
        wrong_assets = non_publication_images(body)
        checks.append(
            Check(
                "figure_assets",
                not wrong_assets,
                "every diagram is a judged *_imagen.png"
                if not wrong_assets
                else f"non-publication figures: {wrong_assets[:3]}",
            )
        )

    absent = missing_sections(body, headings or [])
    checks.append(
        Check(
            "complete",
            not absent,
            f"{len(headings or [])} sections present"
            if not absent
            else f"never written: {absent[:3]}",
        )
    )

    if outline is not None:
        gaps = outline_coverage_gaps(body, outline)
        checks.append(
            Check(
                "outline_coverage",
                not gaps,
                "every approved section and key question is on the page"
                if not gaps
                else f"missing: {gaps[:3]}",
            )
        )

    dangling = ungrounded_citations(body, sources)
    checks.append(
        Check(
            "grounded",
            not dangling,
            "every citation resolves" if not dangling else f"dangling: {dangling}",
        )
    )

    loose = uncited_claims(body)
    checks.append(
        Check(
            "cited",
            not loose,
            "every paragraph cites a source" if not loose else f"uncited: {loose[:2]}",
        )
    )

    invented = ungrounded_identifiers(body, corpus)
    checks.append(
        Check(
            "sourced",
            not invented,
            "every identifier is in the evidence"
            if not invented
            else f"not in the evidence: {invented[:3]}",
        )
    )

    missing = unresolved_images(body, base_dir)
    checks.append(
        Check(
            "images",
            not missing,
            f"{len(IMAGE.findall(body))} figures resolve"
            if not missing
            else f"missing: {missing[:3]}",
        )
    )

    dashes = len(EM_DASH.findall(_mask_code(body)))
    checks.append(Check("style", dashes == 0, f"{dashes} em dashes"))

    if min_section_words:
        thin = sections_without_prose(body, min_section_words)
        checks.append(
            Check(
                "has_body",
                not thin,
                "every section carries prose" if not thin else f"empty or near empty: {thin[:3]}",
            )
        )
    if min_words:
        words = word_count(body)
        checks.append(
            Check(
                "length",
                words >= min_words,
                f"{words} words (need {min_words})",
            )
        )

    return Score(checks=checks)


def has_specifics(text: str) -> bool:
    """A number, a version, a date, a proper name, or a quoted phrase."""
    masked = _mask_code(text)
    return bool(
        PERCENT.search(masked)
        or VERSION.search(masked)
        or YEAR.search(masked)
        or BIG_INT.search(masked)
        or QUOTED.search(masked)
        or PROPER.search(masked)
        or re.search(r"\d", masked)
    )


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def section_check(
    body: str,
    *,
    section: dict | None = None,
    findings: list | None = None,
    evidence: str = "",
    word_target: int = 0,
) -> Score:
    """Eight deterministic rows on one section, before any judge."""
    section = section or {}
    findings = findings or []
    checks: list[Check] = []
    target = int(word_target or section.get("word_target") or 0)
    words = word_count(body)
    if target:
        low = int(0.6 * target)
        high = int(1.25 * target)
        checks.append(
            Check(
                "length",
                low <= words <= high,
                f"{words} words (need {low}-{high} for target {target})",
            )
        )
    else:
        checks.append(Check("length", True, f"{words} words"))

    stub = STUB.findall(body)
    checks.append(
        Check("stub", not stub, "no stub markers" if not stub else f"stub: {stub[:3]}")
    )

    questions = []
    for item in section.get("key_questions") or []:
        text = item if not isinstance(item, dict) else item.get("text") or ""
        if str(text).strip():
            questions.append(str(text).strip())
    missing_q = [q for q in questions if q.lower() not in body.lower()]
    checks.append(
        Check(
            "coverage",
            not missing_q,
            "every key question is named" if not missing_q else f"unnamed: {missing_q[:2]}",
        )
    )

    uncited = []
    for para in _paragraphs(body):
        if para.startswith("#") or para.startswith("!") or para.startswith(">"):
            continue
        if para.startswith(("|", "-", "*")):
            continue
        if has_specifics(para) and not CITATION.search(para):
            uncited.append(para.splitlines()[0][:80])
    checks.append(
        Check(
            "cited",
            not uncited,
            "every specific is cited" if not uncited else f"uncited: {uncited[:2]}",
        )
    )

    numbers = {str(f.get("number") or "") for f in findings if f.get("number")}
    ids = {str(f.get("id") or "") for f in findings}
    dangling = []
    for marker in CITATION.findall(body):
        if marker not in numbers and marker not in ids and f"[{marker}]" not in "".join(
            str(f.get("id") or "") for f in findings
        ):
            # A citation is grounded if it matches a finding number or id suffix.
            if not any(str(f.get("number")) == marker for f in findings):
                dangling.append(f"[{marker}]")
    checks.append(
        Check(
            "grounded",
            not dangling,
            "every citation resolves" if not dangling else f"dangling: {dangling[:3]}",
        )
    )

    unknown = ungrounded_identifiers(body, evidence, extended=True)
    checks.append(
        Check(
            "sourced",
            not unknown,
            "every identifier is in the evidence" if not unknown else f"ungrounded: {unknown[:3]}",
        )
    )

    planned = [
        fig.get("name")
        for fig in (section.get("figures") or [])
        if isinstance(fig, dict) and fig.get("name")
    ]
    missing_fig = [name for name in planned if name and name not in body]
    checks.append(
        Check(
            "figures",
            not missing_fig,
            "planned figures referenced" if not missing_fig else f"missing: {missing_fig}",
        )
    )

    style_hits = []
    if EM_DASH.search(body):
        style_hits.append("em dash")
    if SECOND_PERSON.search(_mask_code(body)):
        style_hits.append("second person")
    if any(RHETORICAL.search(p.splitlines()[-1]) for p in _paragraphs(body) if p):
        style_hits.append("rhetorical question")
    checks.append(
        Check("style", not style_hits, "clean" if not style_hits else ", ".join(style_hits))
    )
    return Score(checks=checks)


def demo() -> int:
    """Assert the checks against their own examples. No pytest, no network."""
    assert strip_em_dashes("a, b, c — d") == "a, b, c: d"
    assert strip_em_dashes("a — b") == "a; b"
    assert strip_em_dashes("`a — b`") == "`a — b`", "a code span is left alone"

    assert ungrounded_citations("see [1] and [3]", ["u1"]) == ["[3]"]
    assert ungrounded_citations("`[3]`", []) == [], "a code span is not a citation"

    assert uncited_claims("The system is fast.") == ["The system is fast."]
    assert uncited_claims("The system is fast [1].") == []
    assert uncited_claims("## Heading") == []
    assert uncited_claims("## Abstract\n\nA review of things.") == []
    assert uncited_claims("## References\n\nsome text") == []
    assert uncited_claims("![f](x.png)\n\nThe figure shows a loop.") == []
    # Only the caption is exempt. The paragraph after it is prose again.
    assert uncited_claims("![f](x.png)\n\nCaption.\n\nA real claim.") == ["A real claim."]
    assert uncited_claims("## Abstract\n\nfine.\n\n## Body\n\nA claim.") == ["A claim."]

    corpus = "we read arXiv:2401.00001 and 10.1000/real today"
    assert ungrounded_identifiers("uses arXiv:2401.00001", corpus) == []
    assert ungrounded_identifiers("uses arXiv:2999.99999", corpus) == ["2999.99999"]
    assert ungrounded_identifiers("see 10.1000/invented", corpus) == ["10.1000/invented"]
    assert ungrounded_identifiers("[Liu, 2024] said", corpus) == ["Liu, 2024"]
    assert ungrounded_identifiers("uses arXiv:2999.99999", "") == [], "no corpus, no opinion"

    assert unresolved_images("![a](x.png)", "/nonexistent") == ["x.png"]
    assert unresolved_images("![a](https://h/x.png)", "/nonexistent") == []
    assert unresolved_images("![a](x.png)", None) == []

    body, flags = take_flags("A point. <!-- NEEDS-SOURCE: the version --> More.")
    assert flags == ["the version"]
    assert "NEEDS-SOURCE" not in body
    assert take_flags("no flags")[1] == []

    assert drop_owned_headings("## A\n\nx\n\n## References\n\n1. u\n\n## B\n\ny") == (
        "## A\n\nx\n\n## B\n\ny"
    )
    assert drop_owned_headings("## Sources:\n\n1. u") == ""
    assert "## A" in drop_owned_headings("## A\n\nx"), "an ordinary section survives"

    assert missing_sections("## The problem\n\nx", ["The problem"]) == []
    assert missing_sections("## Other\n\nx", ["The problem"]) == ["The problem"]
    assert missing_sections("## the PROBLEM", ["The problem"]) == [], "heading case is noise"

    score = check("The system is fast [1].\n\n![f](x.png)", ["u1"], base_dir="/nonexistent")
    assert not score.passed
    assert score.signature() == ("images",), score.signature()

    # The hole this row exists for: a paper with no body, and every other row
    # green. A live run produced exactly this and the rubric called it green.
    hollow = check("# T\n\n## Abstract\n\nAn abstract.\n\n## References\n\n1. u1", ["u1"])
    assert hollow.passed, "without headings there is nothing to be missing"
    named = check(
        "# T\n\n## Abstract\n\nAn abstract.\n\n## References\n\n1. u1",
        ["u1"],
        headings=["The problem"],
    )
    assert named.signature() == ("complete",), named.signature()

    clean = check("The system is fast [1].", ["u1"])
    assert clean.passed, clean.report()
    assert clean.signature() == ()

    short = check("The system is fast [1].", ["u1"], min_words=MIN_WORDS)
    assert "length" in short.signature()

    thin = section_check(
        "TODO write this later",
        section={"word_target": 200, "key_questions": ["what failed"], "figures": []},
        findings=[{"id": "f1", "number": 1}],
        evidence="",
    )
    assert "length" in thin.signature()
    assert "stub" in thin.signature()
    assert "coverage" in thin.signature()
    specific = section_check(
        "Python 3.13 shipped in 2024 [1].",
        section={"word_target": 10, "key_questions": [], "figures": []},
        findings=[{"id": "f1", "number": 1, "quote": "Python 3.13 shipped in 2024"}],
        evidence="Python 3.13 shipped in 2024",
        word_target=10,
    )
    assert "cited" not in specific.signature(), specific.report()
    assert "sourced" not in specific.signature(), specific.report()
    assert has_specifics('The "Model Context Protocol" landed.')
    assert not has_specifics("The mechanism is local.")

    print("checks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
