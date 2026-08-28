"""HMAC, routing, and HTTP adapter tests. No ngrok. No Claude."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
MOD_PATH = HERE.parent / "bin" / "webhook_trigger.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("webhook_trigger", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


wt = load_mod()


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_match():
    body = b'{"ok":true}'
    secret = "s3cret"
    assert wt.verify_signature(body, sign(body, secret), secret)


def test_verify_signature_rejects_mismatch():
    assert not wt.verify_signature(b"{}", "sha256=deadbeef", "s3cret")
    assert not wt.verify_signature(b"{}", "", "s3cret")
    assert not wt.verify_signature(b"{}", sign(b"{}", "s3cret"), "")


def test_ticket_id_from_title_or_body():
    assert wt.ticket_id({"issue": {"title": "[T900] grey button"}}) == "T900"
    assert wt.ticket_id({"issue": {"title": "no id", "body": "see [T001] due dates"}}) == "T001"
    assert wt.ticket_id({"issue": {"title": "nothing"}}) is None


def test_should_run_issue_opened():
    payload = {"action": "opened", "issue": {"title": "[T900] grey button"}}
    assert wt.should_run("issues", payload) == "T900"


def test_should_run_skips_own_comment():
    payload = {
        "action": "created",
        "issue": {"title": "[T900] grey button"},
        "comment": {"body": "draft posted\n<!-- enhancer-loop -->"},
    }
    assert wt.should_run("issue_comment", payload) is None


def test_should_run_human_comment():
    payload = {
        "action": "created",
        "issue": {"title": "[T900] grey button"},
        "comment": {"body": "please add acceptance criteria"},
    }
    assert wt.should_run("issue_comment", payload) == "T900"


def test_should_run_ping_and_unrelated():
    assert wt.should_run("ping", {}) is None
    assert wt.should_run("issues", {"action": "closed", "issue": {"title": "[T900] x"}}) is None
    assert wt.should_run("pull_request", {"action": "opened"}) is None


def test_enhancer_cmd():
    assert wt.enhancer_cmd("T001") == ["task", "run", "--", "--ticket", "T001"]


def test_plugin_ready(tmp_path):
    assert not wt.plugin_ready(tmp_path)
    skill = tmp_path / ".claude" / "skills" / "enhancer-loop"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# loop\n", encoding="utf-8")
    assert wt.plugin_ready(tmp_path)


def _start(tmp_path, env: dict) -> tuple[ThreadingHTTPServer, str]:
    plugin = tmp_path / "plugin"
    skill = plugin / ".claude" / "skills" / "enhancer-loop"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# loop\n", encoding="utf-8")
    work = tmp_path / "work"
    os.environ.update(env)
    os.environ["PLUGIN_DIR"] = str(plugin)
    os.environ["WEBHOOK_WORK"] = str(work)
    os.environ["WEBHOOK_DRY_RUN"] = "1"
    server = ThreadingHTTPServer(("127.0.0.1", 0), wt.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def _post(url: str, body: dict, *, secret: str, event: str, delivery: str) -> tuple[int, dict]:
    raw = json.dumps(body).encode()
    req = Request(
        url + "/github-webhook",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": sign(raw, secret),
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as err:
        return err.code, json.loads(err.read().decode())


def test_http_health_ping_and_accept(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    server, base = _start(tmp_path, {"GITHUB_WEBHOOK_SECRET": "s3cret"})
    try:
        with urlopen(base + "/health", timeout=5) as resp:
            health = json.loads(resp.read().decode())
        assert health["ok"] is True
        assert health["plugin_ready"] is True

        code, body = _post(
            base,
            {"zen": "design for failure"},
            secret="s3cret",
            event="ping",
            delivery="d-ping",
        )
        assert code == 200
        assert body["status"] == "pong"

        code, body = _post(
            base,
            {"action": "opened", "issue": {"number": 8, "title": "[T900] grey button"}},
            secret="s3cret",
            event="issues",
            delivery="d-open",
        )
        assert code == 202
        assert body["ticket"] == "T900"
        last = json.loads((tmp_path / "work" / "last-webhook.json").read_text())
        assert last["ticket"] == "T900"
        assert last["cmd"] == ["task", "run", "--", "--ticket", "T900"]

        code, body = _post(
            base,
            {"action": "opened", "issue": {"number": 8, "title": "[T900] grey button"}},
            secret="s3cret",
            event="issues",
            delivery="d-open",
        )
        assert code == 200
        assert body["status"] == "duplicate"
    finally:
        server.shutdown()


def test_http_401_on_bad_signature(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    server, base = _start(tmp_path, {"GITHUB_WEBHOOK_SECRET": "s3cret"})
    try:
        raw = b'{"action":"opened"}'
        req = Request(
            base + "/github-webhook",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "bad",
                "X-Hub-Signature-256": "sha256=00",
            },
            method="POST",
        )
        try:
            urlopen(req, timeout=5)
            raise AssertionError("expected 401")
        except HTTPError as err:
            assert err.code == 401
    finally:
        server.shutdown()
