"""The backend. An unattended loop needs the cost it actually spent."""

from __future__ import annotations

import subprocess
from pathlib import Path

import adapter
import gates
import pytest
from conftest import FakeResultMessage


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "r"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return root


def test_it_reads_the_result_message_not_its_repr(fake_sdk, repo):
    fake_sdk([FakeResultMessage(result="the answer", total_cost_usd=0.25)])
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.ok
    assert result.output == "the answer"


def test_cost_reaches_the_money_gate(fake_sdk, repo):
    """`fixer.py` calls `boss.spend(result.usd)` and `gates.decide` has a live
    `usd_left <= 0` branch. With `usd` pinned at zero it could never fire, so
    an unattended fixer had no cost ceiling at all."""
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.42)])
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.usd == 0.42

    spent = gates.decide(passed=False, iteration=1, budget=9, usd_left=0.0)
    assert spent.gate == gates.ESCALATE
    assert "money" in spent.reason


def test_a_runtime_ceiling_comes_back_as_a_stop_reason(fake_sdk, repo):
    for subtype, expected in (
        ("error_max_turns", "max turns"),
        ("error_max_budget_usd", "cost budget spent"),
    ):
        fake_sdk([FakeResultMessage(result="", subtype=subtype)])
        result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
        assert result.stop_reason == expected
        assert not result.ok


def test_an_error_result_is_not_ok(fake_sdk, repo):
    fake_sdk([FakeResultMessage(result="boom", is_error=True)])
    assert not adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[]).ok


def test_it_reports_only_writes_inside_scope(fake_sdk, repo):
    module = fake_sdk([FakeResultMessage(result="x")])

    async def query(*, prompt, options):
        (repo / "app" / "main.py").write_text("x = 2\n")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_x.py").write_text("def test_x(): pass\n")
        for message in [FakeResultMessage(result="x")]:
            yield message

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=["app/**"])
    assert result.wrote == ["app/main.py"]


def test_it_fails_gracefully_with_no_sdk(repo, monkeypatch):
    import sys  # noqa: PLC0415

    monkeypatch.delitem(sys.modules, "claude_agent_sdk", raising=False)
    real = __import__

    def blocked(name, *args, **kwargs):
        if name == "claude_agent_sdk":
            raise ImportError("no sdk")
        return real(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert not result.ok
    assert "agent sdk backend failed" in result.output
