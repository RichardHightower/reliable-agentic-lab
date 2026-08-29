"""Deterministic rubric check for the ticket enhancer plugin.

The Judge agent decides which required fields have real content (a model
judgment call). This script decides whether that adds up to ready (a fact,
not a judgment call). Given the Judge's {kind, present_fields}, it looks up
the required field list for that kind and computes missing_fields itself. It
never trusts a model's own claim about what is missing.

Usage:
    python3 check_fields.py '{"kind": "feature", "present_fields": ["problem", "proposal"]}'
    python3 check_fields.py --kind feature '{"kind": "ui", "present_fields": [...]}'
    echo '{"kind": "bug", "present_fields": [...]}' | python3 check_fields.py
"""

from __future__ import annotations

import json
import sys

REQUIRED = {
    "bug": ["title", "steps", "expected", "actual", "environment"],
    "feature": ["problem", "proposal", "value", "criteria"],
    "ui": ["problem", "proposal", "value", "criteria", "wireframe"],
}


def check(kind: str, present_fields: list[str]) -> dict:
    if kind not in REQUIRED:
        raise ValueError(f"unknown ticket kind {kind!r}, expected one of {sorted(REQUIRED)}")
    required = REQUIRED[kind]
    present = set(present_fields)
    missing_fields = [f for f in required if f not in present]
    return {
        "kind": kind,
        "present_fields": [f for f in required if f in present],
        "missing_fields": missing_fields,
        "ready": not missing_fields,
    }


def check_payload(payload: dict, expected_kind: str | None = None) -> dict:
    """Apply the caller's stable kind when one has already been established.

    A judge still decides whether a field has meaningful content.  It must not
    be allowed to change a ticket from feature to UI halfway through a round:
    that changes the rubric and can manufacture a wireframe requirement.
    """

    return check(expected_kind or payload["kind"], payload.get("present_fields", []))


def main() -> None:
    args = sys.argv[1:]
    expected_kind = None
    if len(args) >= 2 and args[0] == "--kind":
        expected_kind = args[1]
        args = args[2:]
    raw = args[0] if args else sys.stdin.read()
    payload = json.loads(raw)
    result = check_payload(payload, expected_kind)
    print(json.dumps(result))


def demo() -> None:
    assert check("feature", ["problem", "proposal", "value", "criteria"]) == {
        "kind": "feature",
        "present_fields": ["problem", "proposal", "value", "criteria"],
        "missing_fields": [],
        "ready": True,
    }
    assert check("ui", ["problem", "proposal"])["missing_fields"] == [
        "value",
        "criteria",
        "wireframe",
    ]
    # a field the model invents that isn't in the rubric is silently dropped,
    # not trusted as evidence of readiness
    assert check("bug", ["title", "steps", "expected", "actual", "environment", "made_up"])[
        "ready"
    ]
    # A later judge may describe a feature as a UI because an acceptance
    # criterion mentions a page or button.  The persisted ticket kind wins.
    assert check_payload(
        {"kind": "ui", "present_fields": ["problem", "proposal", "value", "criteria"]},
        "feature",
    )["ready"]
    print("check_fields: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
