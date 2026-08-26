#!/usr/bin/env python3
"""Extra credit. One FastAPI webhook for ngrok or a DigitalOcean Droplet.

Not Saturday. Polling stays the class default.
Same entry point for the Python loops, Claude Code headless, Codex, OpenCode, Grok Build.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solutions.extra_credit import fix_pr, github_api as gh, groom_ticket
from solutions.loops import implementer

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
LOCK_DIR = WORK / "locks"
DEFAULT_PORT = int(os.environ.get("WEBHOOK_PORT", "8765"))
MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "3"))

app = FastAPI(title="reliable-agentic-lab extra-credit webhook")


def webhook_secret() -> str:
    return (os.environ.get("GITHUB_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SECRET") or "").strip()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def lock_path(key: str) -> Path:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
    return LOCK_DIR / f"{safe}.lock"


def acquire_lock(key: str) -> bool:
    path = lock_path(key)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock(key: str) -> None:
    lock_path(key).unlink(missing_ok=True)


def backend_name() -> str:
    return (os.environ.get("AGENT_BACKEND") or "python").strip().lower()


def _issue_number(payload: dict) -> str | None:
    issue = payload.get("issue") or {}
    if issue.get("number") is not None:
        return str(issue["number"])
    pr = payload.get("pull_request") or {}
    if pr.get("number") is not None:
        return str(pr["number"])
    suite = payload.get("check_suite") or {}
    pulls = suite.get("pull_requests") or []
    if pulls and pulls[0].get("number") is not None:
        return str(pulls[0]["number"])
    return None


def _label_names(payload: dict) -> list[str]:
    names = []
    label = payload.get("label") or {}
    if label.get("name"):
        names.append(str(label["name"]))
    issue = payload.get("issue") or {}
    names.extend(gh.label_names(issue))
    return names


def route_event(event: str, payload: dict) -> str:
    """Return groom | fulfill | fix | ping | ignore."""
    if event == "ping":
        return "ping"
    if event == "issues":
        action = payload.get("action")
        labels = _label_names(payload)
        if action == "labeled" and "ready" in labels:
            return "fulfill"
        if action in {"opened", "labeled", "edited", "reopened"}:
            return "groom"
        return "ignore"
    if event == "check_suite":
        suite = payload.get("check_suite") or {}
        if payload.get("action") == "completed" and suite.get("conclusion") == "failure":
            return "fix"
        return "ignore"
    if event == "pull_request":
        action = payload.get("action")
        if action in {"synchronize", "reopened"}:
            return "fix"
        return "ignore"
    return "ignore"


def run_python(kind: str, number: str) -> dict:
    if kind == "groom":
        if number.isdigit() and gh.token_from_env():
            return groom_ticket.run_github(int(number), budget=MAX_ATTEMPTS)
        ticket = number if number.startswith("T") else "T001"
        return groom_ticket.run_local(ticket, incorporate=False, budget=MAX_ATTEMPTS)
    if kind == "fulfill":
        ticket = number if str(number).startswith("T") else "T001"
        return implementer.run(ticket_id=ticket, doer="reference", budget=MAX_ATTEMPTS)
    if kind == "fix":
        if number.isdigit() and gh.token_from_env():
            return fix_pr.run_github(int(number), budget=MAX_ATTEMPTS, doer="reference")
        ticket = number if str(number).startswith("T") else "T001"
        return fix_pr.run_local(ticket, doer="reference", budget=MAX_ATTEMPTS)
    return {"ok": False, "error": f"unknown kind {kind}"}


def run_cli(kind: str, number: str, backend: str) -> dict:
    prompt = ROOT / "labs" / "extra-credit" / "prompts" / "claude-code.md"
    env = os.environ.copy()
    env["ISSUE_NUMBER"] = number
    env["PR_NUMBER"] = number
    env["AGENT_KIND"] = kind
    commands = {
        "claude": [
            "claude",
            "-p",
            f"Extra credit. Kind={kind}. Issue or PR {number}. Follow {prompt}. Do not edit the target repo's tests.",
            "--allowedTools",
            "Read,Edit,Write,Bash,Glob,Grep",
        ],
        "opencode": ["opencode", "run", "--dir", str(ROOT), f"Extra credit {kind} for {number}. Follow {prompt}."],
        "codex": ["codex", "exec", f"Extra credit {kind} for {number}. Follow {prompt}."],
        "grok": ["grok", "-p", f"Extra credit {kind} for {number}. Follow {prompt}.", "--no-auto-update"],
        "agent-sdk": [sys.executable, str(ROOT / "labs" / "extra-credit" / "scripts" / "groom_ticket.py"), "--issue", number],
        "langgraph": [sys.executable, str(ROOT / "labs" / "extra-credit" / "scripts" / "groom_ticket.py"), "--issue", number],
    }
    cmd = commands.get(backend)
    if not cmd:
        raise HTTPException(status_code=400, detail=f"unknown AGENT_BACKEND={backend}")
    async_mode = os.environ.get("WEBHOOK_ASYNC", "").strip() in {"1", "true", "yes"}
    if async_mode:
        subprocess.Popen(cmd, cwd=str(ROOT), env=env)
        return {"ok": True, "backend": backend, "async": True, "cmd": cmd[:2]}
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)
    return {
        "ok": result.returncode == 0,
        "backend": backend,
        "exit_code": result.returncode,
        "stdout": (result.stdout or "")[-1500:],
        "stderr": (result.stderr or "")[-800:],
    }


def handle_event(event: str, payload: dict) -> dict:
    kind = route_event(event, payload)
    if kind == "ping":
        return {"status": "pong"}
    if kind == "ignore":
        return {"status": "ignored", "event": event, "action": payload.get("action")}
    number = _issue_number(payload) or "T001"
    lock_key = f"{kind}-{number}"
    if not acquire_lock(lock_key):
        return {"status": "skipped", "reason": "agent-in-progress", "key": lock_key}
    try:
        backend = backend_name()
        if backend == "python":
            result = run_python(kind, number)
        else:
            result = run_cli(kind, number, backend)
        WORK.mkdir(parents=True, exist_ok=True)
        (WORK / "last-webhook.json").write_text(
            json.dumps({"event": event, "kind": kind, "number": number, "backend": backend, "result": result}, indent=2, default=str),
            encoding="utf-8",
        )
        return {"status": "accepted", "kind": kind, "number": number, "backend": backend, "result": result}
    finally:
        release_lock(lock_key)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "extra_credit": True, "backend": backend_name()}


@app.post("/github-webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()
    secret = webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="GITHUB_WEBHOOK_SECRET is not set")
    if not verify_signature(body, x_hub_signature_256 or "", secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    result = handle_event(x_github_event or "", payload if isinstance(payload, dict) else {})
    return JSONResponse(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extra credit GitHub webhook server")
    parser.add_argument("--host", default=os.environ.get("WEBHOOK_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    import uvicorn

    print(f"extra-credit webhook on http://{args.host}:{args.port}/github-webhook", file=sys.stderr)
    print("ngrok: ngrok http {0}".format(args.port), file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
