"""Ticket quality criteria from the PRD."""
from __future__ import annotations

import re

BUG = [
    "clear title",
    "step-by-step reproduction steps",
    "expected vs actual behavior",
    "environment / version details",
]

FEATURE = [
    "clear problem statement",
    "proposed solution",
    "why the change is valuable",
    "edge cases or constraints",
]

UI_EXTRA = [
    "wireframe or mockup attached",
]


def classify(issue: dict) -> str:
    blob = (issue.get("title") or "") + "\n" + (issue.get("body") or "")
    low = blob.lower()
    if "wireframe" in low or "user interface" in low or re.search(r"\bui\b", low):
        return "ui"
    if "bug" in low or "misses" in low or "returns nothing" in low or "broken" in low:
        return "bug"
    return "feature"


def _has_success_criteria(body: str) -> bool:
    if "## success criteria" not in body.lower():
        return False
    bullets = [ln for ln in body.splitlines() if ln.strip().startswith("- ")]
    return len(bullets) >= 4


def evaluate(issue: dict) -> dict:
    kind = classify(issue)
    body = issue.get("body") or ""
    title = (issue.get("title") or "").strip()
    missing: list[str] = []
    if not title:
        missing.append("clear title")
    if kind == "bug":
        needed = list(BUG)
        if "repro" not in body.lower() and "steps" not in body.lower() and "search" not in body.lower():
            missing.append("step-by-step reproduction steps")
        if "expected" not in body.lower() and "get nothing" not in body.lower():
            missing.append("expected vs actual behavior")
        if "environment" not in body.lower() and "version" not in body.lower():
            missing.append("environment / version details")
    else:
        needed = list(FEATURE)
        if not _has_success_criteria(body):
            missing.extend(["proposed solution", "edge cases or constraints"])
        if "valuable" not in body.lower() and "missing follow-ups" not in body.lower() and "matter more" not in body.lower():
            missing.append("why the change is valuable")
        if kind == "ui" and "wireframe" not in body.lower() and "```" not in body:
            missing.append("wireframe or mockup attached")
    ready = _has_success_criteria(body) and not missing
    # A gold ready contract always wins.
    if _has_success_criteria(body):
        ready = True
        missing = []
    return {
        "kind": kind,
        "needed": needed + (UI_EXTRA if kind == "ui" else []),
        "missing": missing,
        "ready": ready,
    }


ASCII_WIREFRAME = """
+---------------- Task ----------------+
| Title:  [                    ]       |
| Due:    [ YYYY-MM-DD        ]       |
| [ Save ]                             |
+--------------------------------------+
""".strip()
