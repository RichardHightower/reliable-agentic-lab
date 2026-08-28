"""The backend. It must never claim a write it did not make, and it must
report what a turn cost."""

from __future__ import annotations

import subprocess
from pathlib import Path

import adapter
import pytest
from conftest import FakeResultMessage


@pytest.fixture
def target(tmp_path) -> Path:
    """A real git repo, because write tracking asks git what changed."""
    root = tmp_path / "r"
    root.mkdir()
    return git_repo(root)


def git_repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "main.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return root


def test_it_reads_the_result_message_not_its_repr(fake_sdk, target):
    """`str(message)` is how a verdict gets lost in a dump of tool events."""
    fake_sdk(
        [FakeResultMessage(result="the answer", total_cost_usd=0.25, structured_output={"a": 1})]
    )
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])
    assert result.ok
    assert result.output == "the answer"
    assert result.structured == {"a": 1}


def test_cost_reaches_the_caller(fake_sdk, target):
    """`DoerResult.usd` sat on the dataclass and was never assigned, so a
    money gate fed by it could never fire."""
    repo = target
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.42)])
    assert adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[]).usd == 0.42


def test_a_runtime_ceiling_comes_back_as_a_stop_reason(fake_sdk, target):
    repo = target
    for subtype, expected in (
        ("error_max_turns", "max turns"),
        ("error_max_budget_usd", "cost budget spent"),
    ):
        fake_sdk([FakeResultMessage(result="", subtype=subtype)])
        result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
        assert result.stop_reason == expected
        assert not result.ok


def test_an_error_result_is_not_ok(fake_sdk, target):
    repo = target
    fake_sdk([FakeResultMessage(result="boom", is_error=True)])
    assert not adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[]).ok


def test_it_sees_a_brand_new_untracked_file(fake_sdk, tmp_path):
    """`git diff --name-only` misses a file git has never heard of, and this
    loop's whole job is creating those."""
    (tmp_path / "r").mkdir()
    repo = git_repo(tmp_path / "r")
    module = fake_sdk([FakeResultMessage(result="x")])

    async def query(*, prompt, options):
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_new.py").write_text("def test_x(): pass\n")
        for message in [FakeResultMessage(result="x")]:
            yield message

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=["tests/**"])
    assert result.wrote == ["tests/test_new.py"]


def test_it_reports_only_writes_inside_scope(fake_sdk, target):
    repo = target
    module = fake_sdk([FakeResultMessage(result="x")])

    async def query(*, prompt, options):
        (repo / "app" / "main.py").write_text("x = 2\n")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_new.py").write_text("def test_x(): pass\n")
        for message in [FakeResultMessage(result="x")]:
            yield message

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=["app/**"])
    assert result.wrote == ["app/main.py"]


def test_a_per_turn_override_does_not_mutate_the_shared_options(fake_sdk, target):
    repo = target
    module = fake_sdk([FakeResultMessage(result="x")])
    options = module.ClaudeAgentOptions(cwd=str(repo))
    adapter.AgentSdkBackend(options).run(repo=repo, prompt="p", allow=[], output_format={"s": 1})
    assert options.output_format is None
    assert module.last_options.output_format == {"s": 1}


def test_it_fails_gracefully_with_no_sdk(target, monkeypatch):
    import sys  # noqa: PLC0415

    repo = target
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
    assert result.wrote == []
