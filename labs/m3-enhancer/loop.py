#!/usr/bin/env python3
"""Module 3 stub. Ticket Enhancer. Fill evaluate_and_act()."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from solutions.loops.store import LocalBoard  # noqa: E402


def evaluate_and_act(board: LocalBoard, ticket_id: str, *, incorporate: bool) -> dict:
    """Classify, score, comment or label ready. Return a trace dict."""
    raise NotImplementedError("fill evaluate_and_act() - see prompts/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--incorporate", action="store_true")
    args = parser.parse_args()
    work = Path(__file__).resolve().parent / "work"
    board = LocalBoard(work)
    board.seed_from_tickets()
    payload = evaluate_and_act(board, args.ticket, incorporate=args.incorporate)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
