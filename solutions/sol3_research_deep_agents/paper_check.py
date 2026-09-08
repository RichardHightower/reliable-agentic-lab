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


def _mask_for_ste(text: str) -> str:
    """Code, an inline URL, and references, gone. Everything else is body prose."""
    return _mask_urls(_mask_references(_mask_code(text)))


def _prose_sentences(text: str) -> list[str]:
    """Sentence-shaped chunks of body prose. Skips headings, images, lists,
    tables, quotes, and fences, none of which are a sentence a writer composed.
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

    Empty when the paper carries no Glossary heading: no captured term means
    no section, not a missing one.
    """
    matches = list(SECTION_HEADING.finditer(body))
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


def glossary_unused(body: str) -> list[str]:
    """Glossary entries for a term the body never uses outside the glossary."""
    terms = glossary_terms(body)
    if not terms:
        return []
    prose = FENCE.sub(lambda m: " " * len(m.group(0)), _mask_section(body, "glossary"))
    return [term for term in terms if not re.search(r"\b" + re.escape(term) + r"\b", prose, re.I)]


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
    located: list[str] | None = None,
    loop_doctrine: bool = True,
    enforce_structure: bool = False,
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

    if enforce_structure:
        # Every row below is opt-in behind this one keyword, the house pattern
        # `loop_doctrine` already sets. A clean snippet with no glossary at
        # all passes both rows by construction: no captured term means
        # nothing missing, and no glossary entry means nothing unused.
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
