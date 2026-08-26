#!/usr/bin/env python3
"""Broken PR Fixer.

Detect a failing pull request. Read the failure. Attempt a fix. Re-run checks.
Stop when green or the retry budget is exhausted, then leave a comment.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import gates
from .paths import DEFAULT_WORK, FIXTURES, GRADER, REPO_ROOT, STARTER_CRM
from .store import LocalBoard

ALLOWED = {
    "app/dates.py",
    "app/models.py",
    "app/main.py",
    "app/templates/task_form.html",
    "app/templates/tasks.html",
}


def _copy_starter(work: Path) -> Path:
    crm = work / "crm"
    if crm.exists():
        shutil.rmtree(crm)
    shutil.copytree(STARTER_CRM, crm, ignore=shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache"))
    return crm


def _apply_reference(crm: Path) -> list[str]:
    written = []
    for src in sorted(FIXTURES.rglob("*")):
        if not src.is_file():
            continue
        relative = str(src.relative_to(FIXTURES))
        if relative not in ALLOWED:
            continue
        dest = crm / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(relative)
    return written


def _grade(crm: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(crm) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(GRADER), "-q"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    output = ((result.stdout or "") + (result.stderr or ""))[-4000:]
    return {"passed": result.returncode == 0, "output": output, "exit_code": result.returncode}


def run(
    *,
    issue_id: str = "T001",
    maker: str = "reference",
    budget: int = gates.DEFAULT_BUDGET,
    work_dir: Path | None = None,
) -> dict:
    work = Path(work_dir or (DEFAULT_WORK / "fixer"))
    work.mkdir(parents=True, exist_ok=True)
    board = LocalBoard(work)
    board.seed_from_tickets()
    crm = _copy_starter(work)
    first = _grade(crm)
    pr = board.open_pr(
        issue_id=issue_id,
        title=f"fix: restore {issue_id}",
        body="Broken PR seeded from starter CRM. Hidden grader is red on purpose.",
        files=[],
        passing=first["passed"],
    )
    steps = []
    last_gate = gates.RETRY
    previous = None
    files: list[str] = []
    last_grade = first

    for iteration in range(1, budget + 1):
        last_grade = _grade(crm)
        passed = last_grade["passed"]
        repeat = previous is not None and previous == last_grade["exit_code"] and not passed
        last_gate = gates.decide(passed=passed, iteration=iteration, repeat=repeat, budget=budget)
        step = {
            "iteration": iteration,
            "passed": passed,
            "gate": last_gate,
            "failure": None if passed else last_grade["output"][-500:],
        }
        if passed:
            board.mark_pr(pr["id"], True)
            board.comment_pr(pr["id"], "Fixer restored the hidden grader to green.")
            steps.append(step)
            break
        if last_gate != gates.RETRY:
            board.comment_pr(
                pr["id"],
                "Fixer gave up. Budget or repeat failure. Human needs to take this PR.\n\n"
                + last_grade["output"][-800:],
            )
            steps.append(step)
            break
        if maker == "reference":
            files = _apply_reference(crm)
            step["maker"] = {"mode": maker, "files": files}
        else:
            step["maker"] = {"mode": maker, "files": []}
        steps.append(step)
        previous = last_grade["exit_code"]

    payload = {
        "trace_id": "fixer-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "pr": pr["id"],
        "passed": last_grade["passed"],
        "gate": last_gate,
        "files": files,
        "steps": steps,
        "exit": "PR green" if last_grade["passed"] else "abandoned with comment",
    }
    (work / "last-fixer.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Broken PR Fixer")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--maker", choices=["none", "reference"], default="reference")
    parser.add_argument("--budget", type=int, default=gates.DEFAULT_BUDGET)
    args = parser.parse_args()
    payload = run(issue_id=args.ticket, maker=args.maker, budget=args.budget)
    print(json.dumps({"passed": payload["passed"], "gate": payload["gate"], "pr": payload["pr"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
