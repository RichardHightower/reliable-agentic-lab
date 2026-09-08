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

Rows `check()` appends, past the three it reuses from `brief`:

    sections       every required heading is present
    limitations    the paper states its limitations (soft)
    figure_alt     every figure carries real alt text
    figure_assets  every diagram is a judged publication asset, not a sketch
    captioned      every image is followed by a Figure N. caption
    figure_referenced every placed figure is named Figure N in its own section's prose
    skip_noted     every skipped figure is named, with its reason, on the page
    no_diagram_source diagram source text never leaked into the body
    ste_language   no contraction, no e.g./i.e./etc. in body prose
    noun_stack     no noun cluster longer than three (soft)
    person         no second person, no first-person tour
    marketing      no banned marketing verb in body prose
    policy_leak    the body names no search host and narrates no retrieval boundary
    caveat_once    a caveat sentence or a numeric finding repeats across sections
    question_heading a heading pastes a question instead of answering it
    abstract_matches_body the abstract and introduction match the body they summarize
    next_step      the last prose heading is a next-step section, not a bare Conclusion
    cta_language   the next-step section sells nothing and every step stays short
    glossary_complete every first-use term reached the glossary
    glossary_exact every glossary entry is a term the body actually uses
    references     the reference list has a row for every source
    reference_hosts every reference host is on the approved allowlist
    exit_doctrine  the body names done, then cost, then max turns, in order
    langgraph_limitations limitations do not contradict an official LangGraph page
    single_source_caveat every single-source claim admits it
    no_contradicted no contradicted claim reached the paper
    has_body       every section carries real prose, not a heading
    length         the paper clears the word floor
    charted        every plotted value is in the corpus and the caption cites

Belt versus judge, matching the house style page's ownership table
(https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style).
Python grades every row above. `skills/reviewer/SKILL.md` grades what Python
cannot: defines_terms, states_mechanism, names_tradeoff, evidence_matches,
scope_honest, no_filler, depth, voice, figure_earns_place, and
abstract_matches_body, where Python catches only the fixed overclaim list and
the reviewer catches the rest.

    python3 paper_check.py --demo
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import brief
import evidence
import outline as outlines
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
# place. Copied from the SDK port, not imported.
FENCE = re.compile(r"^[ \t]*([`~]{3,})([^\n]*)\n(.*?)(?:\n[ \t]*\1[ \t]*(?=\n|\Z)|\Z)", re.M | re.S)
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

# Copied from `sections.py`, where it already grades one section. No second
# person anywhere in the paper, not just the section body.
SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.I)

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
LIST_ITEM = re.compile(r"^\d+[.)]\s")

# P3, first-use glossary terms. The writer marks a term in the section that
# first uses it, `<!-- TERM: orchestrator: the process that sequences roles -->`,
# and assembly harvests and strips the mark. Copied from the SDK port's
# `NEEDS_SOURCE` and `take_flags` mechanism at `checks.py`, not imported.
TERM_MARKER = re.compile(r"<!--\s*TERM:\s*(.*?)\s*-->", re.S)
# The glossary entry assembly writes for each captured term: `**term.** text`.
GLOSSARY_ENTRY = re.compile(r"^\*\*(.+?)\.\*\*\s*(.+)$", re.M)

# STE-S5, no noun stack longer than three. There is no part-of-speech tagger
# in this codebase and this unit may not add one, so a token counts as a noun
# candidate only when it is not one of these function words and does not carry
# a verb or adverb ending. The list is short on purpose: articles,
# prepositions, conjunctions, pronouns/determiners, auxiliaries, and the
# common verbs and adverbs a briefing actually uses. Copied from the SDK port,
# not imported.
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
# the ending is cheaper than tagging the word. A trailing double `s`,
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
# The SDK's inline-and-fenced code mask, copied so a contraction inside
# single backticks is not scored as prose in this port either. `FENCE`
# elsewhere in this file grades only a full fenced block; this one is scoped
# to the STE belt.
CODE_SPAN = re.compile(r"`[^`]*`|```.*?```", re.S)

