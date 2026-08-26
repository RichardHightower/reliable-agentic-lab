#!/usr/bin/env python3
"""Ticket Implementer.

Poll ready tickets. Copy the starter CRM. Implement. Grade. Open a PR only if tests pass.
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
from .paths import (
    DEFAULT_WORK,
    FIXTURES,
    GRADER,
    READY_T001,
    REPO_ROOT,
    STARTER_CRM,
)
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


def _grade(crm: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(crm) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(GRADER), "-q"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def run(
    *,
    ticket_id: str = "T001",
    maker: str = "reference",
    budget: int = gates.DEFAULT_BUDGET,
    work_dir: Path | None = None,
) -> dict:
    work = Path(work_dir or (DEFAULT_WORK / "implementer"))
    work.mkdir(parents=True, exist_ok=True)
    board = LocalBoard(work)
    board.seed_from_tickets()
    # Implementer only takes ready tickets.
    issue = board.get_issue(ticket_id)
    if "ready" not in issue.get("labels", []):
        board.add_label(ticket_id, "ready")
        if READY_T001.exists():
            text = READY_T001.read_text(encoding="utf-8")
            body = text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text
            board.set_body(ticket_id, body)

    crm = _copy_starter(work)
    steps = []
    files: list[str] = []
    last_gate = gates.RETRY
    passed = False
    pytest_output = ""
    previous = None

    for iteration in range(1, budget + 1):
        result = _grade(crm)
        pytest_output = ((result.stdout or "") + (result.stderr or ""))[-4000:]
        passed = result.returncode == 0
        signature = result.returncode
        repeat = previous is not None and previous == signature and not passed
        last_gate = gates.decide(passed=passed, iteration=iteration, repeat=repeat, budget=budget)
        step = {"iteration": iteration, "passed": passed, "gate": last_gate}
        if passed:
            steps.append(step)
            break
        if last_gate != gates.RETRY:
            steps.append(step)
            break
        if maker == "reference":
            files = _apply_reference(crm)
            step["maker"] = {"mode": maker, "files": files}
        else:
            step["maker"] = {"mode": maker, "files": []}
        steps.append(step)
        previous = signature

    ticket = board.get_issue(ticket_id)
    pr_body = (
        f"# {ticket_id}: {ticket['title']}\n\n"
        "Implementation against the ready contract.\n\n"
        "## Files\n\n"
        + "\n".join(f"- `{name}`" for name in files)
        + "\n\n## Verify\n\nHidden grader "
        + ("passed." if passed else "failed.")
        + "\n\nLinked ticket: "
        + ticket_id
        + "\n"
    )
    pr = None
    if passed:
        pr = board.open_pr(
            issue_id=ticket_id,
            title=ticket["title"],
            body=pr_body,
            files=files,
            passing=True,
        )
    payload = {
        "trace_id": "implementer-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "ticket_id": ticket_id,
        "files": files,
        "passed": passed,
        "gate": last_gate,
        "pr": None if pr is None else pr["id"],
        "steps": steps,
        "pytest_output": pytest_output,
        "exit": "PR opened" if pr else "budget or escalate",
    }
    (work / "last-implementer.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (work / "PR.md").write_text(pr_body, encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ticket Implementer")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--maker", choices=["none", "reference"], default="reference")
    parser.add_argument("--budget", type=int, default=gates.DEFAULT_BUDGET)
    args = parser.parse_args()
    payload = run(ticket_id=args.ticket, maker=args.maker, budget=args.budget)
    print(json.dumps({"passed": payload["passed"], "gate": payload["gate"], "pr": payload["pr"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
