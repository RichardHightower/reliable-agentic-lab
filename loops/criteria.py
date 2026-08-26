"""What makes a ticket ready. The enhancer's judge.

This judge is the counterpart to the rubric. The rubric scores code and needs no
model. This scores prose and cannot avoid one, except for the parts that are
structural, which are worth checking deterministically anyway.

Teach the contrast. Use a model only where you must.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

BUG, FEATURE, UI = "bug", "feature", "ui"

REQUIRED = {
    BUG: [
        ("title", "a clear one-line title"),
        ("steps", "numbered steps to reproduce"),
        ("expected", "what you expected to happen"),
        ("actual", "what actually happened"),
        ("environment", "the version or environment it happened on"),
    ],
    FEATURE: [
        ("problem", "the problem this solves, not the solution"),
        ("proposal", "the proposed change"),
        ("value", "why it is worth doing"),
        ("criteria", "acceptance criteria a test can fail"),
    ],
    UI: [
        ("problem", "the problem this solves, not the solution"),
        ("proposal", "the proposed change"),
        ("value", "why it is worth doing"),
        ("criteria", "acceptance criteria a test can fail"),
        ("wireframe", "a simple wireframe or mockup"),
    ],
}

CUES = {
    "steps": re.compile(r"^\s*(\d+[.)]|\s*[-*]\s)", re.M),
    "expected": re.compile(r"\bexpect(ed)?\b", re.I),
    "actual": re.compile(r"\bactual(ly)?\b|\binstead\b", re.I),
    "environment": re.compile(r"\bversion\b|\benvironment\b|\bbrowser\b|\bos\b|\bpython\b", re.I),
    "problem": re.compile(r"\bproblem\b|\bcannot\b|\bcan not\b|\bno way to\b|\bunable\b", re.I),
    "proposal": re.compile(r"\badd\b|\ballow\b|\bsupport\b|\bexpose\b|\bintroduce\b", re.I),
    "value": re.compile(r"\bso that\b|\bbecause\b|\bin order to\b|\bwhy\b", re.I),
    "wireframe": re.compile(r"```|!\[|\bwireframe\b|\bmockup\b", re.I),
}

UI_WORDS = re.compile(r"\bform\b|\bpage\b|\bbutton\b|\bscreen\b|\btemplate\b|\blayout\b", re.I)
BUG_WORDS = re.compile(r"\bbug\b|\bbroken\b|\bcrash\b|\berror\b|\bfails?\b|\bregression\b", re.I)


@dataclass
class Verdict:
    kind: str
    ready: bool
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def signature(self) -> tuple[str, ...]:
        return tuple(sorted(self.missing))


def classify(title: str, body: str) -> str:
    text = f"{title}\n{body}"
    if BUG_WORDS.search(text):
        return BUG
    if UI_WORDS.search(text):
        return UI
    return FEATURE


def judge(ticket) -> Verdict:
    """Score one ticket against the criteria for its kind.

    Deterministic where it can be. A criterion that names a section, a number,
    or a fenced block is checkable without a model, and checking it that way
    means the model is never asked a question it can flatter its way through.
    """
    kind = classify(ticket.title, ticket.body)
    missing: list[str] = []
    reasons: list[str] = []

    for key, description in REQUIRED[kind]:
        if key == "title":
            if len(ticket.title.strip()) < 8:
                missing.append(description)
            continue
        if key == "criteria":
            if len(ticket.criteria) < 2:
                missing.append(description)
                reasons.append(
                    "A criterion that cannot fail a test is a wish. Write each one so a "
                    "test can fail it."
                )
            continue
        cue = CUES.get(key)
        if cue and not cue.search(ticket.body):
            missing.append(description)

    return Verdict(kind=kind, ready=not missing, missing=missing, reasons=reasons)


def suggestion(ticket, verdict: Verdict) -> str:
    """The comment the enhancer leaves. Concrete edits, not a grade."""
    lines = [
        f"The ticket enhancer read this as a **{verdict.kind}** ticket.",
        "",
    ]
    if verdict.ready:
        lines.append("It is ready for the implementer.")
        return "\n".join(lines)

    lines.append("It is not ready yet. Please add:")
    lines.append("")
    lines += [f"- {item}" for item in verdict.missing]
    if verdict.reasons:
        lines.append("")
        lines += verdict.reasons
    if verdict.kind == UI and any("wireframe" in m for m in verdict.missing):
        lines += ["", "A wireframe can be this simple:", "", "```", WIREFRAME, "```"]
    return "\n".join(lines)


WIREFRAME = """\
+--------------------------------------+
|  New sales task                      |
+--------------------------------------+
|  Title    [____________________]     |
|  Customer [ Acme Corp        v ]     |
|  Due date [ 2026-09-15      ] [cal]  |
|  Notes    [____________________]     |
|                                      |
|            [ Cancel ]  [ Save ]      |
+--------------------------------------+"""
