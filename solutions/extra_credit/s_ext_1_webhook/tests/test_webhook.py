"""Signature, routing, lock, budget, and the sol1 handoff."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

from solutions.extra_credit import github_api as gh
from solutions.extra_credit.fake_github import FakeGitHub
from solutions.extra_credit.s_ext_1_webhook import webhook


SECRET = "test-secret"


def sign(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("AGENT_BACKEND", "claude")
    monkeypatch.setenv("AGENT_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("WEBHOOK_JOURNAL", str(tmp_path / "last-webhook.json"))
    webhook._held.clear()
    fake = FakeGitHub(
        {
            "number": 7,
            "title": "[T001] Add due dates",
            "body": "id: T001\n\nDraft.",
            "labels": [],
        }
    )
    webhook.github_factory = lambda: fake
    calls: list[dict] = []

    def runner(*, ticket_id, backend, cwd):
        calls.append({"ticket_id": ticket_id, "backend": backend, "cwd": str(cwd)})
        return {"returncode": 0, "stdout": "T001 waiting", "stderr": ""}

    webhook.sol1_runner = runner
    yield TestClient(webhook.app), fake, calls, tmp_path
    webhook.sol1_runner = None


def post(client, event: str, payload: dict, signature: str | None = True):
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "d1",
        "Content-Type": "application/json",
    }
    if signature is True:
        headers["X-Hub-Signature-256"] = sign(body)
    elif isinstance(signature, str):
        headers["X-Hub-Signature-256"] = signature
    return client.post("/github-webhook", content=body, headers=headers)


def test_health(client):
    test_client, _, _, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["backend"] == "claude"
    assert body["sol1"].endswith("solutions/sol1_enhancer")


def test_unsigned_is_401(client):
    test_client, _, _, _ = client
    response = post(test_client, "issues", {"action": "opened"}, signature=None)
    assert response.status_code == 401


def test_bad_signature_is_401(client):
    test_client, _, _, _ = client
    response = post(test_client, "issues", {"action": "opened"}, signature="sha256=dead")
    assert response.status_code == 401


def test_missing_secret_is_503(client, monkeypatch):
    test_client, _, _, _ = client
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    response = post(test_client, "issues", {"action": "opened"})
    assert response.status_code == 503


def test_opened_issue_calls_sol1(client):
    test_client, fake, calls, tmp_path = client
    payload = {
        "action": "opened",
        "issue": {
            "number": 7,
            "title": "[T001] Add due dates",
            "body": "draft",
            "labels": [],
        },
    }
    response = post(test_client, "issues", payload)
    assert response.status_code == 202
    assert calls == [
        {
            "ticket_id": "T001",
            "backend": "claude",
            "cwd": str(calls[0]["cwd"]),
        }
    ]
    assert "sol1_enhancer" in calls[0]["cwd"]
    assert gh.IN_PROGRESS not in gh.label_names(fake.issue)
    assert "agent-attempts-1" in gh.label_names(fake.issue)
    journal = json.loads((tmp_path / "last-webhook.json").read_text())
    assert journal["status"] == "ok"
    assert journal["ticket_id"] == "T001"


def test_gives_up_at_max_attempts(client):
    test_client, fake, calls, _ = client
    fake.issue["labels"] = [
        {"name": "agent-attempts-3"},
        {"name": "agent-in-progress"},
    ]
    payload = {
        "action": "opened",
        "issue": {"number": 7, "title": "[T001] x", "labels": fake.issue["labels"]},
    }
    webhook.handle_delivery("issues", payload)
    assert calls == []
    assert fake.comments
    assert "Giving up" in fake.comments[0]
    assert gh.IN_PROGRESS not in gh.label_names(fake.issue)


def test_skips_own_enhancer_comments(client):
    _, _, calls, _ = client
    payload = {
        "action": "created",
        "comment": {"body": "drafted fields\n<!-- enhancer-loop -->"},
        "issue": {"number": 7, "title": "[T001] x"},
    }
    record = webhook.handle_delivery("issue_comment", payload)
    assert record["status"] == "ignored"
    assert calls == []


def test_ready_label_is_not_sol1(client):
    _, _, calls, _ = client
    payload = {
        "action": "labeled",
        "label": {"name": "ready"},
        "issue": {"number": 7, "title": "[T001] x", "labels": [{"name": "ready"}]},
    }
    record = webhook.handle_delivery("issues", payload)
    assert record["route"] == "fulfill"
    assert record["status"] == "not-wired"
    assert calls == []
