#!/usr/bin/env python3
"""Run a loop with nobody watching. Module 4.

The loop does not change when it runs unattended. What changes is everything
around it:

    durable state     four fields, so the next run knows what the last one did
    a hard budget     nobody is there to stop it
    a written trace   if you cannot read the last score, you cannot debug at 2am
    an exit code      CI needs a number, not a paragraph

State lives in `.harness/state.json` in the target repo, next to the receipt.
It survives the process, which is the whole point.

    python -m loops.unattended --repo work/northwind-field-crm --loop fixer
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from loops import gates
from loops.contract import Contract

STATE_FILE = ".harness/state.json"


def load_state(repo: Path) -> dict:
    path = Path(repo) / STATE_FILE
    if not path.exists():
        return {"runs": 0, "last_gate": None, "last_reason": None, "last_run_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # A corrupt state file is not a fresh start. Say so, then start fresh.
        return {
            "runs": 0,
            "last_gate": None,
            "last_reason": "previous state was unreadable",
            "last_run_at": None,
        }


def save_state(repo: Path, state: dict) -> Path:
    path = Path(repo) / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


def run(*, repo: str | Path, loop: str = "fixer", budget: int = 3, **kwargs) -> dict:
    """Run one loop unattended and record enough to debug it later."""
    contract = Contract(repo)
    contract.validate()
    target = contract.repo
    state = load_state(target)

    # Import here so a missing optional dependency in one loop cannot stop the
    # others from running in CI.
    if loop == "fixer":
        from loops.fixer import run as run_loop  # noqa: PLC0415

        trace = run_loop(repo=target, budget=budget, **kwargs)
    elif loop == "implementer":
        from loops.implementer import run as run_loop  # noqa: PLC0415

        trace = run_loop(repo=target, budget=budget, **kwargs)
    elif loop == "enhancer":
        from loops.enhancer import run as run_loop  # noqa: PLC0415

        trace = run_loop(repo=target, budget=budget, **kwargs)
    else:
        raise ValueError(f"unknown loop: {loop!r}")

    state["runs"] = int(state.get("runs", 0)) + 1
    state["loop"] = loop
    state["last_gate"] = trace.get("gate")
    state["last_reason"] = trace.get("reason")
    state["last_run_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_state(target, state)
    return {"state": state, "trace": trace}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a loop unattended")
    parser.add_argument("--repo", default="work/northwind-field-crm")
    parser.add_argument("--loop", default="fixer", choices=["fixer", "implementer", "enhancer"])
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--doer", default="reference")
    args = parser.parse_args(argv)

    extra = {} if args.loop == "enhancer" else {"doer": args.doer}
    result = run(repo=args.repo, loop=args.loop, budget=args.budget, **extra)
    state = result["state"]

    print(json.dumps(state, indent=2))

    # An unattended run reports a number. Escalate is not a crash, it is a
    # decision, so it gets its own code and CI can tell them apart.
    return {gates.PASS: 0, gates.ESCALATE: 2}.get(state["last_gate"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
