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

`--kind` is the durable kind recorded in a ticket's frontmatter.  On a later
poll it deliberately overrides the Judge's fresh classification while still
using the Judge's field observations.  A feature may mention a form or page
as part of its implementation without becoming a UI ticket.
"""

from __future__ import annotations

import json
import sys

REQUIRED = {
    "bug": ["title", "steps", "expected", "actual", "environment", "source_evidence"],
    "feature": ["problem", "proposal", "value", "criteria"],
    "ui": ["problem", "proposal", "value", "criteria", "wireframe"],
}


def check(
    kind: str,
    present_fields: list[str],
    source_status: str = "not_applicable",
) -> dict:
    if kind not in REQUIRED:
        raise ValueError(f"unknown ticket kind {kind!r}, expected one of {sorted(REQUIRED)}")
    required = REQUIRED[kind]
    present = set(present_fields)
    if source_status not in {"supported", "contradicted", "unknown", "not_applicable"}:
        raise ValueError(f"unknown source status {source_status!r}")
    if kind != "bug":
        source_status = "not_applicable"
    # A bug needs an inspected code path, not merely a plausible story copied
    # from its issue stub.  A Judge may only count that evidence after it says
    # the source supports the reported behavior.
    if kind == "bug" and source_status != "supported":
        present.discard("source_evidence")
    missing_fields = [f for f in required if f not in present]
    return {
        "kind": kind,
        "present_fields": [f for f in required if f in present],
        "missing_fields": missing_fields,
        "source_status": source_status,
        "blocked": source_status == "contradicted",
        "ready": not missing_fields and source_status != "contradicted",
    }


def effective_kind(reported_kind: str, persisted_kind: str | None = None) -> str:
    """Choose a persisted ticket kind over a new model classification."""
    return persisted_kind if persisted_kind is not None else reported_kind


def main() -> None:
    args = sys.argv[1:]
    persisted_kind: str | None = None
    if args[:1] == ["--kind"]:
        if len(args) < 2:
            raise SystemExit("--kind requires bug, feature, or ui")
        persisted_kind = args[1]
        if persisted_kind not in REQUIRED:
            raise SystemExit(f"unknown persisted ticket kind {persisted_kind!r}")
        args = args[2:]
    raw = args[0] if args else sys.stdin.read()
    payload = json.loads(raw)
    result = check(
        effective_kind(payload["kind"], persisted_kind),
        payload.get("present_fields", []),
        payload.get("source_status", "not_applicable"),
    )
    print(json.dumps(result))


def demo() -> None:
    assert check("feature", ["problem", "proposal", "value", "criteria"]) == {
        "kind": "feature",
        "present_fields": ["problem", "proposal", "value", "criteria"],
        "missing_fields": [],
        "source_status": "not_applicable",
        "blocked": False,
        "ready": True,
    }
    assert check("ui", ["problem", "proposal"])["missing_fields"] == [
        "value",
        "criteria",
        "wireframe",
    ]
    # A completed feature can mention a form or page.  Its original kind wins
    # over a later Judge call that would otherwise call it UI.
    assert effective_kind("ui", "feature") == "feature"
    assert check(
        effective_kind("ui", "feature"),
        ["problem", "proposal", "value", "criteria"],
    )["ready"]
    # A bug cannot pass because it has nice-looking sections: the Judge must
    # point to code that supports its claimed actual behavior.
    bug_fields = ["title", "steps", "expected", "actual", "environment", "source_evidence"]
    assert not check("bug", bug_fields)["ready"]
    assert check("bug", bug_fields, "supported")["ready"]
    contradicted = check("bug", bug_fields, "contradicted")
    assert contradicted["blocked"]
    assert not contradicted["ready"]
    # A field the model invents that isn't in the rubric is silently dropped,
    # not trusted as the source evidence a bug now requires.
    assert not check(
        "bug", ["title", "steps", "expected", "actual", "environment", "made_up"]
    )["ready"]
    print("check_fields: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
