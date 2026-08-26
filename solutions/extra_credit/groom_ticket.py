#!/usr/bin/env python3
"""Extra credit. Groom one ticket from a GitHub Actions issue event, or locally."""
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
from solutions.loops import criteria, enhancer

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "3"))


def _issue_from_github(client: gh.GitHub, number: int) -> dict:
    payload = client.get_issue(number)
    return {
        "id": str(payload.get("number") or number),
        "title": payload.get("title") or "",
        "body": payload.get("body") or "",
        "labels": gh.label_names(payload),
        "html_url": payload.get("html_url"),
        "number": int(payload.get("number") or number),
    }


def _log(name: str, payload: dict) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_local(ticket_id: str, *, incorporate: bool, budget: int) -> dict:
    payload = enhancer.run(
        ticket_id=ticket_id,
        incorporate=incorporate,
        budget=budget,
        work_dir=WORK / "local-groom",
    )
    payload["mode"] = "local"
    payload["extra_credit"] = True
    _log("last-groom.json", payload)
    return payload


def run_github(number: int, *, budget: int, client: gh.GitHub | None = None) -> dict:
    api = client or gh.GitHub(gh.token_from_env(), gh.repo_from_env())
    issue = _issue_from_github(api, number)
    labels = issue["labels"]
    attempts = gh.attempt_count(labels)
    trace: dict = {
        "trace_id": "groom-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "mode": "github",
        "extra_credit": True,
        "issue": number,
        "attempts": attempts,
        "labels": labels,
        "actions": [],
        "ready": "ready" in labels,
    }
    if "ready" in labels:
        trace["exit"] = "already ready"
        _log("last-groom.json", trace)
        return trace
    if gh.IN_PROGRESS in labels:
        trace["exit"] = "skipped concurrent run"
        _log("last-groom.json", trace)
        return trace
    if attempts >= budget:
        api.comment(number, f"Ticket Enhancer stopped. Max attempts ({budget}) reached.")
        trace["actions"].append("comment:gave-up")
        trace["exit"] = "budget"
        _log("last-groom.json", trace)
        return trace

    api.add_label(number, gh.IN_PROGRESS)
    trace["actions"].append(f"label:{gh.IN_PROGRESS}")
    try:
        verdict = criteria.evaluate(issue)
        api.add_label(number, gh.next_attempt_label(attempts))
        if verdict["ready"]:
            api.add_label(number, "ready")
            api.comment(number, "Ticket Enhancer: this issue meets the ready contract.")
            trace["actions"].extend(["label:ready", "comment:ready"])
            trace["exit"] = "ready label"
            trace["ready"] = True
        else:
            missing = "\n".join(f"- {item}" for item in verdict["missing"]) or "- none listed"
            body = (
                f"Ticket Enhancer classified this as **{verdict['kind']}**.\n\n"
                "It is not ready for the implementer yet.\n\n"
                "Please add:\n"
                f"{missing}\n"
            )
            api.comment(number, body)
            trace["actions"].append("comment:not-ready")
            trace["exit"] = "commented"
            trace["ready"] = False
            trace["missing"] = verdict["missing"]
    finally:
        try:
            api.remove_label(number, gh.IN_PROGRESS)
            trace["actions"].append(f"unlabel:{gh.IN_PROGRESS}")
        except gh.GitHubError:
            trace["actions"].append("unlabel-failed")
    _log("last-groom.json", trace)
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Extra credit ticket groomer")
    parser.add_argument("--issue", default=os.environ.get("ISSUE_NUMBER", "T001"))
    parser.add_argument("--github", action="store_true", help="Use GitHub Issues instead of the local board.")
    parser.add_argument("--incorporate", action="store_true")
    parser.add_argument("--budget", type=int, default=MAX_ATTEMPTS)
    args = parser.parse_args()
    github_mode = args.github or (str(args.issue).isdigit() and bool(gh.token_from_env()))
    if github_mode and str(args.issue).isdigit():
        payload = run_github(int(args.issue), budget=args.budget)
        print(json.dumps({"mode": "github", "exit": payload.get("exit"), "issue": args.issue}, indent=2))
        return 0 if payload.get("exit") in {"ready label", "already ready", "skipped concurrent run"} else 1
    payload = run_local(str(args.issue), incorporate=args.incorporate, budget=args.budget)
    print(json.dumps({"mode": "local", "ready": payload.get("ready"), "gate": payload.get("gate")}, indent=2))
    return 0 if payload.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
