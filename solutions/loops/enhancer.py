#!/usr/bin/env python3
"""Ticket Enhancer (grooming agent).

Poll draft issues. Classify. Score against type criteria.
If thin, comment with concrete edits. If ready, apply the ready label.
Exit when the ticket is ready or the budget is spent.

Class default: local board. GitHub polling is optional.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import criteria, gates
from .paths import DEFAULT_WORK, READY_T001
from .store import LocalBoard


SUGGESTIONS = {
    "T001": READY_T001,
}


def _suggested_body(issue: dict) -> str | None:
    gold = SUGGESTIONS.get(issue["id"])
    if gold and gold.exists():
        text = gold.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            return parts[2].lstrip("\n") if len(parts) >= 3 else text
        return text
    kind = criteria.classify(issue)
    extra = ""
    if kind == "ui":
        extra = "\n\n## Wireframe\n\n```\n" + criteria.ASCII_WIREFRAME + "\n```\n"
    return (
        issue["body"].rstrip()
        + "\n\n## Success criteria\n\n"
        + "\n".join(f"- Specify {item}." for item in criteria.FEATURE)
        + extra
        + "\n"
    )


def _comment_body(issue: dict, verdict: dict) -> str:
    missing = "\n".join(f"- {item}" for item in verdict["missing"]) or "- none"
    suggested = _suggested_body(issue) or ""
    return (
        f"Ticket Enhancer classified this as **{verdict['kind']}**.\n\n"
        "It is not ready for the implementer yet.\n\n"
        "Please add:\n"
        f"{missing}\n\n"
        "Suggested ready body:\n\n"
        f"{suggested}"
    )


def run(
    *,
    ticket_id: str = "T001",
    incorporate: bool = False,
    budget: int = gates.DEFAULT_BUDGET,
    work_dir: Path | None = None,
) -> dict:
    board = LocalBoard(work_dir or (DEFAULT_WORK / "enhancer"))
    board.seed_from_tickets()
    issue = board.get_issue(ticket_id)
    steps: list[dict] = []
    previous_missing: list[str] | None = None
    last_gate = gates.RETRY

    for iteration in range(1, budget + 1):
        issue = board.get_issue(ticket_id)
        verdict = criteria.evaluate(issue)
        passed = bool(verdict["ready"])
        repeat = previous_missing is not None and previous_missing == verdict["missing"]
        last_gate = gates.decide(passed=passed, iteration=iteration, repeat=repeat, budget=budget)
        step = {
            "iteration": iteration,
            "kind": verdict["kind"],
            "ready": passed,
            "missing": verdict["missing"],
            "gate": last_gate,
        }
        if passed:
            board.add_label(ticket_id, "ready")
            step["action"] = "label:ready"
            steps.append(step)
            break
        board.comment(ticket_id, _comment_body(issue, verdict))
        step["action"] = "comment"
        if last_gate != gates.RETRY:
            steps.append(step)
            break
        if incorporate:
            suggested = _suggested_body(issue)
            if suggested:
                board.set_body(ticket_id, suggested)
                step["action"] = "comment+incorporate"
        steps.append(step)
        previous_missing = list(verdict["missing"])

    issue = board.get_issue(ticket_id)
    payload = {
        "trace_id": "enhancer-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "ticket_id": ticket_id,
        "labels": issue.get("labels", []),
        "comment_count": len(issue.get("comments", [])),
        "ready": "ready" in issue.get("labels", []),
        "gate": last_gate,
        "steps": steps,
        "exit": "ready label" if "ready" in issue.get("labels", []) else "budget or escalate",
    }
    work = Path(work_dir or (DEFAULT_WORK / "enhancer"))
    work.mkdir(parents=True, exist_ok=True)
    (work / "last-enhancer.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ticket Enhancer")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--incorporate", action="store_true", help="Simulate a human accepting the suggested body.")
    parser.add_argument("--budget", type=int, default=gates.DEFAULT_BUDGET)
    args = parser.parse_args()
    payload = run(ticket_id=args.ticket, incorporate=args.incorporate, budget=args.budget)
    print(json.dumps({"ready": payload["ready"], "gate": payload["gate"], "comments": payload["comment_count"]}, indent=2))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
