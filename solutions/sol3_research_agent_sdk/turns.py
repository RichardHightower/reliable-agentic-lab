"""The model turns, and an offline twin of every one of them.

Two implementations of one interface.

    SdkTurns       spawns a named subagent through the Agent SDK
    OfflineTurns   deterministic templates over a recorded fixture

The offline twin is not a mock for the tests. It is how this folder runs in a
room with no network and no key, and it is what `task run --backend fixture`
uses. Every phase in `phases.py` is written against the interface, so the
pipeline it exercises offline is the same pipeline, not a shortened one.

The seam matters for a second reason. Every model call in this port is one
method here. When you want to know what this system asks a model to do, this is
the whole list, and it is short.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import research
import source_policy
from load_agents import (
    CHART_SCHEMA,
    DIAGRAM_SCHEMA,
    FINDINGS_SCHEMA,
    GROUNDING,
    LEDGER_SCHEMA,
    OUTLINE_SCHEMA,
    OUTLINE_VERDICT_SCHEMA,
    RESEARCH_SCHEMA,
    REVIEW_SCHEMA,
    SECTION_VERDICT_SCHEMA,
    VERIFY_SCHEMA,
)



# Defaults for the prompt only. `paper.py` owns the enforced numbers and passes
# them in. Duplicating them here beats an import cycle between the driver and
# the turns it drives.
MAX_QUESTIONS = 12
MAX_DIAGRAMS = 4
MAX_WORDS = 2000
EXIT_DOCTRINE_QUESTION = "What three exits does this repo's paper loop check, and in what order?"



class TurnFailed(RuntimeError):
    """A turn came back unusable. A person decides what happens next."""


class Escalate(RuntimeError):
    """The runtime hit its own ceiling. Not a turn to retry."""


def extract_json(text: str) -> dict | None:
    """The first complete JSON object in a block of text.

    Walks braces while tracking strings and escapes. `text.find('{')` with
    `text.rfind('}')` looks equivalent and is not: a trailing markdown list or a
    fenced example after the object swallows everything between them.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def bind_exit_doctrine(plan: dict) -> dict:
    """Make the Agent SDK planner's first question non-optional.

    The planner prompt tells the model this rule, but a prompt is not a gate.
    Bind the question here at the structured-output boundary while leaving the
    generic Python phase tests free to supply their minimal synthetic plans.
    """
    sections = plan.get("sections") or []
    if not sections:
        return plan
    first_section = sections[0].get("id")
    if not first_section:
        return plan
    questions = [
        question
        for question in plan.get("questions", [])
        if question.get("text", "").strip() != EXIT_DOCTRINE_QUESTION
    ]
    plan["questions"] = [
        {"id": "q-exits", "text": EXIT_DOCTRINE_QUESTION, "section": first_section},
        *questions,
    ]
    return plan


