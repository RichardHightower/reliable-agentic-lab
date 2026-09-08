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
    question_heading a heading pastes a question instead of answering it
    policy_leak   the body names a search host or narrates the run's own retrieval boundary
    caveat_once   a caveat sentence or a numeric finding repeats across sections

`complete` looks redundant and is not. Without it a paper with no body at all
passes every other row: the abstract is exempt from `cited`, the reference list
is intact, and there are no figures to break and no prose to hold an em dash. A
live run produced exactly that, and the rubric called it green.

`sourced` is the one that matters most and is the least obvious. A web search
cannot refute a citation that was never published. Asking a model "is this real"
gets you a confident yes. The only thing that catches a fabricated reference is
checking its identifier against the corpus that was actually retrieved.

Rows `check()` added later, still Python's, still no vote for the model:

    sources       at least one source was retrieved
    hosts         every graded reference host is on the allowlist
    doctrine      the loop-doctrine exit order and the figure order agree
    figure_assets every diagram is a judged publication asset, not a sketch
    outline_coverage every approved section and key question is on the page
    abstract_matches_body the abstract and introduction match the body they summarize
    ste_language  no contraction, no e.g./i.e./etc. in body prose
    noun_stack    no noun cluster longer than three (advisory)
    person        no second person, no first-person tour
    marketing     no banned marketing verb in body prose
    next_step     the last prose heading is a next-step section, not a bare Conclusion
    cta_language  the next-step section sells nothing and every step stays short
    glossary_complete every first-use term reached the glossary
    glossary_exact every glossary entry is a term the body actually uses
    captioned     every placed image is followed by a Figure N. caption
    figure_referenced every placed figure is named Figure N in its own section's prose
    skip_noted    every skipped figure is named, with its reason, on the page
    methods_present the Methods section, Python-written from the run record, is present
    conclusion_present the Conclusion section, one writer turn from the body, is present
    study_table   one Evidence summary row per human-study claim, placed after Methods
    front_matter  the byline, date, provenance line, and conflicts line sit above the Abstract

Belt versus judge, matching the house style page's ownership table
(https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style).
Python grades every row above. `research-judge.md` grades what Python cannot:
defined, structured, evidenced, limited, figured, depth, repetition, voice,
and abstract_matches_body, where Python catches only the fixed overclaim list
and the judge catches the rest.

    python3 checks.py --demo
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import outline as outlines
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

# Sections Python writes directly, never through a writer turn: Methods from
# the run record, and the Evidence summary table from the ledger (#478).
# Neither carries a citation of its own to demand and neither is prose a
# length floor should measure. A name-based exemption, not an incidental
# formatting rule: PR #535 judge revision, item (b) and F2. The day either
# section's own rendering changes, this set is the one place that still has
# to say why the section is exempt.
PYTHON_WRITTEN_SECTIONS = {"methods", "evidence summary"}

# #479. The byline, date, provenance, and conflicts block, above the
# Abstract. `uncited_claims` is the one row that walks the whole body by
# heading, H1 included, so it is the one row that needs this name; every
# other section-keyed check reads only `## `-and-deeper headings and never
# sees the zone between the title and the first one at all.
FRONT_MATTER_SECTION = "front matter"

# Sections where a paragraph without a citation is correct, not sloppy. An
# abstract summarizes material that is cited below it, and a reference list is
# the citation. Demanding a marker in either produces a paper that cites its own
# bibliography.
UNCITED_SECTIONS = {"abstract", "references", "summary", FRONT_MATTER_SECTION} | PYTHON_WRITTEN_SECTIONS

# Opt-in floors. Unit tests of other rows stay short. The pipeline passes
# these when it is producing a paper rather than exercising one phase.
# Abstract is assembler-owned from the outline thesis, so the section floor
# does not apply to it. The whole-paper floor still does.
MIN_WORDS = 2000
MIN_SECTION_WORDS = 80
# The conclusion joins the abstract here for the same reason: `OfflineTurns`
# stands in with a short, deterministic placeholder rather than a full-length
# turn, so the floor below would fail every offline run over a section no
# model actually wrote at length. #478. Methods and the study table join for
# the reason above: neither is prose a length floor should measure. PR #535
# judge revision B2.
PROSE_EXEMPT = {"references", "figures", "abstract", "conclusion"} | PYTHON_WRITTEN_SECTIONS
SECTION_HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.M)
# A judge on PR #529 found three fence shapes this pattern missed. Group 1 is
# the delimiter run, backtick or tilde, backreferenced so a closer must use
# the same character; group 2 is the info string, unrestricted so a trailing
# space or a hyphenated language tag (`objective-c`) still opens a fence;
# group 3 is the body. The closer is `\1` on its own line, or end of body
# when no closer exists, so an unclosed fence masks to the end rather than
# leaving its content, headings included, exposed as prose.
#
# The trailing `(?=\n|\Z)` is a lookahead, not a consumed match. A judge on
# the same PR found the first version consumed that newline, so a heading
# on the line right after a closing fence, with no blank line between, had
# its own leading newline swallowed into the masked span and replaced with
# a space along with it. `SECTION_HEADING`'s `^` anchor needs an actual
# newline before it, not a space, so that heading vanished from every row
# that scans it, and `missing_sections` reported a present `References` as
# missing. The lookahead ends the match before that newline, leaving it in
# place.
FENCE = re.compile(r"^[ \t]*([`~]{3,})([^\n]*)\n(.*?)(?:\n[ \t]*\1[ \t]*(?=\n|\Z)|\Z)", re.M | re.S)
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


def _mask_fences(text: str) -> str:
    """Blank a fenced code block, keeping every character offset.

    A judge on PR #508 found a `##` line inside a quoted markdown snippet
    counted as a heading in `question_heading`, and every sibling row that
    scans headings has the same exposure: `next_step` (`last_prose_heading`),
    the outline coverage scan, the `sections`/`complete` row, and the
    section-boundary helpers they all share. Narrower than `_mask_code` on
    purpose: an inline single-backtick span never spans a line, so it cannot
    fake a heading, and blanking it here would also blank a heading's own
    inline code, e.g. `## Using `--brain``. #509
    """
    return FENCE.sub(lambda m: " " * len(m.group(0)), text)


def _headings(text: str) -> list[re.Match]:
    """`SECTION_HEADING` matches read from the fence-masked body.

    One call, and every row below reads through it, so a heading inside a
    fenced snippet is never counted as paper structure. #509
    """
    return list(SECTION_HEADING.finditer(_mask_fences(text)))


def _mask_for_ste(text: str) -> str:
    """Code, an inline URL, and references, gone. Everything else is body prose."""
    return _mask_urls(_mask_references(_mask_code(text)))


def _prose_sentences(text: str) -> list[str]:
    """Sentence-shaped chunks of body prose. Skips headings, images, lists,
    tables, quotes, fences, and a `Figure N.` caption, the same exemptions
    `uncited_claims` already grants, because none of those are a sentence a
    writer composed. A caption is system-generated from a diagram's own
    node labels, not prose a writer is held to the STE belt for. #464.
    """
    sentences: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith(("#", "!", "|", ">", "```", "-", "*")):
            continue
        if LIST_ITEM.match(block) or FIGURE_CAPTION.match(block):
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


# P6, the paper does not narrate the harness. #452 #465 #412: the finished
# creatine paper named arxiv.org 42 times and spent whole paragraphs saying no
# preprint was found. A reader of a sports-nutrition paper does not care which
# index a search was scoped to.
POLICY_LEAK_PHRASES = (
    "preprint search",
    "search scope",
    "no study was hosted on",
)
POLICY_LEAK_PHRASE = re.compile(
    "|".join(re.escape(phrase) for phrase in POLICY_LEAK_PHRASES), re.I
)


