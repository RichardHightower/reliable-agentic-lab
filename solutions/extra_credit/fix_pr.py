#!/usr/bin/env python3
"""Extra credit. Repair a broken PR from a check_suite failure, or locally."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solutions.extra_credit import github_api as gh
from solutions.loops import fixer

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "3"))


def _log(name: str, payload: dict) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_local(ticket_id: str, *, doer: str, budget: int) -> dict:
    payload = fixer.run(
        issue_id=ticket_id,
        doer=doer,
        budget=budget,
        work_dir=WORK / "local-fix",
    )
    payload["mode"] = "local"
    payload["extra_credit"] = True
    _log("last-fix.json", payload)
    return payload


def run_github(pr_number: int, *, budget: int, doer: str, client: gh.GitHub | None = None) -> dict:
    api = client or gh.GitHub(gh.token_from_env(), gh.repo_from_env())
    issue = api.get_issue(pr_number)
    labels = gh.label_names(issue)
    attempts = gh.attempt_count(labels)
    trace: dict = {
        "trace_id": "fix-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "mode": "github",
        "extra_credit": True,
        "pr": pr_number,
        "attempts": attempts,
        "labels": labels,
        "actions": [],
        "apply": doer != "none",
    }
    if gh.IN_PROGRESS in labels:
        trace["exit"] = "skipped concurrent run"
        _log("last-fix.json", trace)
        return trace
    if attempts >= budget:
        api.comment(pr_number, f"PR Fixer stopped. Max attempts ({budget}) reached. Human needs this PR.")
        trace["actions"].append("comment:gave-up")
        trace["exit"] = "budget"
        _log("last-fix.json", trace)
        return trace

    api.add_label(pr_number, gh.IN_PROGRESS)
    trace["actions"].append(f"label:{gh.IN_PROGRESS}")
    try:
        api.add_label(pr_number, gh.next_attempt_label(attempts))
        local = run_local("T001", doer=doer, budget=budget)
        trace["local"] = {"passed": local.get("passed"), "gate": local.get("gate"), "exit": local.get("exit")}
        if local.get("passed"):
            api.comment(
                pr_number,
                "PR Fixer restored the hidden due-date test suite in the extra-credit worktree.\n"
                "Review the log artifact. This run does not force-push your branch unless you add --apply in a later lab.",
            )
            trace["actions"].append("comment:green")
            trace["exit"] = "PR green"
            trace["passed"] = True
        else:
            api.comment(
                pr_number,
                "PR Fixer could not restore the test suite within budget.\n\n"
                f"Exit: {local.get('exit')}\nGate: {local.get('gate')}",
            )
            trace["actions"].append("comment:abandoned")
            trace["exit"] = "abandoned with comment"
            trace["passed"] = False
    finally:
        try:
            api.remove_label(pr_number, gh.IN_PROGRESS)
            trace["actions"].append(f"unlabel:{gh.IN_PROGRESS}")
        except gh.GitHubError:
            trace["actions"].append("unlabel-failed")
    _log("last-fix.json", trace)
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Extra credit PR fixer")
    parser.add_argument("--pr", default=os.environ.get("PR_NUMBER", "T001"))
    parser.add_argument("--github", action="store_true")
    parser.add_argument("--doer", choices=["none", "reference"], default="reference")
    parser.add_argument("--apply", action="store_true", help="Use the reference doer. Still extra credit. No force-push.")
    parser.add_argument("--budget", type=int, default=MAX_ATTEMPTS)
    args = parser.parse_args()
    doer = args.doer if not args.apply else "reference"
    github_mode = args.github or (str(args.pr).isdigit() and bool(gh.token_from_env()))
    if github_mode and str(args.pr).isdigit():
        payload = run_github(int(args.pr), budget=args.budget, doer=doer)
        print(json.dumps({"mode": "github", "exit": payload.get("exit"), "pr": args.pr}, indent=2))
        return 0 if payload.get("exit") in {"PR green", "skipped concurrent run"} else 1
    ticket = str(args.pr) if str(args.pr).startswith("T") else "T001"
    payload = run_local(ticket, doer=doer, budget=args.budget)
    print(json.dumps({"mode": "local", "passed": payload.get("passed"), "gate": payload.get("gate")}, indent=2))
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
