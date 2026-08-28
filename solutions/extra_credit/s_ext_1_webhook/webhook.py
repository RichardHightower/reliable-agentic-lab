#!/usr/bin/env python3
"""Extra credit 1. FastAPI receiver GitHub can POST to.

Issues opened (and new comments) call solutions/sol1_enhancer via `task run`.
The exits stay in that folder. This file only verifies, locks, and starts.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from solutions.extra_credit import ROOT, github_api as gh
from solutions.extra_credit.s_ext_1_webhook import call_sol1

HERE = Path(__file__).resolve().parent
DEFAULT_LOCK_DIR = HERE / "work" / "locks"
DEFAULT_JOURNAL = HERE / "work" / "last-webhook.json"
TICKET_IN_TITLE = re.compile(r"\[(T\d+)\]", re.IGNORECASE)
TICKET_IN_BODY = re.compile(r"(?:^|\n)\s*id:\s*(T\d+)\b", re.IGNORECASE)

app = FastAPI(title="reliable-agentic-lab extra-credit webhook")
_lock_guard = threading.Lock()
_held: set[int] = set()

# Tests replace these.
github_factory: Callable[[], Any] = lambda: gh.GitHub(gh.token_from_env(), gh.repo_from_env())
sol1_runner: Callable[..., dict] | None = None


def secret() -> str:
    return (os.environ.get("GITHUB_WEBHOOK_SECRET") or "").strip()


def max_attempts() -> int:
    return int(os.environ.get("AGENT_MAX_ATTEMPTS") or "3")


def lock_dir() -> Path:
    return Path(os.environ.get("LOCK_DIR") or DEFAULT_LOCK_DIR)


def journal_path() -> Path:
    return Path(os.environ.get("WEBHOOK_JOURNAL") or DEFAULT_JOURNAL)


def backend_name() -> str:
    return call_sol1.backend_name()


def ticket_id_from_issue(issue: dict) -> str | None:
    title = issue.get("title") or ""
    match = TICKET_IN_TITLE.search(title)
    if match:
        return match.group(1).upper()
    body = issue.get("body") or ""
    match = TICKET_IN_BODY.search(body)
    if match:
        return match.group(1).upper()
    return None


def verify_signature(body: bytes, header: str | None) -> None:
    value = secret()
    if not value:
        raise HTTPException(status_code=503, detail="GITHUB_WEBHOOK_SECRET is not set")
    if not header:
        raise HTTPException(status_code=401, detail="missing X-Hub-Signature-256")
    digest = hmac.new(value.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    if not hmac.compare_digest(expected, header.strip()):
        raise HTTPException(status_code=401, detail="bad signature")


def write_journal(record: dict) -> None:
    path = journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")


def acquire_issue(number: int) -> bool:
    with _lock_guard:
        if number in _held:
            return False
        _held.add(number)
    lock_dir().mkdir(parents=True, exist_ok=True)
    (lock_dir() / f"{number}.lock").write_text("held\n", encoding="utf-8")
    return True


def release_issue(number: int) -> None:
    with _lock_guard:
        _held.discard(number)
    path = lock_dir() / f"{number}.lock"
    if path.exists():
        path.unlink()


def labels_named(payload_issue: dict) -> list[str]:
    return gh.label_names(payload_issue)


def handle_delivery(event: str, payload: dict) -> dict:
    """Synchronous work. FastAPI runs this after it returns 202."""
    issue = payload.get("issue") or {}
    number = int(issue.get("number") or payload.get("issue_number") or 0)
    record: dict[str, Any] = {
        "event": event,
        "action": payload.get("action"),
        "issue": number,
        "backend": backend_name(),
        "status": "ignored",
    }
    try:
        route = route_event(event, payload)
        record["route"] = route
        if route is None:
            write_journal(record)
            return record
        if number <= 0:
            record["status"] = "no-issue"
            write_journal(record)
            return record
        if not acquire_issue(number):
            record["status"] = "busy"
            write_journal(record)
            return record
        try:
            record.update(run_routed(route, number, payload, issue))
        finally:
            release_issue(number)
        write_journal(record)
        return record
    except Exception as exc:  # noqa: BLE001 — journal the crash, never 500 GitHub
        record["status"] = "error"
        record["error"] = str(exc)[:500]
        try:
            write_journal(record)
        except OSError:
            pass
        return record


def route_event(event: str, payload: dict) -> str | None:
    action = payload.get("action")
    if event == "issues" and action == "opened":
        return "groom"
    if event == "issue_comment" and action == "created":
        body = ((payload.get("comment") or {}).get("body") or "")
        if "<!-- enhancer-loop -->" in body:
            return None
        return "groom"
    if event == "issues" and action == "labeled":
        name = ((payload.get("label") or {}).get("name") or "").strip().lower()
        if name == "ready":
            return "fulfill"
        return None
    if event == "check_suite" and payload.get("action") == "completed":
        suite = payload.get("check_suite") or {}
        if suite.get("conclusion") == "failure":
            return "fix"
        return None
    if event == "check_suite" and (payload.get("check_suite") or {}).get("conclusion") == "failure":
        return "fix"
    return None


def run_routed(route: str, number: int, payload: dict, issue: dict) -> dict:
    client = github_factory()
    live = client.get_issue(number)
    names = gh.label_names(live)
    attempts = gh.attempt_count(names)
    budget = max_attempts()
    if attempts >= budget:
        client.comment(
            number,
            f"Giving up after {attempts} attempts (AGENT_MAX_ATTEMPTS={budget}).",
        )
        if gh.IN_PROGRESS in names:
            client.remove_label(number, gh.IN_PROGRESS)
        return {"status": "gave-up", "attempts": attempts}
    if route != "groom":
        # Extra credit 1 drop: only the enhancer is wired. Fulfill and fix
        # stay Saturday labs. Record the route so the journal is honest.
        return {"status": "not-wired", "attempts": attempts, "route": route}

    ticket_id = ticket_id_from_issue(live) or ticket_id_from_issue(issue)
    if not ticket_id:
        client.comment(
            number,
            "No ticket id. Put `[T001]` in the issue title, matching "
            "`solutions/sol1_enhancer`.",
        )
        return {"status": "no-ticket", "attempts": attempts}

    client.add_label(number, gh.IN_PROGRESS)
    client.add_label(number, gh.next_attempt_label(attempts))
    if attempts > 0:
        old = f"{gh.ATTEMPTS_PREFIX}{attempts}"
        if old in names:
            client.remove_label(number, old)
    try:
        result = call_sol1.run_sol1(ticket_id, runner=sol1_runner)
        status = "ok" if result.get("returncode", 1) == 0 else "sol1-failed"
        return {
            "status": status,
            "attempts": attempts + 1,
            "ticket_id": ticket_id,
            "sol1": result,
        }
    finally:
        try:
            client.remove_label(number, gh.IN_PROGRESS)
        except gh.GitHubError:
            pass


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "backend": backend_name(),
        "sol1": str(call_sol1.sol1_dir()),
    }


@app.post("/github-webhook")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()
    verify_signature(body, x_hub_signature_256)
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="body is not JSON") from exc
    event = (x_github_event or "").strip()
    preview = {
        "event": event,
        "action": payload.get("action"),
        "delivery": x_github_delivery,
        "backend": backend_name(),
        "status": "accepted",
    }
    write_journal(preview)
    background.add_task(handle_delivery, event, payload)
    return JSONResponse(preview, status_code=202)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extra credit GitHub webhook")
    parser.add_argument("--host", default=os.environ.get("WEBHOOK_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEBHOOK_PORT", "8000")))
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, factory=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
