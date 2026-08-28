#!/usr/bin/env python3
"""GitHub webhook adapter for the copied sol1_enhancer plugin.

ngrok forwards HTTPS to this process. This process replies fast, then starts
one `task run -- --ticket Txxx` in the copied plugin folder. The enhancer
loop still owns the exits.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TICKET_RE = re.compile(r"\[(T\d+)\]")
MARKER = "<!-- enhancer-loop -->"
DEFAULT_PORT = int(os.environ.get("WEBHOOK_PORT", "8765"))


def plugin_dir() -> Path:
    override = os.environ.get("PLUGIN_DIR", "").strip()
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


def work_dir() -> Path:
    override = os.environ.get("WEBHOOK_WORK", "").strip()
    if override:
        return Path(override).resolve()
    return plugin_dir() / "work"


def webhook_secret() -> str:
    return (
        os.environ.get("GITHUB_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SECRET") or ""
    ).strip()


def plugin_ready(folder: Path | None = None) -> bool:
    root = folder or plugin_dir()
    return (root / ".claude" / "skills" / "enhancer-loop" / "SKILL.md").is_file()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def ticket_id(payload: dict) -> str | None:
    issue = payload.get("issue") or {}
    title = str(issue.get("title") or "")
    match = TICKET_RE.search(title)
    if match:
        return match.group(1)
    body = str(issue.get("body") or "")
    match = TICKET_RE.search(body)
    return match.group(1) if match else None


def should_run(event: str, payload: dict) -> str | None:
    """Return a ticket id, or None to ignore."""
    if event == "ping":
        return None
    if event == "issues":
        if payload.get("action") in {"opened", "edited", "reopened"}:
            return ticket_id(payload)
        return None
    if event == "issue_comment":
        if payload.get("action") != "created":
            return None
        comment = (payload.get("comment") or {}).get("body") or ""
        if MARKER in comment:
            return None
        return ticket_id(payload)
    return None


def lock_path(ticket: str) -> Path:
    folder = work_dir() / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in ticket)
    return folder / f"{safe}.lock"


def acquire_lock(ticket: str) -> bool:
    path = lock_path(ticket)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock(ticket: str) -> None:
    lock_path(ticket).unlink(missing_ok=True)


def already_seen(delivery_id: str) -> bool:
    if not delivery_id:
        return False
    folder = work_dir() / "deliveries"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{delivery_id}.json"
    if path.exists():
        return True
    path.write_text("{}", encoding="utf-8")
    return False


def enhancer_cmd(ticket: str) -> list[str]:
    return ["task", "run", "--", "--ticket", ticket]


def spawn_enhancer(ticket: str, meta: dict) -> None:
    work = work_dir()
    work.mkdir(parents=True, exist_ok=True)
    (work / "last-webhook.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if os.environ.get("WEBHOOK_DRY_RUN", "").strip() in {"1", "true", "yes"}:
        release_lock(ticket)
        return
    log = work / f"enhancer-{ticket}.log"
    try:
        with log.open("ab") as out:
            proc = subprocess.Popen(
                enhancer_cmd(ticket),
                cwd=str(plugin_dir()),
                stdout=out,
                stderr=subprocess.STDOUT,
            )
        proc.wait()
    finally:
        release_lock(ticket)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[webhook]", fmt % args)

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send(
                200,
                {
                    "ok": True,
                    "triggers": "sol1_enhancer",
                    "plugin_ready": plugin_ready(),
                    "plugin_dir": str(plugin_dir()),
                },
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/github-webhook":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length)
        secret = webhook_secret()
        if not secret:
            self._send(503, {"error": "GITHUB_WEBHOOK_SECRET is not set"})
            return
        sig = self.headers.get("X-Hub-Signature-256") or ""
        if not verify_signature(raw, sig, secret):
            self._send(401, {"error": "invalid signature"})
            return
        event = self.headers.get("X-GitHub-Event") or ""
        delivery = self.headers.get("X-GitHub-Delivery") or ""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return
        if not isinstance(payload, dict):
            self._send(400, {"error": "invalid json"})
            return
        if event == "ping":
            self._send(200, {"status": "pong"})
            return
        if not plugin_ready():
            self._send(
                503,
                {
                    "error": "plugin not copied",
                    "hint": "run bin/copy_plugin.sh from this folder",
                },
            )
            return
        if already_seen(delivery):
            self._send(200, {"status": "duplicate", "delivery": delivery})
            return
        ticket = should_run(event, payload)
        if not ticket:
            self._send(200, {"status": "ignored", "event": event, "action": payload.get("action")})
            return
        if not acquire_lock(ticket):
            self._send(200, {"status": "skipped", "reason": "in-progress", "ticket": ticket})
            return
        meta = {
            "event": event,
            "action": payload.get("action"),
            "ticket": ticket,
            "delivery": delivery,
            "issue": (payload.get("issue") or {}).get("number"),
            "cmd": enhancer_cmd(ticket),
        }
        if os.environ.get("WEBHOOK_DRY_RUN", "").strip() in {"1", "true", "yes"}:
            spawn_enhancer(ticket, meta)
        else:
            threading.Thread(target=spawn_enhancer, args=(ticket, meta), daemon=True).start()
        self._send(202, {"status": "accepted", "ticket": ticket})


def serve(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    if not webhook_secret():
        raise SystemExit("set GITHUB_WEBHOOK_SECRET before starting")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"listening on http://127.0.0.1:{port}/github-webhook")
    print(f"plugin: {plugin_dir()}")
    print(f"plugin_ready: {plugin_ready()}")
    print(f"then: ngrok http {port}")
    print("spawns: task run -- --ticket <id>")
    server.serve_forever()


def main() -> int:
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
