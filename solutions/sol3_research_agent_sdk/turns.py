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


@dataclass
class Turns:
    """What a runtime must be able to do. Six calls, and no seventh."""

    def plan(self, topic: str, prior_art: str, budget: dict | None = None, note: str = "") -> dict:
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

    def plan(self, topic: str, prior_art: str, budget: dict | None = None, note: str = "") -> dict:
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
        return self._json(
            "research-planner",
            f"Plan a technical white paper on: {topic}\n\n{limits}\n\n{known}\n"
            f"{note}\n\n{GROUNDING}",
            PLAN_SCHEMA,
        )

    def research(self, question: str, note: str = "") -> dict:
        return self._json(
            "research-researcher",
            f"Answer this research question from primary sources: {question}\n"
            f"{note}\n\n{GROUNDING}",
            RESEARCH_SCHEMA,
        )

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
            "checked.\n\n"
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


@dataclass
class OfflineTurns(Turns):
    """Deterministic stand-ins over a recorded fixture."""

    backend: research.Backend

    def plan(self, topic: str, prior_art: str, budget: dict | None = None, note: str = "") -> dict:
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
            {"id": "q1", "text": topic, "section": "problem"},
            {"id": "q2", "text": f"{topic} common mistake", "section": "approach"},
            {"id": "q3", "text": f"{topic} how to verify", "section": "limits"},
        ]
        return {
            "title": topic[:1].upper() + topic[1:],
            "abstract": f"A technical review of {topic}, assembled from recorded sources.",
            "sections": sections,
            "questions": questions,
            "diagrams": [
                {"name": "pipeline", "concept": f"the phases of {topic}", "section": "approach"}
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
        return {
            "language": "mermaid",
            "source": (
                "flowchart LR\n"
                "  Plan[Plan] --> Research[Research]\n"
                "  Research --> Verify[Verify]\n"
                "  Verify --> Write[Write]\n"
                "  Write --> Check[Check]\n"
            ),
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
            body = claim["text"].strip()
            if claim.get("status") == "disputed":
                body = f"Sources disagree on this point. {body}"
            elif claim.get("status") == "unverified":
                body = f"One source reports the following, unconfirmed. {body}"
            lines += [f"{body} {marker}".strip(), ""]
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
