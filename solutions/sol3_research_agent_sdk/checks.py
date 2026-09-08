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
    length        the paper clears the 2000-word floor (opt-in on paper runs)
    ledger_consistency a number or term disagrees with itself, or a forward ref is open
    corpus_marked a model-written corpus brief is labelled in the reference list
    gaps_stated   a coverage gap is named in Limitations
    charted       every plotted value is in the corpus and the caption cites

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
# The researcher keys its findings `fm-q1-03`, and that id is the only handle
# the writer holds for them, so that is what the writer cites. A numeric-only
# pattern read every one of those paragraphs as uncited, and no rewrite could
# fix it. `CITATION` still answers "which numbered reference is this", which
# a finding id cannot. `ANY_CITATION` answers "is this paragraph sourced".
# The researcher names its own findings, and the scheme changes every run:
# `fm-q1-01`, `reliability-failure-modes-q1-f2`, `f1`, `f3b`. A pattern that
# guesses the shape rejects the next one. Accept any bracketed token instead
# and let the `grounded` row decide whether it names a finding. The lookahead
# keeps a markdown link out, because `[the spec](url)` names a source without
# saying which claim it backs.
FINDING_ID = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9._-]*)\](?!\()")
ANY_CITATION = FINDING_ID
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
MIN_WORDS = 2000
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

# P3, first-use glossary terms. The writer marks a term in the section that
# first uses it, `<!-- TERM: orchestrator: the process that sequences roles -->`,
# and assembly harvests the mark the same way it harvests `NEEDS_SOURCE`: the
# comment is invisible in rendered markdown and gone from the body assembly
# writes, and the payload survives to become one glossary entry.
TERM_MARKER = re.compile(r"<!--\s*TERM:\s*(.*?)\s*-->", re.S)
# The glossary entry assembly writes for each captured term: `**term.** text`.
GLOSSARY_ENTRY = re.compile(r"^\*\*(.+?)\.\*\*\s*(.+)$", re.M)

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

# STE-S6, no contractions. `n't` covers do not/does not/etc; the pronoun list
# covers `it's`, `that's`, `we're`, and the like without also matching a
# genitive noun such as "the writer's card", which is not a contraction.
CONTRACTION = re.compile(
    r"\b[A-Za-z]+n't\b"
    r"|\b(?:i|you|we|they|it|he|she|that|there|who|what|here|let|how|when|where|why)"
    r"'(?:m|re|ve|ll|d|s)\b",
    re.I,
)
# STE-S7, no Latin abbreviations. Write "for example", not "e.g."
LATIN_ABBREV = re.compile(r"\b(?:e\.g\.|i\.e\.|etc\.)", re.I)
# Split into sentence-shaped chunks without breaking on the two periods inside
# "e.g."/"i.e."/"etc." themselves.
SENTENCE_END = re.compile(r"(?<!e\.g\.)(?<!i\.e\.)(?<!etc\.)(?<=[.!?])\s+", re.I)
REFERENCES_HEADING = re.compile(r"^#{1,6}\s+references?\s*$", re.I | re.M)

# STE-S5, no noun stack longer than three. There is no part-of-speech tagger
# in this codebase and this unit may not add one, so a token counts as a noun
# candidate only when it is not one of these function words and does not carry
# a verb or adverb ending. The list is short on purpose: articles,
# prepositions, conjunctions, pronouns/determiners, auxiliaries, and the
# common verbs and adverbs a briefing actually uses.
STE_FUNCTION_WORDS = frozenset(
    """
    a an the
    of in on at by for with about against between into through during before
    after above below to from up down over under again further than once off
    out across along among around behind beside beyond near toward towards
    upon within without via per amid versus plus minus
    and but or nor so yet because although though while if unless whether
    since as
    i you he she it we they this that these those who whom which what whose
    when where why how whatever whoever whichever wherever whenever
    someone something anyone anything everyone everything nothing each either
    neither all any some such one two three four five six seven eight nine
    ten first second third fourth fifth last next single multiple several
    various many few much more most less least other another same own new old
    whole entire additional its his her their our your my no not
    every cannot both none them due
    be is are was were been being have has had do does did will would shall
    should may might must can could
    run runs use uses need needs want wants show shows name names hold holds
    take takes give gives get gets know knows see sees say says call calls
    make makes made
    also only just still even already always never often sometimes here
    there now then well however therefore thus very quite rather instead
    hence otherwise nonetheless nevertheless regardless moreover furthermore
    meanwhile besides namely indeed perhaps maybe given whereas whereby
    thereby notwithstanding
    """.split()
)
# A gerund/participle, an adverb, or a third-person-singular verb / plain
# plural reads as a verb or an adverb, not a noun, often enough that excluding
# the ending is cheaper than tagging the word. "raises" in "Creatine raises
# phosphocreatine stores" is exactly this: a verb the suffix rule must reject
# so the sentence does not read as a four-noun stack. A trailing double `s`,
# `harness`, `process`, is left alone, because that `s` is not the plural or
# verb marker.
# ponytail: heuristic noun test, upgrade to a tagger if false positives appear
STE_VERB_ADVERB_SUFFIX = re.compile(r"(?:ing|ed|ly)$|(?<!s)s$", re.I)
# A handful of adjective endings read as a descriptive modifier, not the noun
# it modifies: "virtual", "single-source", "top level" survives, "folder-local
# Python virtual environment" does not once "folder-local" and "virtual" both
# drop out. A hyphenated token is almost always a compound modifier
# ("folder-local", "twenty-four") rather than the noun itself, and a spelled-
# out number is a quantifier, not a noun.
MODIFIER_SUFFIX = re.compile(r"(?:al|ous|ive|able|ible|ful|less|ic|ish|ary|ent|ant)$", re.I)
NUMBER_WORDS = frozenset(
    """
    one two three four five six seven eight nine ten eleven twelve thirteen
    fourteen fifteen sixteen seventeen eighteen nineteen twenty hundred
    thousand
    """.split()
)
# Digits stay inside a token so `E2E` is one token, not `E` and `E` either
# side of an invisible `2`; a token that carries a digit is never itself a
# noun candidate, so it still breaks the run instead of extending it.
STE_WORD_TOKEN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
NOUN_STACK_LIMIT = 3


def _mask_references(text: str) -> str:
    """Blank the references section. A host name in a URL is not body prose."""
    match = REFERENCES_HEADING.search(text)
    if not match:
        return text
    return text[: match.start()] + " " * (len(text) - match.start())


INLINE_URL = re.compile(r"https?://\S+")


def _mask_urls(text: str) -> str:
    """Blank an inline URL, through the next whitespace.

    A citation URL outside the reference list is not body prose either. A
    `your-account` path segment fabricated a `person` hit, and `unlock-guide`
    fabricated a `marketing` hit, both from a link a reader never reads as
    English.
    """
    return INLINE_URL.sub(lambda m: " " * len(m.group(0)), text)


def _mask_for_ste(text: str) -> str:
    """Code, an inline URL, and references, gone. Everything else is body prose."""
    return _mask_urls(_mask_references(_mask_code(text)))


def _prose_sentences(text: str) -> list[str]:
    """Sentence-shaped chunks of body prose. Skips headings, images, lists,
    tables, quotes, and fences, the same exemptions `uncited_claims` already
    grants, because none of those are a sentence a writer composed.
    """
    sentences: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith(("#", "!", "|", ">", "```", "-", "*")):
            continue
        if LIST_ITEM.match(block):
            continue
        for piece in SENTENCE_END.split(block):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def ste_language_violations(body: str) -> list[str]:
    """Sentences carrying a contraction or a Latin abbreviation.

    STE-S6 and STE-S7. Unconditional: a clean sentence passes by construction.
    """
    masked = _mask_for_ste(body)
    return [
        sentence[:160]
        for sentence in _prose_sentences(masked)
        if CONTRACTION.search(sentence) or LATIN_ABBREV.search(sentence)
    ]


def _noun_candidate(word: str) -> bool:
    if "-" in word or any(ch.isdigit() for ch in word):
        return False
    lowered = word.lower()
    if lowered in STE_FUNCTION_WORDS or lowered in NUMBER_WORDS:
        return False
    return not (STE_VERB_ADVERB_SUFFIX.search(word) or MODIFIER_SUFFIX.search(word))


NOUN_RUN_BREAK = re.compile(r"[,;:()]")


def noun_stacks(body: str, limit: int = NOUN_STACK_LIMIT) -> list[str]:
    """Runs of more than `limit` consecutive noun-candidate tokens.

    STE-S5. Advisory: reported, never a hard gate. A hyphenated token,
    `folder-local`, stays one token so it breaks the run as one unit, but it
    reads as a compound modifier and is never itself a candidate. A comma-
    separated list, "the researcher, verifier, writer, and gate boundaries",
    is enumeration, not a stack, so punctuation between two tokens also
    breaks the run.
    """
    masked = _mask_for_ste(body)
    hits: list[str] = []
    for sentence in _prose_sentences(masked):
        run: list[str] = []
        end = 0
        for match in STE_WORD_TOKEN.finditer(sentence):
            if NOUN_RUN_BREAK.search(sentence, end, match.start()):
                run = []
            end = match.end()
            word = match.group(0)
            if _noun_candidate(word):
                run.append(word)
                if len(run) == limit + 1:
                    hits.append(" ".join(run))
            else:
                run = []
    return hits


# P2, third person and no first person tour. SECOND_PERSON already grades one
# section at `section_check`; these rows raise the same regex, plus the two
# first-person phrases, to the whole paper.
WE_WILL = re.compile(r"\bwe\s+will\b", re.I)
IN_THIS_ARTICLE = re.compile(r"\bin\s+this\s+article\b", re.I)


def person_violations(body: str) -> list[str]:
    """Sentences carrying second person, or a first-person tour.

    Unconditional: third person, active voice, passes by construction.
    """
    masked = _mask_for_ste(body)
    return [
        sentence[:160]
        for sentence in _prose_sentences(masked)
        if SECOND_PERSON.search(sentence) or WE_WILL.search(sentence) or IN_THIS_ARTICLE.search(sentence)
    ]


# P2, the marketing lexicon. `\w*` covers the inflections a writer reaches
# for: leverages, unlocked, empowering, revolutionizes, seamlessly,
# robustness.
#
# `leverage`/`leverages` alone is exempt when the next word is `ratio(s)` or
# `buyout(s)`: a finance section naming a bank's leverage ratio is not the
# harness's marketing verb. `leveraging`/`leveraged` carry no such reading and
# stay banned outright.
MARKETING_VERB = re.compile(
    r"\bleverages?\b(?!\s+(?:ratios?|buyouts?)\b)"
    r"|\bleverag(?:ing|ed)\w*\b"
    r"|\b(?:unlock\w*|empower\w*|revolutioniz\w*|seamless\w*|robust\w*)\b",
    re.I,
)


def marketing_violations(body: str) -> list[str]:
    """Sentences carrying a marketing verb: leverage, unlock, empower,
    revolutionize, seamless, robust.

    Unconditional: a clean sentence passes by construction.
    """
    masked = _mask_for_ste(body)
    return [sentence[:160] for sentence in _prose_sentences(masked) if MARKETING_VERB.search(sentence)]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    # How far this row is from passing, when the row can measure it. `None`
    # means the row is pass or fail with nothing in between.
    distance: float | None = None
    # An advisory row is measured and reported and never blocks. Thirteen live
    # runs never stamped a section, and the last one died 24 words over a
    # ceiling after eight writer turns. The Deep Agents port made length
    # advisory in #294 and it is the port that finishes papers.
    advisory: bool = False


@dataclass
class Score:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed or c.advisory for c in self.checks)

    def signature(self) -> tuple[str, ...]:
        """What failed, not how it was worded.

        Two equal signatures mean the last attempt changed nothing, which is the
        stall the gate stops on. An advisory row is never in it.
        """
        return tuple(sorted(c.name for c in self.checks if not c.passed and not c.advisory))

    def advisories(self) -> tuple[str, ...]:
        """Rows that missed their mark and did not block. For the record."""
        return tuple(sorted(c.name for c in self.checks if not c.passed and c.advisory))

    def distances(self) -> dict[str, float]:
        """How far each failing row is from passing, where it can say.

        The stall rule compares row names. A section that went from 1912 words
        to 1400 against a 1500 ceiling failed `length` both times, so the names
        matched and the loop stopped while the writer was still closing the
        gap. Names alone cannot tell a section that is stuck from one that is
        working.
        """
        return {
            c.name: c.distance
            for c in self.checks
            if not c.passed and not c.advisory and c.distance is not None
        }

    def report(self) -> str:
        def label(c: Check) -> str:
            if c.passed:
                return "PASS"
            return "NOTE" if c.advisory else "FAIL"

        return "\n".join(f"{label(c)}  {c.name:<10} {c.detail}" for c in self.checks)

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


