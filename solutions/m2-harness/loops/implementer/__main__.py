from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

M2_ROOT = Path(__file__).resolve().parents[2]
if str(M2_ROOT) not in sys.path:
    sys.path.insert(0, str(M2_ROOT))

from loops.implementer.gates import DEFAULT_BUDGET
from loops.implementer.orchestrator import run_loop
from paths import DEFAULT_TICKET


def main() -> int:
    parser = argparse.ArgumentParser(description="Module 2 implementer harness")
    parser.add_argument("--ticket", type=Path, default=DEFAULT_TICKET)
    parser.add_argument("--maker", choices=["none", "reference"], default="none")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    args = parser.parse_args()
    payload = run_loop(ticket_path=args.ticket, maker_mode=args.maker, budget=args.budget)
    print(json.dumps(payload["score"], indent=2))
    return 0 if payload["score"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
