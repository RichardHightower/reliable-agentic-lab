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
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
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


def ungrounded_identifiers(body: str, corpus: str) -> list[str]:
    """Lookup identifiers that appear nowhere in the retrieved evidence.

    Ported from `v3/article_pipeline/util/verified_facts.py`. A fabricated
    arXiv id or DOI reads exactly like a real one and survives every check that
    asks a model whether it is real. It does not survive being looked for in the
    text that was actually retrieved.
    """
    if not corpus:
        return []
    text = _mask_code(body)
    found: list[str] = []
    for pattern in (ARXIV, DOI, AUTHOR_YEAR):
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
    nearby = body[first.start() : body.find("\n\n", first.end()) if "\n\n" in body[first.end() :] else len(body)]
    if not EXIT_ORDER.search(nearby):
        return "Figure 1 must label done, then cost, then max turns"
    return None


def disallowed_reference_hosts(sources: list[str]) -> list[str]:
    """References from blogs and DeepWiki never become a paper's bibliography."""
    return [url for url in sources if not source_policy.is_allowed_url(url)]


def check(
    body: str,
    sources: list[str],
    *,
    base_dir: Path | str | None = None,
    corpus: str = "",
    headings: list[str] | None = None,
    enforce_source_policy: bool = False,
    enforce_loop_doctrine: bool = False,
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

    print("checks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
