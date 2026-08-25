#!/usr/bin/env python3
"""Module 1 working loop: ready ticket -> implement -> grade -> PR body."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLUTIONS = HERE.parent
REPO = SOLUTIONS.parent
STARTER = HERE / "starter_crm"
FIXTURES = SOLUTIONS / "m2-harness" / "fixtures" / "t001-pass"
GRADER = SOLUTIONS / "m2-harness" / "graders" / "test_due_date_contract.py"
TICKET = SOLUTIONS / "tickets" / "T001-due-dates.ready.md"
WORK = HERE / "work"
PR_PATH = HERE / "PR.md"

ALLOWED = {
    "app/dates.py",
    "app/models.py",
    "app/main.py",
    "app/templates/task_form.html",
    "app/templates/tasks.html",
}


def copy_starter() -> Path:
    crm = WORK / "crm"
    if crm.exists():
        shutil.rmtree(crm)
    shutil.copytree(STARTER, crm, ignore=shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache"))
    return crm


def apply_due_dates(crm: Path) -> list[str]:
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
    body = (
        "# T001: add due dates to sales tasks\n\n"
        "Ready ticket contract implemented on a starter CRM work copy.\n\n"
        "## Files\n\n"
        + "\n".join(f"- `{name}`" for name in files)
        + "\n\n## Verify\n\nHidden grader "
        + ("passed." if passed else "failed.")
        + "\n\n## Ticket\n\n"
        + ticket
    )
    PR_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    crm = copy_starter()
    files = apply_due_dates(crm)
    result = grade(crm)
    passed = result.returncode == 0
    write_pr(files, passed)
    WORK.mkdir(parents=True, exist_ok=True)
    trace = {
        "trace_id": "m1-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "ticket_id": "T001",
        "files": files,
        "passed": passed,
        "pytest_output": ((result.stdout or "") + (result.stderr or ""))[-4000:],
        "pr": str(PR_PATH),
    }
    (WORK / "last-loop.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "files": files, "pr": str(PR_PATH)}, indent=2))
    if not passed:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
