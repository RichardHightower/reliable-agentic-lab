#!/usr/bin/env python3
"""Unattended runner for Module 4."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STATE = HERE / "state.json"


def run_m2() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "loops.implementer",
        "--maker",
        "none",
    ]
    env_pythonpath = str(REPO / "solutions" / "m2-harness")
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = env_pythonpath + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(cmd, cwd=REPO, env=env, text=True, capture_output=True)
    return {
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout": (result.stdout or "")[-2000:],
        "stderr": (result.stderr or "")[-1000:],
    }


def run_m3() -> dict:
    script = REPO / "solutions" / "m3-research" / "loop.py"
    result = subprocess.run([sys.executable, str(script)], cwd=REPO, text=True, capture_output=True)
    return {
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout": (result.stdout or "")[-2000:],
        "stderr": (result.stderr or "")[-1000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["m2", "m3"], default="m2")
    args = parser.parse_args()
    result = run_m2() if args.target == "m2" else run_m3()
    state = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "ticket_id": "T001" if args.target == "m2" else "report",
        "branch": "main",
        "trace_id": None,
        "last_score": {"passed": result["passed"], "exit_code": result["exit_code"]},
        "human": False,
    }
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