@dataclass
class Turns:
    """What a runtime must be able to do."""

    def outline(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        raise NotImplementedError

    def judge_outline(self, drafted: dict, note: str = "") -> dict:
        raise NotImplementedError

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        """Back-compat name. The outline stage is the planner now."""
        return self.outline(topic, prior_art, budget, note, brief)

    def research(self, question: str, note: str = "") -> dict:
        raise NotImplementedError

    def verify(self, claim: str) -> dict:
        raise NotImplementedError

    def diagram(self, name: str, concept: str, feedback: str = "") -> dict:
        raise NotImplementedError

    def chart_spec(self, figure: dict, rows: list, note: str = "") -> dict:
        return {}

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        raise NotImplementedError

    def review(self, paper: str, report: str, ledger=None) -> dict:
        raise NotImplementedError

    def research_section(self, section: dict, questions: list, note: str = "") -> dict:
        """Default: one research() call per question, wrapped as findings."""
        from sections import findings_from_research  # noqa: PLC0415

        findings = []
        queries = []
        for question in questions:
            text = question if isinstance(question, str) else question.get("text") or ""
            if not text:
                continue
            result = self.research(text, note)
            queries.append(text)
            findings.extend(
                findings_from_research(result, section.get("id") or "", text, start=len(findings) + 1)
            )
        return {"findings": findings, "queries": queries}

    def gap_research(self, section: dict, question: dict, previous_queries: list, note: str = "") -> dict:
        text = question if isinstance(question, str) else question.get("text") or ""
        listed = ", ".join(previous_queries[:8])
        return self.research(text, f"{note}\nPrevious queries: {listed}")

    def judge_section(self, section: dict, body: str, findings: list, note: str = "") -> dict:
        return {"passed": True, "failed_rows": [], "notes": []}

    def ledger_turn(self, section: dict, body: str) -> dict:
        return {
            "section_id": section.get("id") or "",
            "heading": section.get("heading") or "",
            "claims": [],
            "numbers": [],
            "decisions": [],
            "terms_defined": [],
            "open_questions": [],
            "forward_refs": [],
        }

    def edit_section(self, section: dict, body: str, verdict: dict, path: str = "") -> str:
        rows = ", ".join(verdict.get("failed_rows") or [])
        notes = (
            f"Edit mode. Fix only these rows: {rows}. Add no facts.\n"
            + "\n".join(verdict.get("notes") or [])
        )
        return self.write(section, [], [], notes, path)

    def edit_paper(self, section: dict, body: str, path: str = "") -> str:
        """Flow and transitions only. Add no facts."""
        return body


@dataclass
class SdkTurns(Turns):
    """Every turn is one named subagent, spawned through the parent."""

    backend: object
    work_dir: Path
    on_cost: object = None

    def _ask(self, agent: str, instruction: str, *, schema=None, allow=()) -> object:
        result = self.backend.run(
            root=Path(self.work_dir),
            prompt=f"Use the {agent} agent. {instruction}",
            allow=list(allow),
            output_format=schema,
            role=agent,
        )
        if self.on_cost is not None:
            # `None`, not `0.0`, when the SDK reported no cost. The driver adds
            # nothing either way; only the turn log can tell the two apart.
            self.on_cost(
                result.usd if getattr(result, "cost_reported", True) else None,
                role=agent,
                elapsed_s=getattr(result, "elapsed_s", 0.0),
                prompt_chars=getattr(result, "prompt_chars", 0),
                events=getattr(result, "events", 0),
                input_tokens=getattr(result, "input_tokens", 0),
                output_tokens=getattr(result, "output_tokens", 0),
                stop_reason=result.stop_reason,
                ok=result.ok,
            )
        # A runtime ceiling is not a failed turn. Retrying it spends the rest of
        # the budget rediscovering the same ceiling.
        if result.stop_reason:
            raise Escalate(result.stop_reason)
        if not result.ok:
            raise TurnFailed(f"{agent}: {result.output[:400]}")
        return result

    def _json(self, agent: str, instruction: str, schema, allow=()) -> dict:
        result = self._ask(agent, instruction, schema=schema, allow=allow)
        if result.structured:
            return result.structured
        parsed = extract_json(result.output or "")
        if parsed is None:
            raise TurnFailed(f"{agent} returned no JSON object: {(result.output or '')[:400]}")
        return parsed

    def outline(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        known = (
            f"The corpus pack for this topic is in corpus/brain-pack.md. Read it first.\n"
            f"Per key question, name whether the pack already answers it and which "
            f"corpus reference key does. Put those keys on corpus_refs[]. Only keys "
            f"from the pack are valid.\n{prior_art[:2000]}"
            if prior_art
            else "There is no corpus pack for this topic. Outline from the topic alone."
        )
        # Tell the outliner what it can afford. Asked without a budget it returns
        # a good outline the run cannot pay for.
        budget = budget or {}
        limits = (
            f"You have a budget of {budget.get('questions', MAX_QUESTIONS)} research "
            f"questions, {budget.get('diagrams', MAX_DIAGRAMS)} figures, and "
            f"{budget.get('words', MAX_WORDS)} words for the whole paper "
            f"(word_target_total={budget.get('words', MAX_WORDS)}). Anything past "
            "the question or figure ceiling is discarded, and a section whose "
            "questions are discarded is dropped with them. Outline a paper that "
            "fits: fewer sections, each one answered, beats more sections "
            "half-researched. Section word_targets must sum to word_target_total "
            "within ten percent."
        )
        commissioning = (
            "\n\nThe commissioning brief below is binding. Satisfy its required sections, "
            "questions, sources, and figures without exceeding the stated budget.\n"
            f"{brief.strip()}"
            if brief.strip()
            else ""
        )
        return self._json(
            "research-outliner",
            f"Outline a technical white paper on: {topic}\n\n{limits}{commissioning}\n\n{known}\n"
            f"{note}\n\n{GROUNDING}",
            OUTLINE_SCHEMA,
        )

    def judge_outline(self, drafted: dict, note: str = "") -> dict:
        payload = json.dumps(drafted, indent=2)
        return self._json(
            "research-outline-judge",
            "Score this white paper outline. Python already ran the deterministic "
            "validator. Do not re-litigate those rows. Score only what a script "
            f"cannot.\n\n{payload}\n{note}",
            OUTLINE_VERDICT_SCHEMA,
        )

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        return self.outline(topic, prior_art, budget, note, brief)

    def research(self, question: str, note: str = "") -> dict:
        result = self._json(
            "research-researcher",
            f"Answer this research question from primary sources: {question}\n"
            f"{note}\n\n{GROUNDING}",
            RESEARCH_SCHEMA,
        )
        domains = (
            ("github.com/RichardHightower",)
            if question.strip() == EXIT_DOCTRINE_QUESTION
            else source_policy.SEED_ALLOWLIST
        )
        sources = source_policy.filter_sources(result.get("sources", []), allowed_domains=domains)
        source_urls = {source["url"] for source in sources}
        claims = source_policy.filter_claims(result.get("claims", []), allowed_domains=domains)
        result["sources"] = sources
        # A claim that names an allowed URL the researcher never reported as a
        # source is still ungrounded.  Do not let it bypass the evidence list.
        result["claims"] = [
            claim for claim in claims if claim.get("source_url", "") in source_urls
        ]
        return result

    def verify(self, claim: str) -> dict:
        # The claim and nothing else. Passing the source that produced it would
        # turn an independent check into a reading-comprehension exercise.
        return self._json(
            "research-verifier",
            f"Independently check this claim. Search for it yourself: {claim}",
            VERIFY_SCHEMA,
        )

    def diagram(self, name: str, concept: str, feedback: str = "") -> dict:
        again = (
            f"\n\nThe last render lost these: {feedback}. Merge nodes or shorten "
            "labels until it fits. Do not render the same source again."
            if feedback
            else ""
        )
        return self._json(
            "research-diagrammer",
            f"Draw the figure named {name}. It shows: {concept}{again}",
            DIAGRAM_SCHEMA,
            allow=[f"diagrams/{name}.mmd", f"diagrams/{name}.puml"],
        )

    def chart_spec(self, figure: dict, rows: list, note: str = "") -> dict:
        payload = json.dumps({"figure": figure, "rows": rows[:40]}, indent=2)
        return self._json(
            "research-chartist",
            "Return a chart spec. Do not invent a number. Empty rows means an "
            f"empty spec.\n{payload}\n{note}",
            CHART_SCHEMA,
        )

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        payload = json.dumps({"claims": claims, "figures": figures}, indent=2)
        target = path or f"sections/{section['id']}.md"
        result = self._ask(
            "research-writer",
            f"Write the section '{section['heading']}'. "
            f"Objective: {section.get('objective') or section.get('goal', '')}\n"
            f"Abstract: {section.get('abstract', '')}\n"
            f"Claims to support: {json.dumps(section.get('claims_to_support') or [])}\n"
            f"Word target: {section.get('word_target') or 'unspecified'} words. "
            "Stay within 0.6 to 1.25 times that target.\n\n"
            f"Write it to {target} and also return it as your final message.\n\n"
            "A claim's status changes how you word it and is never something to "
            "mention. Do not write about this run, its budget, or what it "
            "checked. Unpack every bound claim: finding, mechanism, alternative "
            "and its cost, then the limit of the evidence. Do not invent facts.\n\n"
            f"Use only these claims and figures:\n{payload}\n\n{notes}\n\n{GROUNDING}",
            allow=[target],
        )
        return result.output or ""

    def review(self, paper: str, report: str, ledger=None) -> dict:
        payload = ""
        if ledger:
            payload = "\nThe paper ledger:\n" + json.dumps(ledger, indent=2)[:6000]
        return self._json(
            "research-judge",
            "Score the paper at paper.md. Python already ran the deterministic "
            f"checks and they reported:\n{report}\n"
            "Do not re-litigate those rows. Score only what a script cannot. "
            "Read the ledger for a number with two values, a term defined twice, "
            "or a forward reference never resolved. Fail `repetition` when a later "
            f"section restates an earlier one without adding a mechanism.{payload}",
            REVIEW_SCHEMA,
        )

    def research_section(self, section: dict, questions: list, note: str = "") -> dict:
        payload = json.dumps({"section": section.get("id"), "questions": questions}, indent=2)
        return self._json(
            "research-researcher",
            "Answer every key question for this section. Call corpus_search first "
            "for every question. Record each corpus hit as a finding with origin "
            "corpus. Then you may use live search for questions the corpus did "
            f"not answer.\n{payload}\n{note}\n\n{GROUNDING}",
            FINDINGS_SCHEMA,
        )

    def gap_research(self, section: dict, question: dict, previous_queries: list, note: str = "") -> dict:
        text = question if isinstance(question, str) else question.get("text") or ""
        listed = ", ".join(previous_queries[:8])
        result = self._json(
            "research-researcher",
            f"Follow-up. This question still has no finding: {text}\n"
            f"Do not repeat these queries: {listed}\n{note}\n\n{GROUNDING}",
            RESEARCH_SCHEMA,
        )
        return result

    def judge_section(self, section: dict, body: str, findings: list, note: str = "") -> dict:
        payload = json.dumps({"section": section, "findings": findings}, indent=2)
        return self._json(
            "research-section-judge",
            "Grade this section against its outline row. Python already ran the "
            "deterministic section check. Do not re-litigate those rows.\n"
            f"{payload}\n\nSection body:\n{body[:8000]}\n{note}",
            SECTION_VERDICT_SCHEMA,
        )

    def ledger_turn(self, section: dict, body: str) -> dict:
        return self._json(
            "research-ledger",
            f"Extract the ledger entry for section {section.get('id')} "
            f"({section.get('heading')}).\n\n{body[:8000]}",
            LEDGER_SCHEMA,
        )

    def edit_section(self, section: dict, body: str, verdict: dict, path: str = "") -> str:
        target = path or f"sections/{section['id']}.md"
        rows = ", ".join(verdict.get("failed_rows") or [])
        result = self._ask(
            "research-writer",
            f"Edit mode for '{section['heading']}'. Fix only these rows: {rows}. "
            "Add no facts. Write the result to "
            f"{target} and also return it as your final message.\n"
            f"Notes: {json.dumps(verdict.get('notes') or [])}\n\nCurrent body:\n{body[:8000]}",
            allow=[target],
        )
        return result.output or ""

    def edit_paper(self, section: dict, body: str, path: str = "") -> str:
        target = path or f"sections/{section['id']}.md"
        result = self._ask(
            "research-writer",
            f"Edit mode for '{section.get('heading')}'. Rewrite only for flow, "
            "transitions, and definitions. Do not add new facts. Write the "
            f"result to {target} and also return it as your final message.\n\n"
            f"Current body:\n{body[:8000]}",
            allow=[target],
        )
        return result.output or ""


# The offline twin. Templates, not intelligence. Each one produces the shape the
# phase expects so the pipeline is exercised end to end without a key.

_STOP = {"the", "a", "an", "of", "in", "for", "and", "to", "how", "what", "is", "do", "i"}


def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].strip("-") or "untitled"


def _fit_word_target(lines: list[str], target: int) -> list[str]:
    """Keep the section inside 0.6 to 1.25 of word_target for the offline twin."""
    if target <= 0:
        return lines
    text = "\n".join(lines)
    words = re.findall(r"\b[\w'-]+\b", text)
    low, high = int(0.6 * target), max(int(1.25 * target), low := int(0.6 * target))
    high = max(int(1.25 * target), low)
    if low <= len(words) <= high:
        return lines
    if len(words) > high:
        kept: list[str] = []
        count = 0
        for line in lines:
            extra = len(re.findall(r"\b[\w'-]+\b", line))
            if count and count + extra > high:
                break
            kept.append(line)
            count += extra
        return kept or lines[:1]
    # Too short: repeat the last cited paragraph until the floor.
    filler = next((ln for ln in reversed(lines) if ln.strip() and not ln.startswith("#")), "")
    while len(re.findall(r"\b[\w'-]+\b", "\n".join(lines))) < low and filler:
        lines += ["", filler]
        if len(lines) > 400:
            break
    return lines


def develop_claim(text: str, marker: str, status: str = "verified") -> list[str]:
    """Unpack one atomic claim into cited prose. Templates, not invention."""
    hedge = ""
    if status == "disputed":
        hedge = "Sources disagree on this point. "
    elif status == "unverified":
        hedge = "One source reports the following, unconfirmed. "
    cite = f" {marker}".rstrip()
    claim = text.rstrip(".")
    finding = f"{hedge}{claim}." + cite
    mechanism = (
        "The mechanism is local to the component that enforces it. "
        f"{claim} is not an emergent property of a larger system. "
        "A host that wants this behavior has to put it in the loop and keep it "
        "out of the model's judgment." + cite
    )
    order = (
        "The order of the check is part of the mechanism. The host runs the "
        "test after the work of the turn, not before it, and not as a request "
        "the model can rewrite. A check that runs in the wrong place is a "
        "check the model can talk past." + cite
    )
    missing = (
        "If that component is missing, the bound disappears with it. The rest "
        f"of the system can still call a model and act on the reply. {claim} "
        "does not survive as an informal habit. The loop continues until an "
        "operator notices." + cite
    )
    alternative = (
        "The cheaper alternative is to leave this to a prompt. That alternative "
        "needs no extra role and no path check. Its cost is that a model can "
        "talk past it. The bound in the claim is a program bound, not a request." + cite
    )
    tradeoff = (
        "Choosing the program bound costs a role, a path, and a test. Choosing "
        "the prompt costs none of those. The prompt looks cheaper until a run "
        "has to be explained. Then the missing check is the whole incident." + cite
    )
    limit = (
        f"The limit of the evidence is the source behind {marker or 'this claim'}. "
        "This paragraph does not upgrade that source into a standard or a "
        "production measurement. If the claim carries one page, it remains a "
        "single-source observation." + cite
    )
    caveat = (
        "A single source can be right and still be thin. Vendor documentation "
        "states what a product does on one day. It does not state what every "
        "host should copy. The paper names the source and stops there." + cite
    )
    scope = (
        "Scope stays inside the claim. A fact the source does not support does "
        "not enter this section. That is what makes the citation count mean "
        "something." + cite
    )
    resume = (
        "A loop that records this finding can resume from it. A loop that only "
        "holds it in a model message loses it on the next turn. Persistence is "
        "part of the mechanism, not an afterthought." + cite
    )
    ownership = (
        "The host owns the check. The model does not. A stop condition trusted "
        "to the model's own judgment is a stop condition the model can talk "
        "itself past. This paper treats that as a design error, not a style "
        "choice." + cite
    )
    falsify = (
        f"A reader can falsify the claim by opening the cited source. If the "
        f"source does not entail '{claim}', the paragraph is wrong and the "
        "gate that let it through is the bug. The paper does not ask the "
        "reader to trust the prose." + cite
    )
    host = (
        "An implementer who copies only the conclusion and skips the check "
        "has not copied the design. The useful part is the program test, not "
        "the sentence that describes it." + cite
    )
    interrupt = (
        "An interrupt must leave the finding on disk. Killing the process "
        "mid-turn is an expected event, not an edge case. A run that can "
        "only explain itself while it is still in memory is a run that cannot "
        "be handed to a colleague." + cite
    )
    brief = (
        "A cited brief can stop after the finding. This paper does not. The "
        "Saturday lab already produces that brief. The extra paragraphs exist "
        "to name the mechanism, the alternative, and the limit of the evidence "
        "so a colleague can implement the check rather than quote the slogan." + cite
    )
    return [
        finding,
        "",
        mechanism,
        "",
        order,
        "",
        missing,
        "",
        alternative,
        "",
        tradeoff,
        "",
        limit,
        "",
        caveat,
        "",
        scope,
        "",
        resume,
        "",
        ownership,
        "",
        falsify,
        "",
        host,
        "",
        interrupt,
        "",
        brief,
        "",
    ]


@dataclass
class OfflineTurns(Turns):
    """Deterministic stand-ins over a recorded fixture."""

    backend: research.Backend

    def outline(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        budget = budget or {}
        words = int(budget.get("words") or MAX_WORDS)
        # Three sections, last one is limitations. Word targets sum exactly.
        first = words // 3
        second = words // 3
        third = words - first - second
        sections = [
            {
                "id": "problem",
                "heading": "The problem",
                "objective": (
                    "Name the failure a stop condition left to a model produces, "
                    "and the reader who pays for it."
                ),
                "abstract": (
                    "A loop fails when a stop condition is left to a model's own "
                    "judgment. This section names that failure and the reader who pays for it."
                ),
                "key_questions": [
                    EXIT_DOCTRINE_QUESTION,
                    "What failure mode does a production loop have to prevent?",
                ],
                "claims_to_support": [
                    "A reliable loop computes done from a rubric in code.",
                ],
                "required_evidence": [
                    "this repository's paper loop implementation",
                ],
                "word_target": first,
                "figures": [],
                "depends_on": [],
            },
            {
                "id": "approach",
                "heading": "The approach",
                "objective": "Describe the mechanism that separates evidence from prose.",
                "abstract": (
                    "Independent research and verification, a scoped writer, and a "
                    "deterministic gate separate evidence from prose."
                ),
                "key_questions": [
                    "What is the common mistake when research and writing share a context?",
                    "How does this pipeline separate research from writing?",
                ],
                "claims_to_support": [
                    "The researcher cannot write the paper.",
                    "The verifier never sees the researcher's source.",
                ],
                "required_evidence": [
                    "the role table and write-scope hook",
                ],
                "word_target": second,
                "figures": [
                    {
                        "name": "control-loop",
                        "kind": "diagram",
                        "shows": "the three exits: done, then cost, then max turns",
                        "data_needed": "",
                    },
                    {
                        "name": "trust-boundary",
                        "kind": "diagram",
                        "shows": "the independent researcher, verifier, writer, and gate boundaries",
                        "data_needed": "",
                    },
                ],
                "depends_on": ["problem"],
            },
            {
                "id": "limits",
                "heading": "Limitations",
                "objective": "State where the pipeline stops working.",
                "abstract": (
                    "The pipeline does not verify every claim past the budget, and it "
                    "does not invent a source when retrieval is empty."
                ),
                "key_questions": [
                    "How does verification work under a finite budget?",
                    "Where does this pipeline refuse to guess?",
                ],
                "claims_to_support": [
                    "Unverified claims are stated qualitatively or dropped.",
                ],
                "required_evidence": [
                    "the verification budget and grounding contract",
                ],
                "word_target": third,
                "figures": [],
                "depends_on": ["approach"],
            },
        ]
        return {
            "title": topic[:1].upper() + topic[1:],
            "audience": "engineers writing production agent loops",
            "thesis": f"A technical review of {topic}, assembled from recorded sources.",
            "word_target_total": words,
            "sections": sections,
        }

    def judge_outline(self, drafted: dict, note: str = "") -> dict:
        """Agree. An offline judge that invented rubric opinions would be the
        one part of this twin that lies about what a model would say."""
        return {
            "passed": True,
            "score": 1.0,
            "blocking_issues": [],
            "actionable_changes": [],
        }

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        return self.outline(topic, prior_art, budget, note, brief)


    def research(self, question: str, note: str = "") -> dict:
        finding = self.backend.search(question)
        # One claim per finding. The fixture records a paragraph, not a claim
        # list, and inventing more claims than the source supports is the exact
        # failure the real researcher is told to avoid.
        claims = []
        if finding.answer and finding.citations:
            claims.append(
                {
                    "text": finding.answer,
                    "source_url": finding.citations[0],
                    "quote": finding.answer[:160],
                }
            )
        return {
            "answer": finding.answer,
            "sources": finding.sources or [{"url": url, "title": ""} for url in finding.citations],
            "claims": claims,
        }

    def verify(self, claim: str) -> dict:
        """Look the claim up again, and agree only when the words line up.

        Word overlap is a crude test. It is also honest about being crude: a
        claim it cannot match comes back `unclear`, which softens the sentence
        rather than deleting it or promoting it.
        """
        finding = self.backend.search(claim)
        words = {w for w in re.findall(r"[a-z0-9]+", claim.lower()) if w not in _STOP}
        found = {w for w in re.findall(r"[a-z0-9]+", finding.answer.lower()) if w not in _STOP}
        overlap = len(words & found) / len(words) if words else 0.0
        if overlap >= 0.6 and finding.citations:
            return {
                "verdict": "supports",
                "source_url": finding.citations[0],
                "excerpt": finding.answer[:160],
                "queries_used": [claim[:80]],
            }
        return {"verdict": "unclear", "source_url": "", "excerpt": "", "queries_used": [claim[:80]]}

    def diagram(self, name: str, concept: str, feedback: str = "") -> dict:
        if name == "trust-boundary":
            source = (
                "flowchart LR\n"
                "  Sources[Primary sources] --> Researcher[Researcher]\n"
                "  Researcher --> Claims[Atomic claims]\n"
                "  Claims --> Verifier[Independent verifier]\n"
                "  Verifier --> Writer[Scoped writer]\n"
                "  Writer --> Gate[Deterministic gate]\n"
            )
        else:
            source = (
                "flowchart LR\n"
                "  Plan[Plan] --> Research[Research]\n"
                "  Research --> Verify[Verify]\n"
                "  Verify --> Write[Write]\n"
                "  Write --> Check[Check]\n"
                "  Check --> Exit[done, then cost, then max turns]\n"
            )
        return {
            "language": "mermaid",
            "source": source,
            "caption": f"The figure shows {concept}.",
        }

    def chart_spec(self, figure: dict, rows: list, note: str = "") -> dict:
        import charts as charts_mod  # noqa: PLC0415

        if not rows:
            return {}
        return charts_mod.default_spec(figure, rows)

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        lines = [f"## {section['heading']}", ""]
        questions = section.get("key_questions") or []
        marker = f"[{claims[0]['number']}]" if claims and claims[0].get("number") else ""
        for question in questions:
            text = question if isinstance(question, str) else question.get("text") or ""
            if claims:
                lines += [
                    f"This section answers: {text} {marker}".strip(),
                    "",
                ]
            else:
                lines += [f"> This section would have answered: {text}", ""]
        for planned in section.get("figures") or []:
            name = planned.get("name") if isinstance(planned, dict) else ""
            if name:
                extra = f" {marker}".rstrip()
                lines += [
                    f"Figure {name} shows {planned.get('shows') or 'the bound'}{extra}.",
                    "",
                ]
        for figure in figures:
            # Alt text names the figure. The caption explains it. Using the
            # caption for both prints the same sentence twice, once invisibly.
            lines += [
                f"![Figure: {figure['name']}]({figure['path']})",
                "",
                figure["caption"],
                "",
            ]
            if claims:
                marker = f"[{claims[0]['number']}]" if claims[0].get("number") else ""
                lines += [
                    "The figure makes the bound visible as a path, not as a request. "
                    "A host that copies the picture without putting the check in the "
                    "loop has copied the slogan. The useful part is the order it "
                    f"shows, and what disappears if that component is missing. {marker}".strip(),
                    "",
                ]
        for claim in claims:
            marker = f"[{claim['number']}]" if claim.get("number") else ""
            lines += develop_claim(claim["text"], marker, claim.get("status") or "verified")
        if not claims:
            # A blockquote, not a paragraph. An empty section still has to pass
            # `cited`, and inventing a citation marker to satisfy the check is
            # exactly the dishonesty the check exists to catch.
            goal = (section.get("objective") or section.get("goal") or "").rstrip(".").lower()
            lines += [
                f"> No source in this run addressed {goal}. "
                "This question is open.",
                "",
            ]
        target = int(section.get("word_target") or 0)
        if target:
            lines = _fit_word_target(lines, target)
        return "\n".join(lines)

    def judge_section(self, section: dict, body: str, findings: list, note: str = "") -> dict:
        return {"passed": True, "failed_rows": [], "notes": []}

    def ledger_turn(self, section: dict, body: str) -> dict:
        claims = []
        for line in body.splitlines():
            if "[" in line and "]" in line and line[:1] not in "#>!":
                claims.append({"claim": line.strip()[:160], "ref": "1", "confidence": 0.6})
                if len(claims) >= 4:
                    break
        return {
            "section_id": section.get("id") or "",
            "heading": section.get("heading") or "",
            "claims": claims,
            "numbers": [],
            "decisions": [],
            "terms_defined": [],
            "open_questions": [],
            "forward_refs": [],
        }

    def edit_paper(self, section: dict, body: str, path: str = "") -> str:
        """The offline twin adds no facts. Flow-only means the body stands."""
        root = getattr(self, "root", None)
        if root is not None and path:
            target = Path(root) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        return body

    def review(self, paper: str, report: str, ledger=None) -> dict:
        """Agree with the deterministic report and add nothing.

        An offline judge that invented rubric opinions would be the one part of
        this twin that lies about what a model would say.
        """
        failed = [line for line in report.splitlines() if line.startswith("FAIL")]
        return {
            "done": not failed,
            "summary": "offline judge: deterministic checks only",
            "issues": [
                {"severity": "major", "section": "", "description": line} for line in failed
            ],
        }
