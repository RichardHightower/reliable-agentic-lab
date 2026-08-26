#!/usr/bin/env python3
"""Module 4 stub. Broken PR Fixer. Fill repair_until_green()."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def repair_until_green(*, maker: str, budget: int) -> dict:
    raise NotImplementedError("fill repair_until_green() - see prompts/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maker", choices=["none", "reference"], default="none")
    parser.add_argument("--budget", type=int, default=3)
    args = parser.parse_args()
    payload = repair_until_green(maker=args.maker, budget=args.budget)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
