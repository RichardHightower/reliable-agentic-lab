"""The final judge. The one judge that needs a model.

The rubric answers "did the work meet the contract". This answers a different
question: "is the ticket actually done". Ten green rows can sit on top of work
that misses the point, and only a reader can see that.

Two rules make a model judge safe to depend on:

1. Its verdict is a schema, not prose. A verdict that contradicts itself, such
   as a pass carrying blocking issues, is rejected.
2. Output that will not parse is a FAIL, never a pass. Borrowed from articles
   v3, where an unreadable checker result becomes a synthetic failing verdict
   rather than slipping through.

The judge holds no write tools. It reads the ticket, steps.jsonl, and the diff,
and it reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

CRITICAL, MAJOR, MINOR = "critical", "major", "minor"
BLOCKING = (CRITICAL, MAJOR)
SEVERITIES = (CRITICAL, MAJOR, MINOR)


@dataclass
class Issue:
    severity: str
    description: str

    @property
    def blocking(self) -> bool:
        return self.severity in BLOCKING


@dataclass
class Verdict:
    done: bool
    summary: str = ""
    issues: list[Issue] = field(default_factory=list)
    parsed: bool = True

    @property
    def blocking_issues(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.blocking]

    def report(self) -> str:
        head = "DONE" if self.done else "NOT DONE"
        lines = [f"{head}. {self.summary}".strip()]
        lines += [f"  [{i.severity}] {i.description}" for i in self.issues]
        return "\n".join(lines)


def synthetic_fail(reason: str) -> Verdict:
    """What an unreadable judge produces. Never a pass."""
    return Verdict(
        done=False,
        summary=f"The judge's output could not be read: {reason}",
        issues=[Issue(MAJOR, "unreadable verdict")],
        parsed=False,
    )


def extract_json(text: str) -> dict[str, Any] | None:
    """Find the JSON object in a model's reply.

    Models fence JSON in markdown, prefix it with a sentence, and follow it with
    another. Brace matching survives all three. A regex does not.
    """
    if not text:
        return None
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
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
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : index + 1])
                except ValueError:
                    start = -1
    return None


def parse_verdict(text: str) -> Verdict:  # noqa: PLR0911
    """Turn a model reply into a Verdict, or into a synthetic failure.

    Rejects a verdict that contradicts itself. A judge that says pass while
    listing blocking issues has not made a decision.

    One return per way a verdict fails to be a decision. Each carries its own
    reason into the synthetic failure, which is what makes a bad judge legible.
    """
    raw = extract_json(text)
    if raw is None:
        return synthetic_fail("no JSON object found")

    if "done" not in raw:
        return synthetic_fail("the verdict has no `done` field")
    done = raw.get("done")
    if not isinstance(done, bool):
        return synthetic_fail(f"`done` must be true or false, got {done!r}")

    issues = []
    for item in raw.get("issues") or []:
        if not isinstance(item, dict):
            return synthetic_fail("an issue is not an object")
        severity = str(item.get("severity", MAJOR)).lower()
        if severity not in SEVERITIES:
            return synthetic_fail(f"unknown severity: {severity!r}")
        issues.append(Issue(severity, str(item.get("description", "")).strip()))

    verdict = Verdict(done=done, summary=str(raw.get("summary", "")).strip(), issues=issues)

    if verdict.done and verdict.blocking_issues:
        return synthetic_fail(
            "the verdict says done while listing blocking issues. That is not a decision."
        )
    if not verdict.done and not verdict.issues:
        return synthetic_fail("the verdict says not done but names nothing to fix")
    return verdict


PROMPT = """\
You are the final judge for a coding ticket. You write nothing. You decide one
thing: is this ticket actually done?

The automated rubric already passed. Do not re-check it. Your job is what it
cannot see: whether the change delivers what the ticket asked for.

TICKET
{ticket}

PLAN (steps.jsonl)
{steps}

DIFF
{diff}

Reply with one JSON object and nothing else:

{{"done": true|false,
  "summary": "one sentence",
  "issues": [{{"severity": "critical|major|minor", "description": "..."}}]}}

Rules:
- `done: true` may not carry a critical or major issue.
- `done: false` must name at least one issue.
- Judge the ticket, not the style. The rubric owns style.
"""


def build_prompt(*, ticket: str, steps: str, diff: str, diff_limit: int = 20000) -> str:
    """Assemble the judge's prompt, with the diff truncated to a readable size."""
    if len(diff) > diff_limit:
        diff = diff[:diff_limit] + f"\n... diff truncated at {diff_limit} characters ..."
    return PROMPT.format(ticket=ticket.strip(), steps=steps.strip(), diff=diff.strip())