def _mask_for_policy(text: str) -> str:
    """Code, a URL, References, and Methods, gone. Methods is where #478
    names the admitted hosts by design; nothing else in the body may.
    """
    return _mask_section(_mask_for_ste(text), "methods")


def policy_leak_violations(body: str, allowed_domains=None) -> list[str]:
    """Sentences that narrate the harness's own source policy instead of the
    subject: a search host name, or one of the three retrieval phrases.

    Unconditional: a clean sentence passes by construction. Methods and
    References are exempt; every other section is graded.
    """
    masked = _mask_for_policy(body)
    hosts = [
        str(host).strip()
        for host in (tuple(source_policy.SEED_ALLOWLIST) + tuple(allowed_domains or ()))
        if str(host).strip()
    ]
    host_pattern = (
        re.compile(r"\b(?:" + "|".join(re.escape(host) for host in hosts) + r")\b", re.I)
        if hosts
        else None
    )
    hits = []
    for sentence in _prose_sentences(masked):
        if POLICY_LEAK_PHRASE.search(sentence) or (host_pattern and host_pattern.search(sentence)):
            hits.append(sentence[:160])
    return hits


# P4, the next-step section may use imperative CTA steps, but it may not sell.
# `unlock`, `revolutionize`, and the rest of the marketing lexicon are already
# banned everywhere by `MARKETING_VERB`; this phrase list is the CTA ban list
# ticket #460 names, minus those two, which are not marketing verbs on their
# own.
CTA_PHRASE = re.compile(
    r"\b(buy|sign up|subscribe|get started|only solution|contact sales|transform your|contact us)\b",
    re.I,
)


def _cta_steps(text: str) -> list[str]:
    """Every step in the next-step section: a bullet line, or a prose
    sentence when a block carries no bullet. A CTA line is short by design,
    so the word cap and the ban list both grade per step, not per section.
    """
    masked = _mask_code(text)
    steps: list[str] = []
    for block in re.split(r"\n\s*\n", masked):
        block = block.strip()
        if not block:
            continue
        bullets = [line.strip() for line in block.splitlines() if re.match(r"^[-*]\s+", line.strip())]
        if bullets:
            steps += [re.sub(r"^[-*]\s+", "", line) for line in bullets]
            continue
        if block.startswith(("#", "!", "|", ">", "```")):
            continue
        for piece in SENTENCE_END.split(block):
            piece = piece.strip()
            if piece:
                steps.append(piece)
    return steps


def cta_violations(section_text: str) -> list[str]:
    """Every step in the next-step section that sells, or runs past 20 words.

    Scoped to the one section `check` hands it. `unlock` in a body section is
    the unconditional `marketing` row's business, not this one.
    """
    hits = []
    for step in _cta_steps(section_text):
        words = len(re.findall(r"\b[\w'-]+\b", step))
        if CTA_PHRASE.search(step) or MARKETING_VERB.search(step) or words > 20:
            hits.append(step[:160])
    return hits


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
            # #479. The H1 title's own block opens the front-matter zone,
            # exempt the same way Methods and References are: nothing there
            # is a claim to cite. A real `## ` heading below it overwrites
            # `section` as it always did.
            section = (
                FRONT_MATTER_SECTION
                if text.startswith("# ") and not text.startswith("##")
                else heading.group(1).strip().lower()
            )
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
    matches = _headings(body)
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
    matches = _headings(text)
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


def _mask_sections(text: str, names: set[str]) -> str:
    """Blank every heading in `names`, one pass, in an order that cannot
    matter.

    Calling `_mask_section` once per name chains: it re-scans the string the
    previous call already mutated, and a mask always eats the newline right
    before the next heading (the mask ends exactly where that heading's `#`
    starts). Two masked sections sitting back to back lose the line break
    between them on the first call, so the second call's own `_headings`
    scan never sees the second heading at all, only sometimes, whichever
    name a set happened to iterate first. Spans are computed once, from the
    untouched text, so this never depends on scanning a text a prior mask
    already edited.
    """
    matches = _headings(text)
    spans = []
    for index, match in enumerate(matches):
        if match.group(2).strip().lower() not in names:
            continue
        level = len(match.group(1))
        end = len(text)
        for later in matches[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        spans.append((match.start(), end))
    out = text
    for start, end in spans:
        out = out[:start] + " " * (end - start) + out[end:]
    return out


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

# P4. Glossary and References are assembled, never written by a model, so the
# last heading a writer could have produced is the last one before them.
# Figures is assembled too, an orphan appendix for a diagram no section
# claimed, so it is not a prose section either.
NON_PROSE_TRAILING = {"glossary", "references", "figures"}


def last_prose_heading(body: str) -> str | None:
    """The last top-level (`##`) section heading before Glossary and References.

    Frozen order: front matter, Abstract, Introduction, Methods, study table,
    body sections, Conclusion, Next step, Glossary, References. `None` when
    the paper has no top-level heading at all.
    """
    headings = [
        match.group(2).strip()
        for match in _headings(body)
        if len(match.group(1)) == 2 and match.group(2).strip().lower() not in NON_PROSE_TRAILING
    ]
    return headings[-1] if headings else None


# Copied from Deep Agents `sections.py` `STOP`/`_terms`, the token-overlap
# rule this row and `section_check`'s `coverage` row now both apply. #385:
# requiring the verbatim question taught the writer to paste it as a
# heading. Scoring whether the question is answered removes that incentive.
# Copied, not imported, per the house rule against a shared loop package.
#
# #510. A judge on PR #508 scored the #385 gist question "Which trace
# counts were reported by the MAST taxonomy paper?" as answered by a body
# that shares only "paper" with it, because the twenty-word list here
# missed ordinary function words: `was`, `were`, `which`, `when`, `has`,
# `not`, `also`, `more`, `should`. `STE_FUNCTION_WORDS`, above, already
# names every one of those.
#
# It also names `run`, `calls`, `names`, `uses`, and `holds`, the STE-S5
# noun-stack row's own verb-suffix exceptions, not a question's function
# words. This repo's own papers are about a loop that runs, a section that
# calls a turn, a term a glossary names: a coverage row that stops those
# words scores a question about them on almost nothing. A judge on PR #529
# found exactly that: "How many tool calls does a run use before it
# holds?" fell to one content term, `tool`, easier to satisfy than the old
# rule's seven. `COVERAGE_VERB_EXCEPTIONS` is that verb block, subtracted
# back out, so a domain verb stays a content word here even though it is
# not one for the noun-stack row it was written for.
COVERAGE_VERB_EXCEPTIONS = frozenset(
    """
    run runs use uses need needs want wants show shows name names hold holds
    take takes give gives get gets know knows see sees say says call calls
    make makes made
    """.split()
)
COVERAGE_STOP = STE_FUNCTION_WORDS - COVERAGE_VERB_EXCEPTIONS


def _coverage_terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in COVERAGE_STOP and len(w) > 2}


