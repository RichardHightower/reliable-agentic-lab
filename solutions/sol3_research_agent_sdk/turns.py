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
    DIAGRAM_SCHEMA,
    GROUNDING,
    PLAN_SCHEMA,
    RESEARCH_SCHEMA,
    REVIEW_SCHEMA,
    VERIFY_SCHEMA,
)

# Defaults for the prompt only. `paper.py` owns the enforced numbers and passes
# them in. Duplicating them here beats an import cycle between the driver and
# the turns it drives.
MAX_QUESTIONS = 12
MAX_DIAGRAMS = 4
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
    """What a runtime must be able to do. Six calls, and no seventh."""

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        raise NotImplementedError

    def research(self, question: str, note: str = "") -> dict:
        raise NotImplementedError

    def verify(self, claim: str) -> dict:
        raise NotImplementedError

    def diagram(self, name: str, concept: str, feedback: str = "") -> dict:
        raise NotImplementedError

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        raise NotImplementedError

    def review(self, paper: str, report: str) -> dict:
        raise NotImplementedError


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
        )
        if self.on_cost is not None:
            self.on_cost(result.usd)
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

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        known = (
            f"Prior art on this topic is in prior-art.md. Read it first.\n{prior_art[:2000]}"
            if prior_art
            else "There is no prior art for this topic. Plan from the topic alone."
        )
        # Tell the planner what it can afford. Asked without a budget it returns
        # a good plan the run cannot pay for, and the harness then truncates it
        # into a paper with two sections and five orphaned headings. A planner
        # that knows the ceiling writes a whole paper under it instead.
        budget = budget or {}
        limits = (
            f"You have a budget of {budget.get('questions', MAX_QUESTIONS)} research "
            f"questions and {budget.get('diagrams', MAX_DIAGRAMS)} figures for the whole "
            "paper. Anything past that is discarded, and a section whose questions are "
            "discarded is dropped with them. Plan a paper that fits: fewer sections, each "
            "one answered, beats more sections half-researched."
        )
        doctrine = (
            "\n\nThe first research question is binding and must be exactly:\n"
            f'"{EXIT_DOCTRINE_QUESTION}"\n'
            "It belongs in the section that explains loop control. Its answer must be "
            "grounded in this repository's implementation; if no repository source is "
            "available, the researcher returns an empty finding rather than substituting "
            "a framework or blog."
        )
        commissioning = (
            "\n\nThe commissioning brief below is binding. Satisfy its required sections, "
            "questions, sources, and figures without exceeding the stated budget.\n"
            f"{brief.strip()}"
            if brief.strip()
            else ""
        )
        return bind_exit_doctrine(self._json(
            "research-planner",
            f"Plan a technical white paper on: {topic}\n\n{limits}{doctrine}{commissioning}\n\n{known}\n"
            f"{note}\n\n{GROUNDING}",
            PLAN_SCHEMA,
        ))

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

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        payload = json.dumps({"claims": claims, "figures": figures}, indent=2)
        target = path or f"sections/{section['id']}.md"
        result = self._ask(
            "research-writer",
            f"Write the section '{section['heading']}'. Its goal: {section['goal']}\n\n"
            f"Write it to {target} and also return it as your final message.\n\n"
            "A claim's status changes how you word it and is never something to "
            "mention. Do not write about this run, its budget, or what it "
            "checked. Unpack every bound claim: finding, mechanism, alternative "
            "and its cost, then the limit of the evidence. Do not invent facts.\n\n"
            f"Use only these claims and figures:\n{payload}\n\n{notes}\n\n{GROUNDING}",
            allow=[target],
        )
        return result.output or ""

    def review(self, paper: str, report: str) -> dict:
        return self._json(
            "research-judge",
            "Score the paper at paper.md. Python already ran the deterministic "
            f"checks and they reported:\n{report}\n"
            "Do not re-litigate those rows. Score only what a script cannot.",
            REVIEW_SCHEMA,
        )


# The offline twin. Templates, not intelligence. Each one produces the shape the
# phase expects so the pipeline is exercised end to end without a key.

_STOP = {"the", "a", "an", "of", "in", "for", "and", "to", "how", "what", "is", "do", "i"}


def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].strip("-") or "untitled"



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

    def plan(
        self, topic: str, prior_art: str, budget: dict | None = None, note: str = "", brief: str = ""
    ) -> dict:
        sections = [
            {"id": "problem", "heading": "The problem", "goal": f"State what {topic} must solve."},
            {
                "id": "approach",
                "heading": "The approach",
                "goal": f"Describe how {topic} works.",
            },
            {
                "id": "limits",
                "heading": "Limitations",
                "goal": f"State where {topic} stops working.",
            },
        ]
        questions = [
            {"id": "q1", "text": EXIT_DOCTRINE_QUESTION, "section": "problem"},
            {"id": "q2", "text": f"{topic} common mistake", "section": "approach"},
            {"id": "q3", "text": f"{topic} how to verify", "section": "limits"},
        ]
        return {
            "title": topic[:1].upper() + topic[1:],
            "abstract": (
                f"This paper is a technical review of {topic}. It is assembled "
                "from recorded primary sources, not from a model's memory. The "
                "question is how a host keeps an agent loop inside a bound it "
                "can check. The finding is that three program-owned exits cover "
                "the observed cases: done, then cost, then max turns. Cost is "
                "second because a loop that finished its work and then noticed "
                "it was over budget did finish. Max turns is last because a "
                "stall that burns money should hit the money cap first. The "
                "cheaper alternative is to ask the model whether it is done. "
                "That alternative needs no extra role. Its cost is that a model "
                "can talk itself past the stop. The paper names the mechanism "
                "in the host, the alternative and its cost, and the limit of "
                "the evidence. A recorded fixture is a single-source corpus. "
                "It is not a production measurement and it is not a standard."
            ),
            "sections": sections,
            "questions": questions,
            "diagrams": [
                {
                    "name": "control-loop",
                    "concept": "the three exits: done, then cost, then max turns",
                    "section": "approach",
                },
                {
                    "name": "trust-boundary",
                    "concept": "the independent researcher, verifier, writer, and gate boundaries",
                    "section": "approach",
                },
            ],
        }

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
            }
        return {"verdict": "unclear", "source_url": "", "excerpt": ""}

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

    def write(
        self, section: dict, claims: list[dict], figures: list[dict], notes: str, path: str = ""
    ) -> str:
        lines = [f"## {section['heading']}", ""]
        for figure in figures:
            # Alt text names the figure. The caption explains it. Using the
            # caption for both prints the same sentence twice, once invisibly.
            lines += [
                f"![Figure: {figure['name']}]({figure['path']})",
                "",
                figure["caption"],
                "",
            ]
        for claim in claims:
            marker = f"[{claim['number']}]" if claim.get("number") else ""
            lines += develop_claim(claim["text"], marker, claim.get("status") or "verified")
        if not claims:
            # A blockquote, not a paragraph. An empty section still has to pass
            # `cited`, and inventing a citation marker to satisfy the check is
            # exactly the dishonesty the check exists to catch.
            lines += [
                f"> No source in this run addressed {section['goal'].rstrip('.').lower()} "
                "This question is open.",
                "",
            ]
        return "\n".join(lines)

    def review(self, paper: str, report: str) -> dict:
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
