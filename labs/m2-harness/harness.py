#!/usr/bin/env python3
"""Module 2 stub. Fill the four functions. Python owns the retry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "solutions" / "m2-harness") not in sys.path:
    sys.path.insert(0, str(REPO / "solutions" / "m2-harness"))

from loops.implementer import grader as hidden_grader  # noqa: E402
from loops.implementer import rubric as ready_rubric  # noqa: E402
from paths import DEFAULT_TICKET  # noqa: E402

PASS, RETRY, ESCALATE = "pass", "retry", "escalate"


def maker(mode: str) -> dict:
    """Edit CRM files. No ticket state changes. No grader edits."""
    raise NotImplementedError("fill maker() - see prompts/")


def checker(grade: dict, previous_failed: list[str] | None) -> dict:
    """Read-only. Return passed, failed_node_ids, summary."""
    raise NotImplementedError("fill checker() - see prompts/")


def decide(*, passed: bool, iteration: int, failed: list[str], previous: list[str] | None, budget: int) -> str:
    """Return pass, retry, or escalate."""
    raise NotImplementedError("fill decide() - see prompts/")


def run_loop(*, maker_mode: str = "none", budget: int = 3) -> dict:
    """Orchestrator. Holds the budget. Sees summaries, not whole files."""
    raise NotImplementedError("fill run_loop() - see prompts/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maker", choices=["none", "reference"], default="none")
    parser.add_argument("--budget", type=int, default=3)
    args = parser.parse_args()
    payload = run_loop(maker_mode=args.maker, budget=args.budget)
    print(json.dumps(payload.get("score", payload), indent=2))
    return 0 if payload.get("score", {}).get("passed") or payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