# Identifiers a later edit must not invent, copied from the SDK's `checks.py`,
# not imported. A bare URL is deliberately excluded: too common in retrieved
# text to be signal, and a dead link is a different problem.
ARXIV = re.compile(r"\barXiv[:\s]*(\d{4}\.\d{4,5})", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
AUTHOR_YEAR = re.compile(r"\[([A-Z][^\[\]\n]{2,60}?,\s*(?:19|20)\d{2})\]")
PERCENT = re.compile(r"\b\d+(?:\.\d+)?%")
VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
BIG_INT = re.compile(r"\b([1-9]\d{2,})\b")
QUOTED = re.compile(r'"([^"]{3,})"')

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
CAVEAT_EXEMPT_SECTIONS = {"glossary", "references"}
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
    opening words. Copied from the SDK's `checks.py`, not imported.
    """
    words = WORD.findall(sentence)
    if not words or len(words) > BACK_REFERENCE_MAX_WORDS:
        return False
    if not sentence.strip().lower().startswith(BACK_REFERENCE_CUES):
        return False
    if not headings:
        return False
    lowered = sentence.lower()
    return any(heading and heading in lowered for heading in headings)


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


def collapse_repeated_back_references(body: str, headings: frozenset[str] | None = None) -> str:
    """Two or more identical back references stacked in one paragraph
    collapse to one.

    The whole-paper pass can point more than one repeat in the same
    paragraph at the same source; each is edited on its own, so the
    result is the same short pointer sentence typed out once per repeat
    it cleared, instead of the single pointer a reader needs. Runs on the
    deterministic trim's own output and again on whatever a model-written
    pass returns, since a model can stack the same pointer on its own.
    #521. Copied from the SDK's `checks.py`, not imported.

    A line that is itself an image never joins the sentence join below
    (#531): the join reduces a prose block to one flowed line, and a same-
    block `![figure]` line with no blank line separating it from the
    prose above it would otherwise be swept into that flow and lose its
    own line.

    `headings` defaults to `top_level_sections(body)`'s own `##` scan,
    right for the SDK's call on a whole assembled body. `stage_trim` calls
    this once per section on `self.written[heading]` alone, which carries
    no `##` line of its own to scan, so it passes the paper's real heading
    set in instead.
    """
    if headings is None:
        headings = frozenset(top_level_sections(body))
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
        ):
            out_lines.append(block)
            return
        segments: list[str] = []
        prose_buf: list[str] = []
        for line in block_lines:
            if line.lstrip().startswith("!["):
                if prose_buf:
                    segments.append(_collapse_prose_piece("\n".join(prose_buf), headings))
                    prose_buf = []
                segments.append(line)
            else:
                prose_buf.append(line)
        if prose_buf:
            segments.append(_collapse_prose_piece("\n".join(prose_buf), headings))
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


def _mask_references(text: str) -> str:
    """Blank the references section. A host name in a URL is not body prose."""
    match = REFERENCES_HEADING.search(text)
    if not match:
        return text
    return text[: match.start()] + " " * (len(text) - match.start())


def _mask_code(text: str) -> str:
    """Blank inline and fenced code so a code sample is not scanned for STE
    violations. Offsets are kept.
    """
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), text)


INLINE_URL = re.compile(r"https?://\S+")


def _mask_urls(text: str) -> str:
    """Blank an inline URL, through the next whitespace.

    A citation URL outside the reference list is not body prose either. A
    `your-account` path segment fabricated a `person` hit, and `unlock-guide`
    fabricated a `marketing` hit, both from a link a reader never reads as
    English. Copied from the SDK port, not imported.
    """
    return INLINE_URL.sub(lambda m: " " * len(m.group(0)), text)


def _mask_fences(text: str) -> str:
    """Blank a fenced code block, keeping every character offset.

    A judge on PR #508 found a `##` line inside a quoted markdown snippet
    counted as a heading in `question_headings`, and every sibling row that
    scans headings has the same exposure: `next_step` (`last_prose_heading`),
    the `sections` row, and the section-boundary helpers they all share.
    Narrower than `_mask_code` on purpose: an inline single-backtick span
    never spans a line, so it cannot fake a heading, and blanking it here
    would also blank a heading's own inline code. Copied from the SDK port,
    not imported. #509
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
    tables, quotes, fences, and a `Figure N.` caption, none of which are a
    sentence a writer composed. A caption is system-generated from a
    diagram's own node labels, not prose a writer is held to the STE belt
    for. #464.
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
# section at `sections.section_check`; these rows raise the same regex, plus
# the two first-person phrases, to the whole paper. Copied from the SDK port,
# not imported.
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
# stay banned outright. Copied from the SDK port, not imported.
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
# index a search was scoped to. Copied from the SDK port, not imported.
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
# own. Copied from the SDK port, not imported.
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


def take_terms(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Pull every TERM marker out of the text, and return both.

    The marker names a term and its first-use definition, separated by the
    first colon. A marker with no definition half is dropped rather than
    guessed at.
    """
    terms: list[tuple[str, str]] = []
    for payload in TERM_MARKER.findall(body):
        term, _, definition = payload.partition(":")
        term = term.strip()
        definition = definition.strip()
        if term and definition:
            terms.append((term, definition))
    return TERM_MARKER.sub("", body), terms


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


def glossary_terms(body: str) -> dict[str, str]:
    """The term-to-definition map assembly wrote into `## Glossary`.

    Empty when the paper carries no Glossary heading: no captured term means
    no section, not a missing one.
    """
    matches = _headings(body)
    for index, match in enumerate(matches):
        if match.group(2).strip().lower() != "glossary":
            continue
        level = len(match.group(1))
        end = len(body)
        for later in matches[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        section = body[match.end() : end]
        return {m.group(1).strip(): m.group(2).strip() for m in GLOSSARY_ENTRY.finditer(section)}
    return {}


def glossary_incomplete(body: str) -> list[str]:
    """A term marked for capture that never reached the glossary.

    Assembly strips every `TERM` marker before it writes the paper, so a
    marker surviving into the body handed to this row is itself the defect. A
    body with no marker at all has nothing captured and passes by
    construction.
    """
    _, captured = take_terms(body)
    glossary = {term.lower() for term in glossary_terms(body)}
    return [term for term, _ in captured if term.lower() not in glossary]


def glossary_host_terms(terms, allowed_domains=None) -> list[str]:
    """Glossary entries that are a search host, not a term.

    The reference list may name `docs.langchain.com`. The glossary may not: it
    is prose about the subject, not a map of where the run went looking.
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
# folds to the singular. Copied from the SDK port, not imported.
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
    used plural, or the reverse, is not graded as two words. Copied from
    the SDK port, not imported.
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
    prose = CODE_SPAN.sub(lambda m: " " * len(m.group(0)), _mask_section(body, "glossary"))
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


def _section_text(body: str, name: str) -> str:
    """One named heading's own body, the same boundary rule `glossary_terms` uses."""
    matches = _headings(body)
    for index, match in enumerate(matches):
        if match.group(2).strip().lower() != name:
            continue
        level = len(match.group(1))
        end = len(body)
        for later in matches[index + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        return body[match.end() : end]
    return ""


def question_headings(body: str, outline: dict | None = None) -> list[str]:
    """H2/H3 headings that are pasted questions, not the answers to them.

    A heading that ends in a question mark reads as a slide prompt, not a
    finding. A heading that repeats an outline key question verbatim is the
    same defect with the closing punctuation changed. Copied from the SDK
    `checks.py` row of the same name, never imported. #385.

    The question and the heading both drop trailing `?.:;!` before the
    comparison. A judge on PR #508 found the P5 version stripped only a
    trailing `?`, so a key question the writer re-punctuated with a period
    or a colon as a heading still matched the wanted set and slipped past.
    """
    wanted = set()
    for section in (outline or {}).get("sections") or []:
        for item in section.get("key_questions") or []:
            text = outlines.question_text(item).strip().lower().rstrip("?.:;!").strip()
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
    return [heading.strip().lower() for heading in HEADING.findall(_mask_fences(body))]


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


FIGURE_CAPTION = re.compile(r"^Figure (\d+)\.[ \t]*(.*)$")
IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*$")
FIGURE_MENTION = re.compile(r"\bFigure\s+(\d+)\b")


def placed_figures(body: str) -> list[dict]:
    """Every numbered figure the assembled body carries: its number, its
    owning `##` section, and the caption text on its own `Figure N.` line.

    Reads the caption line `assemble` writes at placement, the single
    source of truth for `captioned`, `figure_referenced`, and the
    whole-paper pass's own figure list: whatever number is on the page is
    the number a mention has to name, nothing recomputed separately.
    Copied from the SDK port's `checks.py`, not imported. #413, #464.
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
    """Every placed image is followed by a `Figure N.` caption line.

    Not a fake caption on an image that resolved to nothing: `figure_alt`
    and `figure_assets` already own the file itself. This row owns only
    whether a resolved image carries the caption a reader needs. #413,
    #464.
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
    return missing


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
        mention = f"Figure {figure['number']}"
        span = spans.get(section)
        scope = body[span[0] : span[1]] if span else body
        prose = re.sub(rf"^Figure {figure['number']}\..*$", "", scope, flags=re.M)
        if mention not in prose:
            missing.append(f"{mention} never named in {section or 'its section'!r} prose")
    return missing


def skip_noted_violations(body: str, skipped: list[dict] | None) -> list[str]:
    """Every recorded skip is named, with its reason, somewhere on the page.

    Not a fake image, not a caption on an empty axis: a skip is a note,
    and a note with nothing to show for it is the defect #386 named. #464.
    """
    missing = []
    for item in skipped or []:
        name = str((item or {}).get("name") or "").strip()
        if name and name not in body:
            missing.append(name)
    return missing


def drop_dangling_figure_mentions(body: str, valid_numbers) -> str:
    """A sentence naming a figure number that is no longer placed reads as
    a promise the page does not keep: a figure a later attempt dropped
    after an earlier pass already pointed a section at it, or one a live
    image backend failed to render (#514, #531). Strips the whole
    sentence, never only the number, so a reader is never left with a
    dangling "shows" pointed at nothing. Copied from the SDK port's
    `checks.py`, not imported. #464.
    """
    valid = set(valid_numbers)
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
        pieces = SENTENCE_END.split(block)
        kept = [
            piece
            for piece in pieces
            if not any(int(n) not in valid for n in FIGURE_MENTION.findall(piece))
        ]
        out_lines.append(block if len(kept) == len(pieces) else " ".join(kept))

    for line in body.split("\n"):
        if line.strip() == "":
            flush()
            out_lines.append(line)
            block_lines = []
            continue
        block_lines.append(line)
    flush()
    return "\n".join(out_lines)


def visible_source_syntax(body: str) -> list[str]:
    """Diagram source left in the paper. The figure is the artifact, not the code."""
    found = []
    for _delimiter, language, block in FENCE.findall(body):
        language = language.strip()
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
    matches = _headings(body)
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


# P7, #472. The abstract restates the body and may not say more than the body
# says. `single_source_caveat` above grades any section a single-source claim's
# own vocabulary matches; this row grades the abstract and the introduction's
# first paragraph by citation number instead, because that is where a reader
# meets the paper's claim before meeting its evidence.
ABSTRACT_HEDGE = re.compile(r"single|one study|one trial|preliminary", re.I)
ABSTRACT_OVERCLAIM = re.compile(r"\b(?:proves|definitively|conclusively|establishes that)\b", re.I)
ABSTRACT_MARKER = re.compile(r"\[(\d+)\]")


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block and not block.startswith(("#", "!", "|", ">", "```", "-", "*")):
            return block
    return ""


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


def _single_source_numbers(body: str, ledger: evidence.Ledger | None) -> set[int]:
    """Reference numbers backed by exactly one source, decided per claim.

    `stages.numbering` already maps url to number from the ledger, but
    `stages.py` imports this module, so calling back would be a cycle. The
    rendered reference list already carries the same mapping, so this reads
    it from `body` instead.

    A url can back more than one claim: one single-source, one corroborated
    by a second url. Flagging the number whenever any claim on that url is
    single-source forced a hedge onto a sentence citing the corroborated
    claim too. A number counts as single-source only when every claim
    citing its url is.
    """
    if ledger is None:
        return set()
    claims_by_url: dict[str, list[evidence.Claim]] = {}
    for claim in ledger.claims.values():
        for source_id in claim.source_ids:
            source = ledger.sources.get(source_id)
            if source is not None:
                claims_by_url.setdefault(source.url, []).append(claim)
    numbers = set()
    for row in reference_rows(body):
        match = re.match(r"\[(\d+)\]\s*(.*)", row)
        if not match:
            continue
        urls = URL.findall(match.group(2))
        url = urls[0].rstrip(".,;") if urls else ""
        claims = claims_by_url.get(url)
        if claims and all(c.truth_state == evidence.SINGLE_SOURCE for c in claims):
            numbers.add(int(match.group(1)))
    return numbers


def abstract_matches_body(body: str, ledger: evidence.Ledger | None = None) -> list[str]:
    """The abstract, and the introduction's first paragraph, state only what
    the body states.

    Inert with no `## Abstract` heading: nothing to grade. Otherwise
    unconditional, because a clean excerpt passes every rule by construction.
    Every graded sentence citing a single-source claim carries a hedge word,
    and a fixed overclaim phrase never appears. The abstract carries one more
    rule the introduction does not: it restates the body, so a number it
    cites must appear in the body too. The introduction is the body; a number
    appearing there for the first time is not a defect.
    """
    abstract = _section_text(body, "abstract")
    if not abstract.strip():
        return []
    single_source = _single_source_numbers(body, ledger)
    rest_of_body = body.replace(abstract, "", 1)
    excerpts = [("abstract", abstract, True)]
    intro_first = _first_paragraph(_section_text(body, "introduction"))
    if intro_first:
        excerpts.append(("introduction", intro_first, False))
    issues: list[str] = []
    for label, excerpt, check_numbers in excerpts:
        for sentence in _cited_sentences(excerpt):
            cited = {int(n) for n in ABSTRACT_MARKER.findall(sentence)}
            if cited & single_source and not ABSTRACT_HEDGE.search(sentence):
                issues.append(f"{label}: unhedged single-source claim: {sentence[:70]!r}")
            if ABSTRACT_OVERCLAIM.search(sentence):
                issues.append(f"{label}: overclaim in: {sentence[:70]!r}")
        if check_numbers:
            for number in {int(n) for n in ABSTRACT_MARKER.findall(excerpt)}:
                if f"[{number}]" not in rest_of_body:
                    issues.append(f"{label}: [{number}] does not appear in the body")
    return issues


def top_level_sections(body: str) -> dict[str, str]:
    """Each `##` heading's own text, running to the next `##`-or-higher
    heading. Keyed by the heading, lowercased. A `###` key-question
    sub-heading is left inside its parent's span, not split out as a second
    section: `caveat_once` needs that distinction, or a sentence under a
    sub-heading is graded as repeating itself, once in its own entry and
    once more inside its `##` parent's span. Copied from the SDK port's
    `checks.py`, not imported.
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
    also happen to contain. Copied from the SDK port, not imported. #477.
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
    composed. Copied from the SDK port, not imported. The caption exemption
    matters here specifically: two auto-described diagrams of the same
    paper share enough boilerplate wording ("A flowchart diagram of
    <topic>, showing ...") to read as a repeat of each other, which is not
    a finding restated, it is two figures about the same paper. #464.
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
    sections that both restate the same finding are still a repeat. Copied
    from the SDK port, not imported. #477.
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
    located: list[str] | None = None,
    loop_doctrine: bool = True,
    enforce_structure: bool = False,
    outline: dict | None = None,
    skipped_figures=None,
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

    # Unconditional, and inert with no image at all: a snippet another
    # row's test built has nothing to caption. #413, #464.
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
    skip_missing = skip_noted_violations(body, skipped_figures)
    checks.append(
        Check(
            "skip_noted",
            not skip_missing,
            "every skipped figure is named with its reason"
            if not skip_missing
            else f"no note: {skip_missing[:3]}",
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
            hard=False,
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
    abstract_mismatches = abstract_matches_body(body, ledger)
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

    if enforce_structure:
        # Every row below is opt-in behind this one keyword, the house pattern
        # `loop_doctrine` already sets. A clean snippet with no glossary at
        # all passes both rows by construction: no captured term means
        # nothing missing, and no glossary entry means nothing unused.
        # A body with no top-level heading at all is not a paper, it is a
        # snippet another row's test built. Nothing to grade, so this passes
        # by construction, the same defence `glossary_complete` gives a body
        # with no captured term.
        last_heading = last_prose_heading(body)
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

        cta_text = _section_text(body, last_heading.strip().lower()) if last_heading else ""
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
    # A located reference is a cabinet source the locator found the public page
    # for. The librarian never admitted a domain for it, because nobody asked
    # the web for it, so grading it against this run's allowlist would reject a
    # paper for citing the very document its second brain was built from.
    exempt = {str(url) for url in (located or [])}
    blocked = [url for url in source_policy.unallowed_urls(urls, allowlist) if url not in exempt]
    checks.append(
        Check(
            "reference_hosts",
            not blocked,
            "every reference host is on the approved allowlist"
            if not blocked
            else f"unapproved: {blocked}",
        )
    )

    # The seminar's own topic, not a property every paper has. Off, no paper
    # is held to a doctrine that has nothing to do with its subject.
    if loop_doctrine:
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


def _specifics(text: str) -> set[str]:
    """Identifiers a later edit must not invent. Copied from the SDK port's
    `checks.py`, not imported, because Deep Agents had no whole-paper edit
    pass before P9.
    """
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


def demo() -> None:
    good = (
        "# Exit conditions in agent loops\n\n"
        "## Abstract\n\n"
        "A loop without an exit spends until someone notices. [1]\n\n"
        "## Introduction\n\n"
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
        "![A flowchart of the three exits](figures/exits_imagen.png)\n\n"
        "Figure 1. A flowchart of the three exits.\n\n"
        "Figure 1 shows the order. [1]\n\n"
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
    # P7, #472: the abstract's citation now needs a matching mention outside
    # the abstract, or the new `abstract_matches_body` row calls it orphaned,
    # which is not what this fixture measures. The introduction restates the
    # same sentence rather than adding new content that would satisfy the
    # gate on its own; `has_body` still fires, on the still-empty Limitations.
    hollow = (
        "# Exit conditions\n\n## Abstract\n\ndone, then cost, then max turns. [1]\n\n"
        "## Introduction\n\ndone, then cost, then max turns. [1]\n\n"
        "## Limitations\n\n## References\n\n"
        "1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
    )
    score = gate(hollow, urls)
    assert not score.passed, score.report()
    assert score.signature() == ("has_body",), score.signature()

    # One sentence under a heading is not a section either.
    thin = good.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
        "![A flowchart of the three exits](figures/exits_imagen.png)\n\n"
        "Figure 1. A flowchart of the three exits.\n\n"
        "Figure 1 shows the order. [1]",
        "Yes. [1]",
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

    # P7, #472. `good`'s abstract and its introduction both cite `[1]`, the
    # same single-source claim, and neither sentence hedges it.
    assert "abstract_matches_body" in gate(good, urls, ledger=ledger).signature()
    hedged_everywhere = good.replace(
        "A loop without an exit spends until someone notices. [1]",
        "A loop without an exit spends until someone notices, on a single source. [1]",
    ).replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]",
        "Three exits cover the observed cases: done, then cost, then max turns, on a single source. [1][2]",
    )
    score = gate(hedged_everywhere, urls, ledger=ledger)
    assert "abstract_matches_body" not in score.signature(), score.report()

    # A number the abstract cites but the body never states.
    orphaned = good.replace(
        "A loop without an exit spends until someone notices. [1]",
        "A loop without an exit spends until someone notices. [1][9]",
    )
    assert "abstract_matches_body" in gate(orphaned, urls).signature()

    # A fixed overclaim phrase, whatever the ledger says.
    overclaimed = good.replace(
        "A loop without an exit spends until someone notices. [1]",
        "This paper proves a loop without an exit spends until someone notices. [1]",
    )
    assert "abstract_matches_body" in gate(overclaimed, urls).signature()

    # No `## Abstract` heading: nothing to grade, so the row passes.
    assert "abstract_matches_body" not in gate(
        good.replace("## Abstract", "## Overview"), urls
    ).signature()

    # A contradicted claim never reaches the paper.
    evidence.corroborate(claim, contradicted=True)
    score = gate(caveated, urls, ledger=ledger)
    assert not score.passed
    assert "no_contradicted" in score.signature()

    assert ste_language_violations("The writer does not skip a step.") == []
    hit = ste_language_violations("The writer doesn't skip a step.")
    assert hit and "doesn't" in hit[0]
    assert ste_language_violations("For example, the writer names the actor.") == []
    assert ste_language_violations("The writer names the actor, e.g. the host.")
    assert ste_language_violations("```\nThe writer doesn't skip a step.\n```") == [], (
        "a fenced code block is masked"
    )
    assert ste_language_violations("`The writer doesn't skip a step.`") == [], (
        "an inline code span is masked too, copied from the SDK's mask"
    )
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
    assert person_violations("```\nYou should not skip a step.\n```") == [], "a fenced code block is masked"
    assert person_violations("## References\n\nSee you at example.com.") == [], (
        "the references section is masked"
    )

    assert marketing_violations("The orchestrator sequences roles in a fixed order.") == []
    assert marketing_violations("The design will leverage existing infrastructure.")
    assert marketing_violations("The mechanism unlocks new throughput for the pipeline.")
    assert marketing_violations("```\na seamless robust retry loop\n```") == [], (
        "a fenced code block is masked"
    )
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