def ungrounded_citations(body: str, sources: list[str], numbers=None) -> list[str]:
    """Citation markers that point at a source the paper never listed.

    `numbers` is the run's citation registry, the numbers the reference list
    actually carries. Deriving them from position assumed `1..len(sources)`,
    and the registry is append-only, so a contradicted source or a resume
    leaves a legitimate gap. With reference 2 alone on the page, position
    rejected `[2]` and accepted `[1]`, which is the wrong answer twice.

    `None` keeps the positional rule for a caller that has no registry.
    """
    if numbers:
        available = {int(n) for n in numbers if int(n) > 0}
    else:
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
        if not ANY_CITATION.search(text):
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


def take_terms(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Pull every TERM marker out of the text, and return both.

    Mirrors `take_flags`. The marker names a term and its first-use definition,
    separated by the first colon; a marker with no definition half is not a
    glossary entry and is dropped rather than guessed at.
    """
    terms: list[tuple[str, str]] = []
    for payload in TERM_MARKER.findall(body):
        term, _, definition = payload.partition(":")
        term = term.strip()
        definition = definition.strip()
        if term and definition:
            terms.append((term, definition))
    return TERM_MARKER.sub("", body), terms


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


def section_bodies(body: str) -> dict[str, str]:
    """Each heading's text, running until the next heading of the same or a
    higher level. Keyed by the heading, lowercased.

    Two rows ended a section at the next heading of any level. A writer that
    names its key questions as sub-headings then has a section whose "body" is
    the blank line before its first sub-heading: `has_body` saw 0 words and
    `outline_coverage` saw none of the questions, both under a section that
    was complete on the page.
    """
    matches = list(SECTION_HEADING.finditer(body))
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        level = len(match.group(1))
        end = len(body)
        for later in matches[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        out[match.group(2).strip().lower()] = body[match.end() : end]
    return out


def _mask_section(text: str, name: str) -> str:
    """Blank one named heading's own text, keeping every other character offset.

    Grading whether a glossary term is used elsewhere in the body must not
    credit the glossary's own entry as that use.
    """
    matches = list(SECTION_HEADING.finditer(text))
    for index, match in enumerate(matches):
        if match.group(2).strip().lower() != name:
            continue
        level = len(match.group(1))
        end = len(text)
        for later in matches[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        start = match.start()
        return text[:start] + " " * (end - start) + text[end:]
    return text


def glossary_terms(body: str) -> dict[str, str]:
    """The term-to-definition map assembly wrote into `## Glossary`.

    Empty when the paper carries no Glossary heading, which is correct: no
    captured term means no section, not a missing one.
    """
    section = section_bodies(body).get("glossary", "")
    return {match.group(1).strip(): match.group(2).strip() for match in GLOSSARY_ENTRY.finditer(section)}


def glossary_incomplete(body: str) -> list[str]:
    """A term marked for capture that never reached the glossary.

    Assembly strips every `TERM` marker before it writes `paper.md`, so a
    marker surviving into the body handed to this row is itself the defect,
    the same defence `NEEDS_SOURCE` gives an unresolved flag. A body with no
    marker at all has nothing captured and passes by construction.
    """
    _, captured = take_terms(body)
    glossary = {term.lower() for term in glossary_terms(body)}
    return [term for term, _ in captured if term.lower() not in glossary]


def glossary_host_terms(terms, allowed_domains=None) -> list[str]:
    """Glossary entries that are a search host, not a term.

    The reference list may name `arxiv.org`. The glossary may not: it is prose
    about the subject, not a map of where the paper went looking.
    """
    hosts = {
        str(entry).strip().lower()
        for entry in (tuple(source_policy.SEED_ALLOWLIST) + tuple(allowed_domains or ()))
        if str(entry).strip()
    }
    return [term for term in terms if term.strip().lower().split("/")[0] in hosts or term.strip().lower() in hosts]


# Irregular plurals a paper actually reaches for. The regular suffix rules
# below cannot fold "criteria" to "criterion": neither form ends in `s`,
# `es`, or `ies`. Checked first, both directions, so either surface form
# folds to the singular.
IRREGULAR_PLURALS = {
    "criteria": "criterion",
    "phenomena": "phenomenon",
    "analyses": "analysis",
    "hypotheses": "hypothesis",
    "indices": "index",
}
_IRREGULAR_FOLD = {**IRREGULAR_PLURALS, **{singular: singular for singular in IRREGULAR_PLURALS.values()}}


def _stem(word: str) -> str:
    """A crude plural fold. An irregular pair folds first, from a fixed
    table (exit criteria / exit criterion and the like). Anything else
    folds by suffix: trailing `ies` to `y`, else strip a trailing `es` or
    `s`. Not a real stemmer, only enough that a term defined singular and
    used plural, or the reverse, is not graded as two words.
    """
    word = word.lower()
    if word in _IRREGULAR_FOLD:
        return _IRREGULAR_FOLD[word]
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 2:
        return word[:-2]
    if word.endswith("s") and len(word) > 1:
        return word[:-1]
    return word


WORD = re.compile(r"[A-Za-z][\w'-]*")


def _term_used(term: str, prose: str) -> bool:
    """Whether `term`'s stemmed words appear as a run inside `prose`.

    A literal phrase match rejected "one exit criterion" for the glossary
    term "exit criteria". Comparing stems catches the regular plural or
    singular a sentence actually used.
    """
    wanted = [_stem(w) for w in WORD.findall(term)]
    if not wanted:
        return False
    found = [_stem(w) for w in WORD.findall(prose)]
    span = len(wanted)
    return any(found[i : i + span] == wanted for i in range(len(found) - span + 1))


def glossary_unused(body: str) -> list[str]:
    """Glossary entries for a term the body never uses.

    "Uses" is generous on purpose. A stemmed match counts. A term repeated
    inside its own definition also counts: that sentence is the one the
    writer's own `TERM` marker carried, not the glossary inventing a use.
    """
    terms = glossary_terms(body)
    if not terms:
        return []
    prose = _mask_code(_mask_section(body, "glossary"))
    return [
        term
        for term, definition in terms.items()
        if not _term_used(term, prose) and not _term_used(term, definition)
    ]

def outline_coverage_gaps(body: str, outline: dict | None) -> list[str]:
    """Approved sections missing from the paper, or key questions never named.

    A key question is named when its text appears in the section body, case
    insensitive. The writer is handed the questions; this row checks they
    reached the page.
    """
    if not outline:
        return []
    bodies = section_bodies(body)
    gaps = []
    for section in outline.get("sections") or []:
        heading = (section.get("heading") or "").strip()
        key = heading.lower()
        if key not in bodies:
            gaps.append(f"section {heading!r} never written")
            continue
        text = bodies[key].lower()
        for question in section.get("key_questions") or []:
            # The question, not the researcher's note stapled to it. #351
            # applied this at the section gate; the paper gate kept matching
            # the raw 460-character string and could never find it.
            named = question_text(question)
            if named and named.lower() not in text:
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


def unplaced_figures(body: str, figures: list[dict] | None) -> list[str]:
    """Rendered diagrams the paper never linked.

    `unresolved_images` only grades links that exist, so a paper with a PNG
    on disk and no markdown image passed. Assembly is supposed to place
    them; this row catches a resume that assembled before that helper.
    """
    missing = []
    for figure in figures or []:
        path = str(figure.get("path") or "").strip()
        if not path:
            continue
        name = str(figure.get("name") or "")
        filename = Path(path).name
        if filename in body or (name and name in body):
            continue
        missing.append(name or filename)
    return missing


def non_publication_images(body: str) -> list[str]:
    """Diagrams must be judged `*_imagen.png`. Charts live under `charts/`."""
    bad = []
    for target in IMAGE.findall(body):
        if target.startswith(("http://", "https://", "data:")):
            continue
        if target.endswith("_imagen.png"):
            continue
        normalized = target.replace("\\", "/")
        if normalized.startswith("charts/") or "/charts/" in normalized:
            continue
        bad.append(target)
    return bad


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


def disallowed_reference_hosts(sources: list[str], allowed_domains=None) -> list[str]:
    """References from blogs and DeepWiki never become a paper's bibliography.

    `allowed_domains` is what the librarian admitted for this run. Without it
    the wall was the seed list, which has no `arxiv.org`, so the first paper
    this port assembled was rejected for citing the MAST paper through a host
    the run had admitted hours earlier. A `corpus:` reference names a claim in
    the brain, not a web host, and is not this row's business. Nor is a located
    cabinet source: the locator found the public copy of a paper the cabinet
    already held, which is a cross-reference the librarian never admitted, so
    the caller passes those references separately.
    """
    # Seed or admitted. The librarian proposes domains, and the seed is where
    # the GitHub orgs live: `github.com/anthropics`, `github.com/langchain-ai`.
    # Honouring the admitted list alone dropped those, and the paper was
    # rejected for citing the vendors' own repositories.
    domains = tuple(source_policy.SEED_ALLOWLIST) + tuple(allowed_domains or ())
    # A host check reads hosts. A `corpus:` key, a brain file path, or a
    # `not-found` placeholder has none, and each was rejected as a disallowed
    # host on the first real paper. Only a URL with a scheme is this row's.
    return [
        url
        for url in sources
        if str(url).lower().startswith(("http://", "https://"))
        and not source_policy.is_allowed_url(url, allowed_domains=domains)
    ]


def word_count(body: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", FENCE.sub("", body)))


def sections_without_prose(body: str, min_words: int) -> list[str]:
    if min_words <= 0:
        return []
    thin = []
    for match in SECTION_HEADING.finditer(body):
        heading = match.group(2).strip()
        if heading.lower() in PROSE_EXEMPT:
            continue
        chunk = section_bodies(body).get(heading.lower(), "")
        chunk = IMAGE.sub("", FENCE.sub("", chunk))
        words = re.findall(r"\b[\w'-]+\b", chunk)
        if len(words) < min_words:
            thin.append(f"{heading} ({len(words)} words)")
    return thin


def check(
    body: str,
    sources: list[str],
    reference_numbers: list[int] | None = None,
    *,
    base_dir: Path | str | None = None,
    corpus: str = "",
    headings: list[str] | None = None,
    outline: dict | None = None,
    enforce_source_policy: bool = False,
    allowed_domains=None,
    host_sources: list[str] | None = None,
    enforce_loop_doctrine: bool = False,
    enforce_structure: bool = False,
    min_words: int = 0,
    min_section_words: int = 0,
    ledger=None,
    gaps=None,
    claims=None,
    charts=None,
    diagrams=None,
) -> Score:
    """Score a paper. No model call."""
    checks: list[Check] = []

    checks.append(Check("sources", bool(sources), f"{len(sources)} sources retrieved"))

    if enforce_source_policy:
        # `host_sources` is the subset the allowlist governs. The caller drops
        # the located cabinet references from it, because the librarian never
        # admitted a domain for a paper the cabinet already held.
        graded = sources if host_sources is None else host_sources
        rejected = disallowed_reference_hosts(graded, allowed_domains)
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

    dangling = ungrounded_citations(body, sources, reference_numbers)
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
    unplaced = unplaced_figures(body, diagrams)
    image_fail = missing + unplaced
    checks.append(
        Check(
            "images",
            not image_fail,
            f"{len(IMAGE.findall(body))} figures resolve"
            if not image_fail
            else f"missing: {image_fail[:3]}",
        )
    )

    dashes = len(EM_DASH.findall(_mask_code(body)))
    checks.append(Check("style", dashes == 0, f"{dashes} em dashes"))

    ste_hits = ste_language_violations(body)
    checks.append(
        Check(
            "ste_language",
            not ste_hits,
            "no contractions or Latin abbreviations in body prose"
            if not ste_hits
            else f"contraction or e.g./i.e./etc. in: {ste_hits[0]!r}",
        )
    )

    stacks = noun_stacks(body)
    checks.append(
        Check(
            "noun_stack",
            not stacks,
            "no noun cluster longer than three"
            if not stacks
            else f"noun cluster: {stacks[0]!r}",
            # Advisory until the heuristic earns a hard gate: a deviation from
            # #456, stated in the P1-fix PR body. It still reports its detail
            # and never blocks `passed`.
            advisory=True,
        )
    )

    person_hits = person_violations(body)
    checks.append(
        Check(
            "person",
            not person_hits,
            "third person, no first person tour"
            if not person_hits
            else f"second person or first person tour in: {person_hits[0]!r}",
        )
    )

    marketing_hits = marketing_violations(body)
    checks.append(
        Check(
            "marketing",
            not marketing_hits,
            "no marketing verb in body prose"
            if not marketing_hits
            else f"marketing verb in: {marketing_hits[0]!r}",
        )
    )

    if enforce_structure:
        # Every row below is opt-in behind this one keyword, the house pattern
        # `enforce_source_policy` and `enforce_loop_doctrine` already set. A
        # clean snippet with no glossary at all passes both rows by
        # construction: no captured term means nothing missing, and no
        # glossary entry means nothing unused.
        incomplete = glossary_incomplete(body)
        checks.append(
            Check(
                "glossary_complete",
                not incomplete,
                "every first-use term reached the glossary"
                if not incomplete
                else f"missing from glossary: {incomplete[:3]}",
            )
        )
        terms = glossary_terms(body)
        unused = glossary_unused(body)
        host_hits = glossary_host_terms(terms, allowed_domains)
        exact_bad = sorted(set(unused) | set(host_hits))
        checks.append(
            Check(
                "glossary_exact",
                not exact_bad,
                "every glossary entry is a term the body uses"
                if not exact_bad
                else f"glossary-only or search-host term: {exact_bad[:3]}",
            )
        )

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

    if ledger is not None:
        clashes = ledger_inconsistencies(ledger)
        checks.append(
            Check(
                "ledger_consistency",
                not clashes,
                "numbers, terms, and forward refs agree"
                if not clashes
                else f"ledger: {clashes[:3]}",
            )
        )

    if claims is not None:
        unmarked = unmarked_corpus_briefs(body, claims)
        checks.append(
            Check(
                "corpus_marked",
                not unmarked,
                "model-written corpus briefs are labelled"
                if not unmarked
                else f"unmarked: {unmarked[:3]}",
            )
        )

    if gaps is not None:
        unnamed = unstated_gaps(body, gaps)
        checks.append(
            Check(
                "gaps_stated",
                not unnamed,
                "every coverage gap is named"
                if not unnamed
                else f"unnamed gaps: {unnamed[:2]}",
            )
        )

    rendered = [c for c in (charts or []) if c.get("path")]
    if rendered:
        import charts as charts_mod  # noqa: PLC0415

        failures = charts_mod.charted_failures(body, rendered, corpus or "")
        checks.append(
            Check(
                "charted",
                not failures,
                "every plotted value is in the corpus"
                if not failures
                else f"charted: {failures[:3]}",
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


MODEL_BRIEF_KINDS = (
    "brief",
    "deep_research_brief",
    "deep-research-brief",
    "model_brief",
    "model-written-brief",
)


def _specifics(text: str) -> set[str]:
    """Identifiers a later edit must not invent."""
    masked = _mask_code(text)
    found: set[str] = set()
    for rx in (ARXIV, DOI, AUTHOR_YEAR, PERCENT, VERSION, YEAR, BIG_INT, QUOTED):
        for match in rx.finditer(masked):
            token = match.group(1) if match.lastindex else match.group(0)
            if token:
                found.add(token.strip())
    return found


def new_claims(before: str, after: str) -> list[str]:
    """Specifics that appear in the edit and not in the original."""
    return sorted(_specifics(after) - _specifics(before))


def _ledger_entries(ledger) -> list[dict]:
    if ledger is None:
        return []
    if isinstance(ledger, list):
        return [item for item in ledger if isinstance(item, dict)]
    if isinstance(ledger, dict):
        return [item for item in (ledger.get("entries") or []) if isinstance(item, dict)]
    return []


def ledger_inconsistencies(ledger) -> list[str]:
    """A number with two values, a term defined twice, or an unresolved forward ref."""
    entries = _ledger_entries(ledger)
    issues: list[str] = []
    numbers: dict[tuple[str, str], str] = {}
    terms: dict[str, str] = {}
    defined: set[str] = set()
    forward: list[str] = []
    for entry in entries:
        for item in entry.get("numbers") or []:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("measures") or "").strip().lower(),
                str(item.get("unit") or "").strip().lower(),
            )
            value = str(item.get("value") or "").strip()
            if not value or key == ("", ""):
                continue
            previous = numbers.get(key)
            if previous is not None and previous != value:
                issues.append(f"{key[0] or key[1]} is {previous} and {value}")
            else:
                numbers[key] = value
        for item in entry.get("terms_defined") or []:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term") or "").strip()
            definition = str(item.get("definition") or "").strip()
            if not term:
                continue
            lowered = term.lower()
            defined.add(lowered)
            previous = terms.get(lowered)
            if previous is not None and previous != definition:
                issues.append(f"{term} defined twice")
            else:
                terms[lowered] = definition
        for item in entry.get("forward_refs") or []:
            if isinstance(item, dict):
                name = str(item.get("term") or item.get("ref") or "").strip()
            else:
                name = str(item).strip()
            if name:
                forward.append(name.lower())
    for name in forward:
        if name and name not in defined:
            issues.append(f"unresolved forward ref: {name}")
    return issues


def is_model_brief(claim: dict) -> bool:
    kind = str(claim.get("source_kind") or "").lower().replace(" ", "_")
    return any(token in kind for token in MODEL_BRIEF_KINDS) or str(
        claim.get("epistemic") or ""
    ).lower() in {"model_written", "model-written"}


def unmarked_corpus_briefs(body: str, claims: list) -> list[str]:
    labelled = "model-written brief" in body.lower()
    unmarked: list[str] = []
    for claim in claims or []:
        origin = str(claim.get("origin") or "").lower()
        if origin not in {"corpus", "brain"}:
            continue
        if not is_model_brief(claim):
            continue
        if labelled:
            return []
        unmarked.append(claim.get("source_url") or claim.get("id") or "corpus brief")
    return unmarked


def question_text(item) -> str:
    """The question a section must answer, without the researcher's note.

    The outliner appends its own research notes to a key question, so one
    question arrived 460 characters long and carrying two corpus ULIDs. The
    `coverage` row matched the whole string against the body, which meant the
    published paper had to reproduce the ULIDs to pass.

    The writer was shown the same raw string and told it must appear verbatim.
    It complied with an HTML comment, invisible in the rendered paper, and the
    `cited` row then failed on the comment. Two rows, mutually exclusive, no
    way through.

    The note is for the researcher, which is the phase that reads it. Strip a
    trailing parenthetical and keep the question.
    """
    text = item if not isinstance(item, dict) else item.get("text") or ""
    text = str(text).strip()
    # Only a note that trails the question. A parenthetical inside the question
    # is part of it.
    return re.sub(r"\s*\([^()]*\)\s*$", "", text).strip() or text


def unstated_gaps(body: str, gaps: list) -> list[str]:
    questions = []
    for gap in gaps or []:
        if isinstance(gap, str):
            text = gap.strip()
        elif isinstance(gap, dict):
            text = str(gap.get("question") or gap.get("text") or "").strip()
        else:
            text = ""
        if text:
            questions.append(text)
    if not questions:
        return []
    lower = body.lower()
    if not re.search(r"^#{1,6}\s+limitations?\b", body, re.I | re.M):
        return questions[:3]
    start = re.search(r"^#{1,6}\s+limitations?\b", body, re.I | re.M)
    rest = lower[start.start() :] if start else lower
    unnamed = []
    for question in questions:
        tokens = [w for w in re.findall(r"[a-z]{4,}", question.lower()) if w not in {"this", "that", "with", "from", "what", "when"}]
        if tokens and not any(token in rest for token in tokens[:4]):
            unnamed.append(question)
        elif not tokens and question.lower() not in rest:
            unnamed.append(question)
    return unnamed


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def section_check(
    body: str,
    *,
    section: dict | None = None,
    findings: list | None = None,
    evidence: str = "",
    word_target: int = 0,
    figures_given: list | None = None,
) -> Score:
    """Eight deterministic rows on one section, before any judge."""
    section = section or {}
    findings = findings or []
    checks: list[Check] = []
    target = int(word_target or section.get("word_target") or 0)
    words = word_count(body)
    if target:
        # Aim for the target within ten percent. Measured, reported to the
        # writer and the editor, and never a reason to fail the section.
        low = int(0.9 * target)
        high = int(1.1 * target)
        checks.append(
            Check(
                "length",
                low <= words <= high,
                f"{words} words (aim for {low}-{high}, target {target})",
                distance=float(max(low - words, words - high, 0)),
                advisory=True,
            )
        )
    else:
        checks.append(Check("length", True, f"{words} words"))

    stub = STUB.findall(body)
    checks.append(
        Check("stub", not stub, "no stub markers" if not stub else f"stub: {stub[:3]}")
    )

    questions = [
        text for text in (question_text(item) for item in section.get("key_questions") or []) if text
    ]
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
        if has_specifics(para) and not ANY_CITATION.search(para):
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
    # A citation is grounded when it names a finding, by its number or by its
    # id. The id branch was here already and never fired, because the numeric
    # pattern that fed this loop could not return one.
    for marker in FINDING_ID.findall(body):
        if marker in numbers or marker in ids:
            continue
        # A writer shortens a long id in prose. `outline.validate` already
        # resolves a bare ULID to its full corpus key, so a citation resolves
        # the same way: an unambiguous suffix is the finding it names.
        #
        # A bare number is never a suffix. `[1]` is a reference number, and
        # letting it match the tail of `s1-f1` or `s1-1` would silently bind a
        # citation to whichever finding happened to end in that digit.
        if marker.isdigit() or len([i for i in ids if i.endswith(f"-{marker}")]) != 1:
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

    # The row grades whether the writer placed the figures it was handed. The
    # `diagram` phase runs after `sections`, so on the first pass `diagrams.json`
    # does not exist and the writer receives none. Grading it against the
    # outline's plan failed the writer for a placement the harness never made
    # possible. `figures_given` is None when the caller does not know, and the
    # plan stands in.
    source = section.get("figures") if figures_given is None else figures_given
    planned = [
        fig.get("name")
        for fig in (source or [])
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
    # A heading is a paragraph, and the outline hands the writer key questions
    # that the `coverage` row then demands it name. The writer names them as
    # subheadings, and this row read those as rhetoric. Remove the heading and
    # `coverage` fails, keep it and `style` fails. Every other rule in this
    # file already skips a heading.
    if any(
        RHETORICAL.search(p.splitlines()[-1])
        for p in _paragraphs(body)
        if p and not p.startswith("#")
    ):
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

    assert new_claims("done first", "done first. Python 3.13") == ["3.13"]
    clash = ledger_inconsistencies(
        {
            "entries": [
                {"numbers": [{"value": "12", "unit": "USD", "measures": "budget"}]},
                {"numbers": [{"value": "40", "unit": "USD", "measures": "budget"}]},
            ]
        }
    )
    assert clash
    assert unmarked_corpus_briefs(
        "no label",
        [{"origin": "corpus", "source_kind": "deep_research_brief", "source_url": "brain:x"}],
    )
    assert unstated_gaps("## Body\n\nx", [{"question": "how watchdog timers fire"}])

    thin = section_check(
        "TODO write this later",
        section={"word_target": 200, "key_questions": ["what failed"], "figures": []},
        findings=[{"id": "f1", "number": 1}],
        evidence="",
    )
    assert "length" in thin.advisories()
    assert "length" not in thin.signature()
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

    assert ste_language_violations("The writer does not skip a step.") == []
    hit = ste_language_violations("The writer doesn't skip a step.")
    assert hit and "doesn't" in hit[0]
    assert ste_language_violations("For example, the writer names the actor.") == []
    assert ste_language_violations("The writer names the actor, e.g. the host.")
    assert ste_language_violations("`The writer doesn't skip a step.`") == [], "a code span is masked"
    assert ste_language_violations("## References\n\nSee it's fine at example.com.") == [], (
        "the references section is masked"
    )
    assert ste_language_violations("The writer's card names the actor.") == [], (
        "a genitive is not a contraction"
    )
    assert noun_stacks("The orchestrator charges the budget before the writer runs.") == []
    assert noun_stacks("A loop harness gate ledger ships every seminar.")
    assert noun_stacks("The independent researcher, verifier, writer, and gate boundaries appear.") == [], (
        "a comma-separated list is enumeration, not a stack"
    )
    # The judge's five reported false positives on PR #492, each traced to a
    # missing guard and now fixed: a suffix that reads as a modifier, a
    # hyphen that reads as a compound modifier, a missing function word, and
    # a digit swallowed by the old tokenizer.
    assert noun_stacks("This is a standalone Claude Agent SDK for the seminar.") == [], (
        "Agent ends in -ent, a modifier suffix"
    )
    assert noun_stacks("Each lab uses a folder-local Python virtual environment.") == [], (
        "folder-local is a hyphenated modifier and virtual ends in -al"
    )
    assert noun_stacks("The plan names a twenty-four question research phase.") == [], (
        "twenty-four is a hyphenated number word"
    )
    assert noun_stacks("The allowlist governs every top level domain.") == [], (
        "every is a function word"
    )
    assert noun_stacks("The default live E2E run costs about a dollar.") == [], (
        "E2E is one digit-bearing token, not two bare letters"
    )

    assert person_violations("The orchestrator charges the budget before the writer runs.") == []
    hit = person_violations("You should charge the budget before the writer runs.")
    assert hit and "You should" in hit[0]
    assert person_violations("We will now look at the budget in detail.")
    assert person_violations("In this article, the orchestrator sequences every role.")
    assert person_violations("`You should not skip a step.`") == [], "a code span is masked"
    assert person_violations("## References\n\nSee you at example.com.") == [], (
        "the references section is masked"
    )

    assert marketing_violations("The orchestrator sequences roles in a fixed order.") == []
    assert marketing_violations("The design will leverage existing infrastructure.")
    assert marketing_violations("The mechanism unlocks new throughput for the pipeline.")
    assert marketing_violations("`a seamless robust retry loop`") == [], "a code span is masked"
    assert marketing_violations("## References\n\n1. https://example.com/unlock-guide\n") == [], (
        "the references section is masked"
    )

    # Follow-up from the P2 judge: a finance term is not the marketing verb.
    assert marketing_violations("The bank's leverage ratio fell in the quarter.") == []
    assert marketing_violations("The fund's leverages ratios stayed flat.") == []
    assert marketing_violations("We leverage the SDK for every call.")
    assert marketing_violations("The design was leveraged to cut costs.")

    # Follow-up from the P2 judge: an inline URL is not body prose either.
    assert person_violations("See https://example.org/your-account for the record.") == []
    assert person_violations("See the record at your account page.")
    assert marketing_violations("See https://example.com/unlock-guide for the record.") == []

    body, terms = take_terms("A point. <!-- TERM: orchestrator: sequences roles --> More.")
    assert terms == [("orchestrator", "sequences roles")]
    assert "TERM" not in body
    assert take_terms("no markers")[1] == []

    glossed = "## Glossary\n\n**orchestrator.** Sequences roles.\n\n**widget.** Unused elsewhere.\n"
    assert glossary_terms(glossed) == {"orchestrator": "Sequences roles.", "widget": "Unused elsewhere."}
    assert glossary_terms("## Body\n\nno glossary here") == {}

    marked = "The orchestrator runs first. <!-- TERM: orchestrator: sequences roles -->"
    assert glossary_incomplete(marked) == ["orchestrator"], "no glossary section, nothing captured it"
    assert glossary_incomplete(marked + "\n\n" + glossed) == []
    assert glossary_incomplete("no marker at all") == []

    assert glossary_unused("The orchestrator runs first.\n\n" + glossed) == ["widget"]
    assert glossary_unused("## Glossary\n\n**widget.** Unused.\n") == ["widget"]
    assert glossary_unused("## Body\n\nno glossary here") == []
    assert glossary_host_terms(["docs.langchain.com", "widget"]) == ["docs.langchain.com"]

    # Follow-up from the PR #499 judge: a stemmed match, and a term repeated
    # inside its own definition, both count as used.
    plural_only = "A point about workflows.\n\n## Glossary\n\n**workflow.** A sequence of steps a run executes.\n"
    assert glossary_unused(plural_only) == []
    self_defined = "A point about the process.\n\n## Glossary\n\n**orchestrator.** The orchestrator sequences roles.\n"
    assert glossary_unused(self_defined) == []

    # Follow-up: an irregular plural is folded from a fixed table, not a
    # suffix rule, since "criteria" does not end in s, es, or ies.
    irregular = "The run checks one exit criterion.\n\n## Glossary\n\n**exit criteria.** What a run must clear before it stops.\n"
    assert glossary_unused(irregular) == []

    print("checks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
