"""Deterministic rubric check for the ticket enhancer plugin.

The Judge agent decides which required fields have real content (a model
judgment call). This script decides whether that adds up to ready (a fact,
not a judgment call). Given the Judge's {kind, present_fields}, it looks up
the required field list for that kind and computes missing_fields itself. It
never trusts a model's own claim about what is missing.

Usage:
    python3 check_fields.py '{"kind": "feature", "present_fields": ["problem", "proposal"]}'
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


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    payload = json.loads(raw)
    result = check(payload["kind"], payload.get("present_fields", []))
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
    print("check_fields: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
