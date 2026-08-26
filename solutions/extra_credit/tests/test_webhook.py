from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from solutions.extra_credit import webhook


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_and_rejects():
    body = b'{"ok":true}'
    secret = "s3cret"
    good = _sign(secret, body)
    assert webhook.verify_signature(body, good, secret) is True
    assert webhook.verify_signature(body, "sha256=deadbeef", secret) is False
    assert webhook.verify_signature(body, good, "") is False


def test_route_issues_and_ready_and_checks():
    assert webhook.route_event("ping", {}) == "ping"
    assert webhook.route_event("issues", {"action": "opened", "issue": {"number": 1}}) == "groom"
    assert (
        webhook.route_event(
            "issues",
            {
                "action": "labeled",
                "label": {"name": "ready"},
                "issue": {"number": 1, "labels": [{"name": "ready"}]},
            },
        )
        == "fulfill"
    )
    assert (
        webhook.route_event(
            "check_suite",
            {
                "action": "completed",
                "check_suite": {"conclusion": "failure", "pull_requests": [{"number": 9}]},
            },
        )
        == "fix"
    )
    assert (
        webhook.route_event(
            "check_suite", {"action": "completed", "check_suite": {"conclusion": "success"}}
        )
        == "ignore"
    )


def test_health_and_missing_secret(monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    client = TestClient(webhook.app)
    assert client.get("/health").json()["ok"] is True
    response = client.post("/github-webhook", content=b"{}", headers={"X-GitHub-Event": "ping"})
    assert response.status_code == 503


def test_invalid_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    client = TestClient(webhook.app)
    response = client.post(
        "/github-webhook",
        content=b"{}",
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=nope"},
    )
    assert response.status_code == 401


def test_ping_ok(monkeypatch):
    secret = "s3cret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    body = b'{"zen":"ok"}'
    client = TestClient(webhook.app)
    response = client.post(
        "/github-webhook",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _sign(secret, body)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pong"


def test_opened_issue_calls_groom(monkeypatch):
    secret = "s3cret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("AGENT_BACKEND", "python")
    called = {}

    def fake_groom(number, budget, client=None):
        called["n"] = number
        return {"exit": "commented", "ready": False}

    monkeypatch.setattr(webhook.groom_ticket, "run_github", fake_groom)
    monkeypatch.setattr(webhook.gh, "token_from_env", lambda: "tok")
    body = json.dumps(
        {
            "action": "opened",
            "issue": {"number": 42, "title": "Due dates", "body": "thin", "labels": []},
        }
    ).encode()
    client = TestClient(webhook.app)
    response = client.post(
        "/github-webhook",
        content=body,
        headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": _sign(secret, body)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "groom"
    assert payload["number"] == "42"
    assert called["n"] == 42


def test_lock_skips_second_run(monkeypatch, tmp_path):
    monkeypatch.setattr(webhook, "LOCK_DIR", tmp_path)
    assert webhook.acquire_lock("groom-1") is True
    assert webhook.acquire_lock("groom-1") is False
    webhook.release_lock("groom-1")
    assert webhook.acquire_lock("groom-1") is True
