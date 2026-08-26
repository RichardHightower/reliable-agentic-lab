#!/usr/bin/env python3
"""Module 1 stub. Fill apply_change(). Do not edit the grader."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STARTER = REPO / "solutions" / "m1-implementer" / "starter_crm"
GRADER = REPO / "solutions" / "m2-harness" / "graders" / "test_due_date_contract.py"
TICKET = REPO / "solutions" / "tickets" / "T001-due-dates.ready.md"
WORK = HERE / "work"
PR_PATH = HERE / "PR.md"


def copy_starter() -> Path:
    crm = WORK / "crm"
    if crm.exists():
        shutil.rmtree(crm)
    shutil.copytree(STARTER, crm, ignore=shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache"))
    return crm


def apply_change(crm: Path) -> list[str]:
    """Implement the ready T001 contract on `crm`. Return relative files you touched."""
    raise NotImplementedError("fill apply_change() - see prompts/")


def grade(crm: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(crm) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(GRADER), "-q"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )


def write_pr(files: list[str], passed: bool) -> None:
    ticket = TICKET.read_text(encoding="utf-8")
    PR_PATH.write_text(
        "# T001 implementer\n\n"
        + "\n".join(f"- `{name}`" for name in files)
        + "\n\nGrader: "
        + ("passed" if passed else "failed")
        + "\n\n"
        + ticket,
        encoding="utf-8",
    )


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    crm = copy_starter()
    files = apply_change(crm)
    result = grade(crm)
    passed = result.returncode == 0
    write_pr(files, passed)
    print(json.dumps({"passed": passed, "files": files, "pr": str(PR_PATH)}, indent=2))
    if not passed:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