def _coverage_needed(terms: set[str]) -> int:
    """A third of the question's content terms, floored at two, and never
    more than the question actually has to give. #510

    A fifteen-term question used to need two incidental matches, the same
    floor a two-term question needed. Scaling the requirement with the
    question closes that gap while a short question still only has to name
    what it actually asks: `min(2, len(terms))` was already the answer for
    `len(terms) <= 2`, and stays that answer here.
    """
    if not terms:
        return 0
    return min(len(terms), max(2, -(-len(terms) // 3)))


def outline_coverage_gaps(body: str, outline: dict | None) -> list[str]:
    """Approved sections missing from the paper, or key questions never answered.

    A key question is answered when its terms overlap the section body. The
    exact wording is not required; a heading that pastes the question passes
    this row for the wrong reason, which is what `question_headings` catches.
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
        body_terms = _coverage_terms(bodies[key])
        for question in section.get("key_questions") or []:
            # The question, not the researcher's note stapled to it. #351
            # applied this at the section gate; the paper gate kept matching
            # the raw 460-character string and could never find it.
            named = question_text(question)
            terms = _coverage_terms(named) if named else set()
            if terms and len(terms & body_terms) < _coverage_needed(terms):
                gaps.append(f"section {heading!r} never answers {named!r}")
    return gaps


def question_headings(body: str, outline: dict | None) -> list[str]:
    """H2/H3 headings that are pasted questions, not the answers to them.

    A heading that ends in a question mark reads as a slide prompt, not a
    finding. A heading that repeats an outline key question verbatim is the
    same defect with the closing punctuation changed. #385: coverage cannot
    require the answer in the body and also accept the question as the
    heading; this row closes the second half.

    The question and the heading both drop trailing `?.:;!` before the
    comparison. A judge on PR #508 found the P5 version stripped only a
    trailing `?`, so a key question the writer re-punctuated with a period
    or a colon as a heading still matched the wanted set and slipped past.
    """
    wanted = set()
    for section in (outline or {}).get("sections") or []:
        for item in section.get("key_questions") or []:
            text = question_text(item).strip().lower().rstrip("?.:;!").strip()
            if text:
                wanted.add(text)
    bad = []
    for match in _headings(body):
        if len(match.group(1)) not in (2, 3):
            continue
        heading = match.group(2).strip()
        stripped = heading.lower().rstrip("?.:;!").strip()
        if heading.endswith("?") or stripped in wanted:
            bad.append(heading)
    return bad


# P7, #472. The abstract restates the body and may not say more than the body
# says. It runs on the abstract and on the introduction's first paragraph. A
# sentence citing a single-source claim needs a hedge word in that sentence,
# a fixed overclaim phrase never appears, and a number the abstract cites
# must also appear in the body: the abstract restates the body, so a claim
# only the abstract makes was never checked against the body it summarizes.
ABSTRACT_HEDGE = re.compile(r"single|one study|one trial|preliminary", re.I)
ABSTRACT_OVERCLAIM = re.compile(r"\b(?:proves|definitively|conclusively|establishes that)\b", re.I)
_MARKER_ONLY = re.compile(r"^(?:\[\d+\]\s*)+$")


def _cited_sentences(text: str) -> list[str]:
    """`_prose_sentences`, with a trailing citation-only fragment folded back
    into the sentence before it.

    The writer cites after the period, `"...notices. [1]"`, so `SENTENCE_END`
    splits the marker into a sentence of its own. Grading that fragment for a
    hedge word finds nothing, because the hedge is one sentence back.
    """
    merged: list[str] = []
    for sentence in _prose_sentences(text):
        if _MARKER_ONLY.match(sentence) and merged:
            merged[-1] = f"{merged[-1]} {sentence}"
        else:
            merged.append(sentence)
    return merged


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block and not block.startswith(("#", "!", "|", ">", "```", "-", "*")):
            return block
    return ""


def _single_source_numbers(claims: list[dict] | None) -> set[int]:
    """Reference numbers backed by exactly one source, decided per claim.

    This port has no formal corroboration count yet (#471, #473 land it). A
    claim the independent verifier confirmed from a second, distinct URL is
    treated as not single source; every other numbered claim is, because
    nothing else in this port's ledger distinguishes them. Two claims can
    share one number: flagging it whenever any claim on it is single-source
    forced a hedge onto a sentence citing the other, corroborated claim.
    A number counts as single-source only when every claim on it does.
    """
    by_number: dict[int, list[bool]] = {}
    for claim in claims or []:
        number = claim.get("number")
        if not number:
            continue
        source = str(claim.get("source_url") or "").strip()
        verifier = str(claim.get("verifier_url") or "").strip()
        single = not verifier or verifier == source
        by_number.setdefault(int(number), []).append(single)
    return {number for number, flags in by_number.items() if all(flags)}


def abstract_matches_body(body: str, claims: list[dict] | None = None) -> list[str]:
    """The abstract, and the introduction's first paragraph, state only what
    the body states.

    Inert with no `## Abstract` heading: nothing to grade. Otherwise the row
    itself is unconditional: it always runs, and the overclaim and
    number-in-body rules need no claim data. The hedge rule alone needs
    `claims` to know which numbers are single-source; `paper.check` passes
    the run's claims on every call, so that rule runs live in production
    too, not only when a caller happens to supply the list.

    Every graded sentence citing a single-source claim carries a hedge word,
    and a fixed overclaim phrase never appears. The abstract carries one more
    rule the introduction does not: a number it cites must appear in the
    body too. The introduction is the body; a number appearing there for the
    first time is not a defect.
    """
    sections = section_bodies(body)
    abstract = sections.get("abstract", "")
    if not abstract.strip():
        return []
    single_source = _single_source_numbers(claims)
    rest_of_body = body.replace(abstract, "", 1)
    excerpts = [("abstract", abstract, True)]
    intro_first = _first_paragraph(sections.get("introduction", ""))
    if intro_first:
        excerpts.append(("introduction", intro_first, False))
    issues: list[str] = []
    for label, excerpt, check_numbers in excerpts:
        for sentence in _cited_sentences(excerpt):
            cited = {int(n) for n in CITATION.findall(sentence)}
            if cited & single_source and not ABSTRACT_HEDGE.search(sentence):
                issues.append(f"{label}: unhedged single-source claim: {sentence[:70]!r}")
            if ABSTRACT_OVERCLAIM.search(sentence):
                issues.append(f"{label}: overclaim in: {sentence[:70]!r}")
        if check_numbers:
            for number in {int(n) for n in CITATION.findall(excerpt)}:
                if f"[{number}]" not in rest_of_body:
                    issues.append(f"{label}: [{number}] does not appear in the body")
    return issues


# Methods restates run-record numbers (hosts, dates, caps spent) that have
# nothing to do with a body finding's own numbers, and the same count can
# land in both by coincidence. #478: exempt for the same reason Glossary and
# References are, not narrative prose a "said once" rule should hold.
# Conclusion stays out of this set on purpose. PR #535 judge revision F3: its
# own prompt asks it to restate the body, the same exposure the abstract
# already carries and is graded on (`repeat_shingles`'s own abstract-only
# exemption is narrower than this set). B4 (`_persist_trim` now stamps
# `conclusion.json`) is the fix: a caught repeat gets a real repair path
# instead of a silent pass.
CAVEAT_EXEMPT_SECTIONS = {"glossary", "references"} | PYTHON_WRITTEN_SECTIONS
# P9, #477. A numeric finding stated in full twice, with the same value and
# unit, is a repeat even when the wording around it differs enough to dodge
# the shingle threshold below: "2.4 percent" once, then "2.4%" a paragraph
# later, is one finding either way.
#
# Methods is exempt from this rule once P11 lands: it is Python-written from
# the run's own ledger, so the same count it names (sources retrieved,
# claims verified) legitimately recurs there in the same units a body
# section reports for an unrelated reason. Not built yet; noted here so the
# exemption is not lost when Methods is.
NUMERIC_FULL = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b", re.I)
# D2, #477. The whole-paper pass replaces a repeat with a short sentence
# that points back to the section stating it first. That sentence is not
# itself a repeat, even when the exact same short sentence appears in two
# sections pointing at the same source: the writer card for the pass is
# told to open with exactly one of these four phrases, so a sentence this
# short starting this way is recognized as a pointer, not a restatement.
#
# #521. The exemption keys on the cue, not the length: a cap of 12 words
# failed the pass's own output once the source section's heading ran past
# four words, because the fixed frame around the heading is already 8
# words. A live model-written outline names sections in five or six words
# routinely; the offline fixtures never hit this because their headings
# are one or two words. 24 words covers a heading well past what a real
# outline produces while still being far too short to smuggle in a fresh
# restatement of a finding.
BACK_REFERENCE_CUES = ("as stated in", "as noted in", "as shown in", "see ")
BACK_REFERENCE_MAX_WORDS = 24


def _is_back_reference(sentence: str, headings: frozenset[str] | None = None) -> bool:
    """A short pointer sentence that names one of the paper's own `##`
    headings, exempt from `caveat_once` because it points at a finding
    instead of restating it.

    The cue phrase alone used to be enough: a judge on #531's line found a
    manufactured "See ..." sentence under 24 words that named no section
    at all could dodge the row by cue and length alone, then repeat across
    sections just like any other sentence. Naming a real heading is the
    difference between a pointer and a restatement wearing a pointer's
    opening words.
    """
    words = WORD.findall(sentence)
    if not words or len(words) > BACK_REFERENCE_MAX_WORDS:
        return False
    if not sentence.strip().lower().startswith(BACK_REFERENCE_CUES):
        return False
    if not headings:
        return False
    lowered = sentence.lower()
    # Word-bounded: a substring match let a short or common heading claim
    # the exemption from inside an unrelated longer word. #464 F6.
    return any(heading and re.search(rf"\b{re.escape(heading)}\b", lowered) for heading in headings)


def _collapse_prose_piece(text: str, headings: frozenset[str] | None) -> str:
    """One prose chunk (no embedded image line) with a duplicate back
    reference collapsed to its first occurrence.

    Compares every piece already kept, not only the immediately preceding
    one (#531): two repeats in the same paragraph can be split by an
    unrelated sentence in between, and the second pointer is still a
    duplicate of the first even though it is not adjacent to it.
    """
    pieces = SENTENCE_END.split(text)
    kept: list[str] = []
    for piece in pieces:
        if _is_back_reference(piece, headings) and any(
            piece.strip() == prior.strip() for prior in kept
        ):
            continue
        kept.append(piece)
    return text if len(kept) == len(pieces) else " ".join(kept)


def _map_prose_blocks(body: str, transform) -> str:
    """Apply `transform(text) -> text` to every prose block, a same-block
    `![figure]` line split onto its own segment first.

    Shared by `collapse_repeated_back_references` and
    `drop_dangling_figure_mentions` (#464 F2): whatever the transform does
    to a block's sentences, an image line with no blank line separating it
    from the prose above it must never be swept into that flow and lose
    its own line. A heading, a list, a table, a quote, a fence, and a
    `Figure N.` caption are passed through untouched, the same exemptions
    the sentence-scanning helpers grant elsewhere.
    """
    out_lines: list[str] = []
    block_lines: list[str] = []

    def flush() -> None:
        if not block_lines:
            return
        block = "\n".join(block_lines)
        stripped = block.strip()
        if (
            not stripped
            or stripped.startswith(("#", "!", "|", ">", "```", "-", "*"))
            or LIST_ITEM.match(stripped)
            or FIGURE_CAPTION.match(stripped)
        ):
            out_lines.append(block)
            return
        segments: list[str] = []
        prose_buf: list[str] = []
        for line in block_lines:
            if line.lstrip().startswith("!["):
                if prose_buf:
                    segments.append(transform("\n".join(prose_buf)))
                    prose_buf = []
                segments.append(line)
            else:
                prose_buf.append(line)
        if prose_buf:
            segments.append(transform("\n".join(prose_buf)))
        out_lines.append("\n".join(segments))

    for line in body.split("\n"):
        if line.strip() == "":
            flush()
            out_lines.append(line)
            block_lines = []
            continue
        block_lines.append(line)
    flush()
    return "\n".join(out_lines)


def collapse_repeated_back_references(body: str) -> str:
    """Two or more identical back references stacked in one paragraph
    collapse to one.

    The whole-paper pass can point more than one repeat in the same
    paragraph at the same source; each is edited on its own, so the
    result is the same short pointer sentence typed out once per repeat
    it cleared, instead of the single pointer a reader needs. Runs on the
    deterministic trim's own output and again on whatever a model-written
    pass returns, since a model can stack the same pointer on its own.
    #521.
    """
    headings = frozenset(top_level_sections(body))
    return _map_prose_blocks(body, lambda text: _collapse_prose_piece(text, headings))


def top_level_sections(body: str) -> dict[str, str]:
    """Each `##` heading's own text, running to the next `##`-or-higher
    heading. Unlike `section_bodies`, a `###` key-question sub-heading is
    left inside its parent's span, not split out as a second section.

    `caveat_once` needs this distinction and nothing else does: handed the
    general-purpose split, a sentence under a `###` sub-heading was counted
    once in its own entry and once more inside its `##` parent's span, which
    graded the sentence as repeating itself.
    """
    matches = [m for m in _headings(body) if len(m.group(1)) == 2]
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        out[match.group(2).strip().lower()] = body[match.end() : end]
    return out


def top_level_section_spans(body: str) -> dict[str, tuple[int, int]]:
    """Byte offsets for `top_level_sections`' own boundaries.

    A deterministic edit that must touch only the one section a repeat
    names, and never search the rest of the document, slices `body[start:
    end]`, edits that slice, and splices it back, instead of asking
    `str.replace` to find a short sentence that a different section might
    also happen to contain. #477.
    """
    matches = [m for m in _headings(body) if len(m.group(1)) == 2]
    out: dict[str, tuple[int, int]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        out[match.group(2).strip().lower()] = (match.end(), end)
    return out


def _section_sentences_with_lines(text: str) -> list[tuple[int, str]]:
    """(line, sentence) pairs inside one section's own text, the line counted
    from that section's own first line. Skips a heading, an image, a list, a
    table, a quote, a fence, and a `Figure N.` caption, the same exemptions
    `_prose_sentences` grants, because none of those is a sentence a writer
    composed. The caption exemption matters here specifically: two
    auto-described diagrams of the same paper share enough boilerplate
    wording ("A flowchart diagram of <topic>, showing ...") to read as a
    repeat of each other, which is not a finding restated, it is two
    figures about the same paper. #464.
    """
    out: list[tuple[int, str]] = []
    block_lines: list[str] = []
    block_start = 0

    def flush() -> None:
        if not block_lines:
            return
        block = "\n".join(block_lines).strip()
        if (
            block.startswith(("#", "!", "|", ">", "```", "-", "*"))
            or LIST_ITEM.match(block)
            or FIGURE_CAPTION.match(block)
        ):
            return
        for piece in SENTENCE_END.split(block):
            piece = piece.strip()
            if piece:
                out.append((block_start, piece))

    for index, line in enumerate(text.split("\n"), start=1):
        if line.strip() == "":
            flush()
            block_lines = []
            continue
        if not block_lines:
            block_start = index
        block_lines.append(line)
    flush()
    return out


def _word_shingles(sentence: str, n: int = 4) -> set[tuple[str, ...]]:
    """Word 4-grams, lowercased. A sentence shorter than `n` words still
    shingles as one tuple, so two short sentences can still match.
    """
    words = [w.lower() for w in WORD.findall(sentence)]
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _numeric_full_tokens(sentence: str) -> frozenset[str]:
    """Every number-and-unit pair stated in full, normalized so '2.4%' and
    '2.4 percent' compare equal.
    """
    return frozenset(
        re.sub(r"\s+", " ", match.group(0).lower()).replace("percent", "%")
        for match in NUMERIC_FULL.finditer(sentence)
    )


def repeat_shingles(sections: dict[str, str]) -> list[dict]:
    """A caveat sentence, or a numeric finding stated in full, that a later
    section restates. Glossary and References are exempt. The abstract may
    restate one body finding, so it is exempt on the abstract side; two body
    sections that both restate the same finding are still a repeat. #477.
    """
    headings = frozenset(sections)
    entries: list[dict] = []
    for name, text in sections.items():
        if name in CAVEAT_EXEMPT_SECTIONS:
            continue
        for line, sentence in _section_sentences_with_lines(text):
            if _is_back_reference(sentence, headings):
                continue
            entries.append(
                {
                    "section": name,
                    "line": line,
                    "sentence": sentence,
                    "shingles": _word_shingles(sentence),
                    "numbers": _numeric_full_tokens(sentence),
                }
            )
    results: list[dict] = []
    for index, entry in enumerate(entries):
        if entry["section"] == "abstract":
            continue
        matches = []
        for other in entries[index + 1 :]:
            if other["section"] == entry["section"] or other["section"] == "abstract":
                continue
            same_numbers = bool(entry["numbers"]) and entry["numbers"] == other["numbers"]
            if same_numbers or _jaccard(entry["shingles"], other["shingles"]) > 0.6:
                matches.append(
                    {"section": other["section"], "line": other["line"], "sentence": other["sentence"]}
                )
        if matches:
            results.append(
                {
                    "section": entry["section"],
                    "line": entry["line"],
                    "sentence": entry["sentence"],
                    "matches": matches,
                }
            )
    return results


def caveat_once_violations(body: str) -> list[str]:
    """Every repeat `repeat_shingles` names, as one detail string per repeat.

    Unconditional: a body with nothing to repeat passes by construction.
    """
    hits = []
    for item in repeat_shingles(top_level_sections(body)):
        where = [f"{item['section']}:{item['line']}"] + [
            f"{m['section']}:{m['line']}" for m in item["matches"]
        ]
        hits.append(f"{item['sentence'][:120]!r} in {', '.join(where)}")
    return hits


def missing_sections(body: str, headings: list[str]) -> list[str]:
    """Sections the plan named that are not in the paper.

    Matched on the heading text, because that is what the writer was told to
    emit and what a reader looks for in a table of contents.
    """
    present = {match.group(1).strip().lower() for match in HEADING.finditer(_mask_fences(body))}
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


FIGURE_CAPTION = re.compile(r"^Figure (\d+)\.[ \t]*(.*)$")
IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\([^)\s]+\)\s*$")
FIGURE_MENTION = re.compile(r"\bFigure\s+(\d+)\b")


def placed_figures(body: str) -> list[dict]:
    """Every numbered figure the assembled body carries: its number, its
    owning `##` section, and the caption text on its own `Figure N.` line.

    Reads the caption line `assemble` writes at placement, the single
    source of truth for `captioned`, `figure_referenced`, and the
    whole-paper pass's own figure list: whatever number is on the page is
    the number a mention has to name, nothing recomputed separately. #464.
    """
    spans = top_level_section_spans(body)
    out: list[dict] = []
    pos = 0
    for line in body.split("\n"):
        match = FIGURE_CAPTION.match(line.strip())
        if match:
            owner = next((name for name, (s, e) in spans.items() if s <= pos < e), "")
            out.append(
                {
                    "number": int(match.group(1)),
                    "section": owner,
                    "caption": match.group(2).strip(),
                }
            )
        pos += len(line) + 1
    return out


def captioned_violations(body: str) -> list[str]:
    """Every placed image is followed by a `Figure N.` caption line, and
    every caption on the page numbers a distinct figure, contiguous from
    one.

    Not a fake caption on an image that resolved to nothing: `images` and
    `unplaced_figures` already own whether the file exists. This row owns
    only whether a resolved image carries the caption a reader needs, and
    whether the numbers on the page still add up. #413, #464.
    """
    lines = body.split("\n")
    missing = []
    for idx, line in enumerate(lines):
        if not IMAGE_LINE.match(line.strip()):
            continue
        j = idx + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        nxt = lines[j].strip() if j < len(lines) else ""
        if not FIGURE_CAPTION.match(nxt):
            missing.append(line.strip()[:80])
    # #464 B2. A figure whose image line was already persisted from an
    # earlier pass, and one freshly placed this call, must still number
    # 1..N with no gap and no duplicate; a caption `assemble` forgot to
    # renumber is the same defect as one it forgot to write.
    numbers = [figure["number"] for figure in placed_figures(body)]
    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        missing.append(f"figure numbers are not contiguous from one: {numbers}")
    return missing


def mentions_figure(text: str, number: int) -> bool:
    """Whether `text` names `Figure {number}` as a whole number, not as a
    prefix of a longer one.

    A plain substring let "Figure 1" read as satisfied by a "Figure 12"
    mention. Shared by `figure_referenced_violations` and both trim
    implementations' own "already mentioned" check, so neither can decide
    a figure is referenced when the other would still flag it missing.
    #464 F1.
    """
    return re.search(rf"\bFigure {number}\b", text) is not None


def figure_referenced_violations(body: str) -> list[str]:
    """Every placed figure is named `Figure N` in its owning section's own
    prose, outside the caption line itself.

    Reads `placed_figures`, so a figure with no number at all -- skipped,
    dropped, or never rendered -- never reaches this row and never demands
    a mention. #464.
    """
    spans = top_level_section_spans(body)
    missing = []
    for figure in placed_figures(body):
        section = figure["section"]
        span = spans.get(section)
        scope = body[span[0] : span[1]] if span else body
        prose = re.sub(rf"^Figure {figure['number']}\..*$", "", scope, flags=re.M)
        if not mentions_figure(prose, figure["number"]):
            missing.append(f"Figure {figure['number']} never named in {section or 'its section'!r} prose")
    return missing


def skip_noted_violations(
    body: str, skipped: list[dict] | None, heading_by_id: dict[str, str] | None = None
) -> list[str]:
    """Every recorded skip is named, with its reason, under the section it
    names -- or somewhere on the page, for a skip with no section at all.

    Not a fake image, not a caption on an empty axis: a skip is a note, and
    a note with nothing to show for it is the defect #386 named. Grading
    only the name let a note that dropped its reason, or landed under the
    wrong section, still pass. #464, F3.

    A skip's own `section` field is a section id, `assemble`'s own
    `fallback_section` shape and every real caller's shape, never a heading
    string. `top_level_sections` keys by heading text. A PR #534 judge
    follow-up: no SDK id equals its own heading, so the lookup below widened
    to whole-body scope for every real skip until this map resolved the id
    through the outline the run already keeps, not by string-matching a
    heading. #478
    """
    sections = top_level_sections(body)
    heading_by_id = heading_by_id or {}
    missing = []
    for item in skipped or []:
        name = str((item or {}).get("name") or "").strip()
        if not name:
            continue
        reason = str((item or {}).get("reason") or "").strip()
        section_id = str((item or {}).get("section") or "").strip().lower()
        # A run with no id-to-heading map (a snippet test, or an outline this
        # call was never handed) falls back to treating the id as the
        # heading, which is exactly right when the two already agree.
        heading = heading_by_id.get(section_id, section_id).strip().lower()
        scope = sections.get(heading, body) if section_id else body
        if name not in scope or (reason and reason not in scope):
            missing.append(name)
    return missing


def drop_dangling_figure_mentions(body: str, valid_numbers) -> str:
    """A sentence naming a figure number that is no longer placed reads as
    a promise the page does not keep: a figure a later attempt dropped
    after an earlier pass already pointed a section at it, or one a live
    image backend failed to render (#514, #531). Strips the whole
    sentence, never only the number, so a reader is never left with a
    dangling "shows" pointed at nothing. #464.
    """
    valid = set(valid_numbers)

    def _drop(text: str) -> str:
        pieces = SENTENCE_END.split(text)
        kept = [
            piece
            for piece in pieces
            if not any(int(n) not in valid for n in FIGURE_MENTION.findall(piece))
        ]
        return text if len(kept) == len(pieces) else " ".join(kept)

    return _map_prose_blocks(body, _drop)


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


SKIP_NOTE = re.compile(r"^>.*was not shown:.*\.$", re.M)


def _strip_figure_notes(body: str) -> str:
    """Blank a `Figure N.` caption line and a skip-note blockquote line.

    Neither is prose a writer composed, and counting either toward
    `has_body` or `length` credits a section for system-generated text.
    `FIGURE_CAPTION` has no `re.M` flag (every other caller matches it
    against one already-split line), so this multiline body needs its own
    flag on the substitution. #464, F4.
    """
    body = re.sub(FIGURE_CAPTION.pattern, "", body, flags=re.M)
    return SKIP_NOTE.sub("", body)


def word_count(body: str) -> int:
    """The whole-paper word count `length` grades against `MIN_WORDS`.

    Blanks the same system-generated text `_strip_figure_notes` already
    excludes, and now also `PYTHON_WRITTEN_SECTIONS`: Methods and the study
    table are Python output, never a writer's prose, and crediting either
    toward the floor is the same overclaim `_strip_figure_notes` already
    names. PR #535 judge revision F5.
    """
    stripped = _mask_sections(_strip_figure_notes(body), PYTHON_WRITTEN_SECTIONS)
    return len(re.findall(r"\b[\w'-]+\b", FENCE.sub("", stripped)))


def sections_without_prose(body: str, min_words: int) -> list[str]:
    if min_words <= 0:
        return []
    thin = []
    for match in _headings(body):
        heading = match.group(2).strip()
        if heading.lower() in PROSE_EXEMPT:
            continue
        chunk = section_bodies(body).get(heading.lower(), "")
        chunk = IMAGE.sub("", FENCE.sub("", _strip_figure_notes(chunk)))
        words = re.findall(r"\b[\w'-]+\b", chunk)
        if len(words) < min_words:
            thin.append(f"{heading} ({len(words)} words)")
    return thin


# Headings a plan inserts as structure, never a body's own evidence section.
# PR #535 judge revision B1: the SDK's own outline never carries one of
# these today, which is why the position check below passed by accident;
# Deep Agents' plan always starts with "abstract", so "the first evidence
# section" has to skip every structural heading explicitly, not just take
# the first one `headings` names.
STRUCTURAL_HEADINGS = {"abstract", "introduction", "methods", "conclusion", "references"}

# A markdown table's own separator row: only `|`, `-`, `:`, and whitespace.
TABLE_SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|$")


def study_table_violations(body: str, human_studies: list[dict], headings: list[str]) -> list[str]:
    """The Evidence summary table exists, holds one row per human-study
    claim, and sits after Methods and before the first evidence section.
    #478. Called only when `human_studies` is non-empty; a paper with no
    human-study claim carries no table to grade.
    """
    sections = top_level_sections(body)
    order = list(sections)
    if "evidence summary" not in order:
        return ["no Evidence summary table for a ledger holding a human-study claim"]
    rows = [
        line.strip()
        for line in sections["evidence summary"].strip().splitlines()
        if line.strip().startswith("|")
    ]
    # PR #535 judge revision F8: a fixed `rows[2:]` miscounted a table that
    # lost its separator row, or that shares its section with an unrelated
    # pipe-prefixed line. The header is the first row; every other row is
    # data unless it is the separator itself.
    data_rows = [row for row in rows[1:] if not TABLE_SEPARATOR_ROW.match(row)]
    problems = []
    if len(data_rows) != len(human_studies):
        problems.append(f"{len(data_rows)} table rows for {len(human_studies)} human-study claims")
    methods_at = order.index("methods") if "methods" in order else -1
    table_at = order.index("evidence summary")
    first_section = next(
        (
            h.strip().lower()
            for h in headings
            if h.strip().lower() in order and h.strip().lower() not in STRUCTURAL_HEADINGS
        ),
        None,
    )
    first_at = order.index(first_section) if first_section else len(order)
    if not (methods_at != -1 and methods_at < table_at < first_at):
        problems.append("the table is not between Methods and the first evidence section")
    return problems


FRONT_MATTER_PROVENANCE = re.compile(
    r"Generated by an automated research loop\. "
    r"Sources: \d+ retrieved, \d+ cited\. "
    r"Verification: \d+ claims cross-checked\. See Methods\."
)


def _front_matter_zone(body: str) -> str:
    """Text between the title and the first `## ` heading, where the byline,
    date, provenance, and conflicts lines live. #479
    """
    zone: list[str] = []
    started = False
    for line in body.splitlines():
        if not started:
            if line.startswith("# "):
                started = True
            continue
        if line.startswith("## "):
            break
        zone.append(line)
    return "\n".join(zone)


def front_matter_violations(body: str) -> list[str]:
    """The byline, the date, the provenance line, and the conflicts line all
    sit above the Abstract. #479. The conflicts line's own text is whatever
    the `CONFLICTS` override was at assemble time, so this checks for a
    fourth paragraph, never for fixed words.
    """
    zone = _front_matter_zone(body)
    problems = []
    if "Prepared by:" not in zone:
        problems.append('no byline ("Prepared by:") above the Abstract')
    if not re.search(r"Date: \d{4}-\d{2}-\d{2}\.", zone):
        problems.append("no Date line above the Abstract")
    if not FRONT_MATTER_PROVENANCE.search(zone):
        problems.append("no provenance line with source and verification counts")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", zone) if p.strip()]
    if len(paragraphs) < 4:
        problems.append(f"only {len(paragraphs)} front-matter lines above the Abstract, need 4")
    return problems


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
    skipped_figures=None,
) -> Score:
    """Score a paper. No model call."""
    checks: list[Check] = []

    # The outline's own id-to-heading map. `skip_noted_violations` resolves a
    # skip's section id through it, never by treating the id as a heading
    # string. Empty when this call carries no outline, which every row below
    # that reads it already tolerates. #478
    heading_by_id = {
        str(section.get("id") or "").strip().lower(): str(section.get("heading") or "")
        for section in (outline or {}).get("sections") or []
        if section.get("id")
    }

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

    # Unconditional: a heading ending in "?" is checked with no outline at
    # all. A clean paper has no interrogative heading, so this never fires
    # on a snippet the outline was never handed. #385 #463.
    bad_headings = question_headings(body, outline)
    checks.append(
        Check(
            "question_heading",
            not bad_headings,
            "no heading is a pasted question"
            if not bad_headings
            else f"heading is a question: {bad_headings[0]!r}",
        )
    )

    # Unconditional, and inert with no `## Abstract` heading: a snippet
    # another row's test built has nothing to grade. #472.
    abstract_mismatches = abstract_matches_body(body, claims)
    checks.append(
        Check(
            "abstract_matches_body",
            not abstract_mismatches,
            "the abstract and introduction match the body they summarize"
            if not abstract_mismatches
            else f"mismatch: {abstract_mismatches[:3]}",
        )
    )

    # Unconditional, and inert with nothing to repeat: a snippet another
    # row's test built has no second section to compare against. #477.
    caveat_hits = caveat_once_violations(body)
    checks.append(
        Check(
            "caveat_once",
            not caveat_hits,
            "no caveat or numeric finding repeats across sections"
            if not caveat_hits
            else f"repeated: {caveat_hits[:2]}",
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

    # Unconditional, and inert with no image at all: a snippet another
    # row's test built has nothing to caption. #464.
    cap_missing = captioned_violations(body)
    checks.append(
        Check(
            "captioned",
            not cap_missing,
            "every image is followed by its Figure N. caption"
            if not cap_missing
            else f"no caption: {cap_missing[:3]}",
        )
    )

    # Unconditional, and inert with no numbered figure at all: `placed_figures`
    # reads only what `Figure N.` captions the body actually carries, so a
    # figure the diagrammer dropped or the chart stage skipped is never
    # placed and never demands a mention here. #464.
    ref_missing = figure_referenced_violations(body)
    checks.append(
        Check(
            "figure_referenced",
            not ref_missing,
            "every placed figure is named Figure N in its own section's prose"
            if not ref_missing
            else f"unreferenced: {ref_missing[:3]}",
        )
    )

    # Unconditional, and inert with nothing skipped: a snippet another
    # row's test built has no skip to note. #386, #464.
    skip_missing = skip_noted_violations(body, skipped_figures, heading_by_id)
    checks.append(
        Check(
            "skip_noted",
            not skip_missing,
            "every skipped figure is named with its reason"
            if not skip_missing
            else f"no note: {skip_missing[:3]}",
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

    leak_hits = policy_leak_violations(body, allowed_domains)
    checks.append(
        Check(
            "policy_leak",
            not leak_hits,
            "the body names no search host and narrates no retrieval boundary"
            if not leak_hits
            else f"search host or retrieval narration in: {leak_hits[0]!r}",
        )
    )

    if enforce_structure:
        # Every row below is opt-in behind this one keyword, the house pattern
        # `enforce_source_policy` and `enforce_loop_doctrine` already set. A
        # clean snippet with no glossary at all passes both rows by
        # construction: no captured term means nothing missing, and no
        # glossary entry means nothing unused.
        # A body with no top-level heading at all is not a paper, it is a
        # snippet another row's test built. Nothing to grade, so this passes
        # by construction, the same defence `glossary_complete` gives a body
        # with no captured term.
        last_heading = last_prose_heading(body)

        # #479. The frozen order's own first item: front matter, above the
        # Abstract. Guarded the same way as every row below: nothing to
        # grade in a heading-less snippet.
        front_matter_missing = last_heading is not None and front_matter_violations(body)
        checks.append(
            Check(
                "front_matter",
                not front_matter_missing,
                "byline, date, provenance, and conflicts sit above the Abstract"
                if not front_matter_missing
                else f"front matter: {front_matter_missing[0]}",
            )
        )
        if last_heading is None:
            next_step_ok, next_step_detail = True, "no prose section to grade"
        elif outlines.is_bare_conclusion(last_heading):
            next_step_ok, next_step_detail = False, f"last prose heading is a bare Conclusion: {last_heading!r}"
        elif not outlines.starts_with_next_step_verb(last_heading):
            next_step_ok, next_step_detail = (
                False,
                f"last prose heading has no next-step verb: {last_heading!r}",
            )
        else:
            next_step_ok, next_step_detail = True, f"last prose heading is a next step: {last_heading!r}"
        checks.append(Check("next_step", next_step_ok, next_step_detail))

        cta_text = section_bodies(body).get(last_heading.strip().lower(), "") if last_heading else ""
        cta_bad = cta_violations(cta_text)
        checks.append(
            Check(
                "cta_language",
                not cta_bad,
                "the next-step section sells nothing and every step is 20 words or fewer"
                if not cta_bad
                else f"cta language or a step over 20 words: {cta_bad[:3]}",
            )
        )

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

        # #478. A body with no top-level heading at all is not a paper, the
        # same defence `next_step` above already gives: nothing to grade,
        # so this passes by construction rather than failing every snippet
        # another row's test built.
        sections_present = top_level_sections(body)
        methods_missing = last_heading is not None and "methods" not in sections_present
        checks.append(
            Check(
                "methods_present",
                not methods_missing,
                "the Methods section is present" if not methods_missing else "no Methods section",
            )
        )

        conclusion_missing = last_heading is not None and "conclusion" not in sections_present
        checks.append(
            Check(
                "conclusion_present",
                not conclusion_missing,
                "the Conclusion section is present"
                if not conclusion_missing
                else "no Conclusion section",
            )
        )

        # Only when the ledger holds a human-study claim: a paper about a
        # topic with none must not be told to grow a table for it.
        human_studies = [c for c in (claims or []) if c.get("study") and c.get("number")]
        if human_studies:
            table_bad = study_table_violations(body, human_studies, headings or [])
            checks.append(
                Check(
                    "study_table",
                    not table_bad,
                    f"{len(human_studies)} human-study rows, correctly placed"
                    if not table_bad
                    else f"study table: {table_bad[0]}",
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


# #473. What names a section's own topic as safety, dosing, or protocol.
GUIDELINE_TOPIC_WORDS = ("safety", "dosing", "protocol")


def evidence_requirements_met(requirements: dict, findings: list[dict]) -> tuple[bool, str]:
    """Grade a question's bound evidence against its own `evidence_requirements`
    block. #475

    `findings` is a flat `{"tier", "year", "text", "url"}` shape both call
    sites build: the pre-write research path (`sections.py`, from a
    finding's nested `source`) and `section_check`'s post-write row (from
    the writer's bound claims, `source_url`). `study_types`/`min_count`:
    how many distinct URLs among the findings carry a tier in the required
    set -- two claims lifted from one reply cite one URL and must count as
    one source, not two. Judge revision on #520, blocking finding 3.

    `recency_years`, when given: a finding with a year counts only inside
    the window. A finding with no year does not satisfy a window: there is
    nothing here to confirm it is recent, so it is dropped from the count
    rather than assumed to qualify. Judge revision on #520, follow-up 2.

    `populations`: each named term must appear, word-bounded, in the
    pooled text of only the findings whose URL counted toward `min_count`
    -- a population named solely by a finding resting on the wrong tier,
    or outside the window, does not satisfy the requirement. Judge
    revision on #520, follow-up 4.

    Returns `(True, "")` when nothing is required, an absent or empty
    block: this is a grading function, not the hard requirement, which is
    `outline.validate`'s job.
    """
    requirements = requirements or {}
    study_types = [str(t) for t in (requirements.get("study_types") or [])]
    min_count = int(requirements.get("min_count") or 0)
    if not study_types or min_count < 1:
        return True, ""

    def _key(finding: dict) -> str:
        return str(finding.get("url") or finding.get("source_url") or id(finding))

    recency_years = requirements.get("recency_years")
    this_year = datetime.now(timezone.utc).year

    def counts(finding: dict) -> bool:
        if (finding.get("tier") or "") not in study_types:
            return False
        if not recency_years:
            return True
        year = str(finding.get("year") or "").strip()
        return year.isdigit() and int(year) >= this_year - int(recency_years)

    matching = [finding for finding in findings if counts(finding)]
    matched_keys = {_key(finding) for finding in matching}
    if len(matched_keys) < min_count:
        return False, f"needs {min_count} {'/'.join(sorted(set(study_types)))}, has {len(matched_keys)}"

    pooled = " ".join(str(f.get("text") or "") for f in findings if _key(f) in matched_keys)
    missing_populations = [
        population
        for population in (requirements.get("populations") or [])
        if not re.search(rf"\b{re.escape(str(population))}\b", pooled, re.I)
    ]
    if missing_populations:
        return False, f"no evidence found for population(s): {', '.join(missing_populations)}"
    return True, ""


def _is_guideline_topic(section: dict) -> bool:
    heading = str(section.get("heading") or "").lower()
    questions = " ".join(
        outlines.question_text(item) for item in section.get("key_questions") or []
    ).lower()
    return any(word in f"{heading} {questions}" for word in GUIDELINE_TOPIC_WORDS)


def guideline_ledger_matches(ledger_sources: list[dict], section: dict, topic: str = "") -> list[dict]:
    """The run's ledger-wide guideline sources this section must reckon with. #517

    `ledger_sources` is every `position_stand_or_guideline`-tier source the
    whole run has retrieved so far, from whichever section's research found
    it, not only this section's own `findings`. #473's own wiring graded a
    section against its own evidence alone, so a position stand retrieved
    for the introduction and never cited by the safety section it actually
    answers passed unnoticed.

    A source only counts here when the section itself is about safety,
    dosing, or protocol (`_is_guideline_topic`) and its title or abstract
    shares at least two content terms, `COVERAGE_STOP` applied the same way
    `_coverage_terms` already applies it, with the paper topic or this
    section's own key questions. One shared word is not on topic; a title
    guideline retrieved for an unrelated question must not be forced on a
    section that never asked about it.

    `source_policy.GUIDELINE_VOCABULARY` (position, stand, guideline,
    consensus, statement, practice, clinical) is dropped from both sides
    before the overlap is counted. #517 follow-up 1: without this, a key
    question that names the tier itself, "what does the position stand say
    about training load", shared "position" and "stand" with any title
    beginning "Position Stand on ...", pulling in a guideline from any
    unrelated field.

    Called from `section_check`'s `guideline_cited` and `grounded` rows,
    and from `sections.py`'s writer brief, so the row that requires a
    citation and the row that would otherwise call it dangling never
    disagree about which sources are in play.
    """
    if not ledger_sources or not _is_guideline_topic(section):
        return []

    def content_terms(text: str) -> set[str]:
        return _coverage_terms(text) - source_policy.GUIDELINE_VOCABULARY

    target_terms = content_terms(
        " ".join(
            [str(topic or "")]
            + [
                text
                for text in (question_text(item) for item in section.get("key_questions") or [])
                if text
            ]
        )
    )
    if not target_terms:
        return []
    matches = []
    for source in ledger_sources:
        if not isinstance(source, dict) or source.get("tier") != "position_stand_or_guideline":
            continue
        source_terms = content_terms(f"{source.get('title') or ''} {source.get('abstract') or ''}")
        if len(source_terms & target_terms) >= 2:
            matches.append(source)
    return matches


def section_check(
    body: str,
    *,
    section: dict | None = None,
    findings: list | None = None,
    evidence: str = "",
    word_target: int = 0,
    figures_given: list | None = None,
    evidence_requirements_unmet: dict[str, str] | None = None,
    ledger_sources: list[dict] | None = None,
    topic: str = "",
) -> Score:
    """Eleven deterministic rows on one section, before any judge."""
    section = section or {}
    findings = findings or []
    # #517. Computed once, reused by `grounded` (so a citation `guideline_cited`
    # demands below is never also read back as a dangling marker) and by
    # `guideline_cited` itself.
    ledger_guidelines = guideline_ledger_matches(ledger_sources or [], section, topic)
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
    # Token overlap, not the verbatim question. #385: requiring the exact
    # string left the writer no way to answer a question except by pasting
    # it, and a pasted question is a heading, not an answer. Deep Agents
    # `sections.py` `_terms`/`STOP` carries the same rule.
    body_terms = _coverage_terms(body)
    missing_q = []
    for question in questions:
        terms = _coverage_terms(question)
        if terms and len(terms & body_terms) < _coverage_needed(terms):
            missing_q.append(question)
    checks.append(
        Check(
            "coverage",
            not missing_q,
            "every key question is answered" if not missing_q else f"unanswered: {missing_q[:2]}",
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
    # #517. A ledger guideline `guideline_cited` requires below is a real,
    # run-wide reference number even when it never reached this section's
    # own findings. Without this, citing it here read as dangling.
    numbers |= {str(source.get("number")) for source in ledger_guidelines if source.get("number")}
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
        if f.get("tier") != "position_stand_or_guideline" or not f.get("number"):
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
            # Not yet in the run's citation registry. The writer brief
            # (`sections.py`) still lists it with the citation form the
            # port uses; nothing here can fail a section on a number that
            # does not exist yet. #517
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

    # #474. `sections.generalizing_claims` tags a finding `generalizing` when
    # it is selected for the counter-evidence pass. `counter` ("hit", "miss",
    # or "capped") is this row's only way to tell "the pass looked" from
    # "nothing ever looked at this claim": a `capped` claim was selected but
    # priced out by the run cap, and it passes, because the writer's brief
    # already tells it to hedge that claim like a single source. A
    # counter-finding itself carries `counterargument_to`, not
    # `generalizing`, so it never needs a counter-search of its own.
    uncountered = [
        f.get("text") or f.get("id") or ""
        for f in findings
        if f.get("generalizing") and not f.get("counterargument_to") and not f.get("counter")
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

    # #475. Each key question's own `evidence_requirements` block, graded
    # against the findings this call was handed that answer it -- the
    # writer's bound claims, not a whole-run source ledger this function has
    # no access to. A question with no block (an older outline, or a section
    # a test built directly) passes trivially: `outline.validate` is where a
    # missing block is a hard failure, not here. `question_id` on a bound
    # finding is the question's own text (`sections._finding_from_claim`'s
    # `answers_question`), never a synthesized id, so this matches on text.
    #
    # Judge revision on #520, blocking finding 1: a question already
    # graded once, whose one shortfall turn is spent and the block is
    # still short (`evidence_requirements_unmet`), passes here. Only a
    # question never graded at all still fails the row; the measured
    # shortfall already travels as a named coverage gap, not a second
    # section failure on top of it.
    unmet = evidence_requirements_unmet or {}
    shortfalls = []
    for question in section.get("key_questions") or []:
        requirements = outlines.question_evidence_requirements(question)
        if not requirements:
            continue
        text = outlines.question_text(question)
        if text in unmet:
            continue
        bound = [f for f in findings if (f.get("question_id") or "") == text]
        met, reason = evidence_requirements_met(requirements, bound)
        if not met:
            shortfalls.append(f"{text!r}: {reason}")
    checks.append(
        Check(
            "evidence_requirements_met",
            not shortfalls,
            "every question's evidence_requirements is met"
            if not shortfalls
            else "; ".join(shortfalls[:2]),
        )
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

    score = check(
        "The system is fast [1]. Figure 1 shows the same idea.\n\n![f](x.png)\n\nFigure 1. f",
        ["u1"],
        base_dir="/nonexistent",
    )
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

    # P4, the next-step section.
    assert last_prose_heading("## Introduction\n\ntext\n\n## Next step\n\ntext\n\n## Glossary\n\nt\n") == "Next step"
    assert last_prose_heading("## Introduction\n\ntext\n\n## References\n\n1. u\n") == "Introduction"
    assert last_prose_heading("no heading here") is None
    assert outlines.is_bare_conclusion("Conclusion") and not outlines.is_bare_conclusion("Next step")
    assert outlines.starts_with_next_step_verb("Next step") and outlines.starts_with_next_step_verb("Evaluate X")
    assert not outlines.starts_with_next_step_verb("Limitations")
    assert cta_violations("- Evaluate X on a live ticket.\n- Run the fixture with --doer none.\n") == []
    assert cta_violations("- Unlock the platform for every team.\n")
    assert cta_violations("- Buy the enterprise plan today and contact us for a demo.\n")
    long_step = "- " + " ".join(["word"] * 21) + "."
    assert cta_violations(long_step)

    print("checks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
