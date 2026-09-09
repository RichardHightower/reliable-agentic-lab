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


def test_it_does_not_join_streamed_tool_events(fake_sdk, repo):
    """Joining every event is how Grep output became a candidate."""

    class StreamEvent:
        def __str__(self):
            return "30\tGrep dump of app/models.py"

    fake_sdk([StreamEvent(), FakeResultMessage(result="the answer")])
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.output == "the answer"
    assert "Grep dump" not in result.output
    assert "StreamEvent" in result.raw_output


def test_a_hung_query_times_out(fake_sdk, repo, monkeypatch):
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached")

    module.query = query
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.05)
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert "timed out" in result.output
    assert "never reached" not in result.output


# -- #541: a failure path never claims a silent 0.0 -------------------------


def test_a_timed_out_query_reports_elapsed_events_and_spend_so_far(fake_sdk, repo, monkeypatch):
    """A query that already told us it had spent something before it hung
    must not lose that number just because the ceiling then cut it off."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeResultMessage(result="progress", total_cost_usd=0.33, subtype="partial")
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached", total_cost_usd=0.99)

    module.query = query
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.05)
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert result.usd == 0.33
    assert "elapsed=" in result.output
    assert "events=1" in result.output
    assert "usd=0.3300" in result.output


def test_a_timed_out_query_with_no_cost_message_reports_usd_as_none(fake_sdk, repo, monkeypatch):
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached")

    module.query = query
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.05)
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.usd is None
    assert "usd=unknown" in result.output


def test_a_message_with_no_cost_field_reports_usd_as_none_not_zero(fake_sdk, repo):
    """`total_cost_usd=None` is "the SDK never told us", not "this was free"."""
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=None)])
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.usd is None


def test_a_backend_that_raises_after_spending_reports_the_spend(fake_sdk, repo, monkeypatch):
    """A crash after the query answered must not erase what it already cost."""
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.77)])
    calls = {"n": 0}
    real_changed_files = adapter._changed_files

    def flaky(target_repo):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_changed_files(target_repo)
        raise RuntimeError("boom after spend")

    monkeypatch.setattr(adapter, "_changed_files", flaky)
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert not result.ok
    assert result.usd == 0.77
    assert "boom after spend" in result.output


def test_a_failed_backend_never_crashes_the_money_gate(fake_sdk, repo):
    """`fixer.py` calls `boss.spend(result.usd)` unconditionally. `spend`
    must tolerate the `None` a failed turn now reports instead of raising."""
    import write_scope as roles  # noqa: PLC0415

    boss = roles.Orchestrator(name="orchestrator", repo=repo)
    fake_sdk([])
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.usd is None
    boss.spend(result.usd)  # must not raise
    assert boss.spent_usd == 0.0


def test_a_bad_timeout_env_var_falls_back_to_the_default(monkeypatch, capsys):
    """#541. A non-integer value must not raise at import and kill the run."""
    assert adapter._timeout_env("SOL4_QUERY_TIMEOUT_SECONDS_UNSET", 900) == 900
    monkeypatch.setenv("SOL4_QUERY_TIMEOUT_SECONDS_TEST", "not-a-number")
    assert adapter._timeout_env("SOL4_QUERY_TIMEOUT_SECONDS_TEST", 900) == 900
    assert "not-a-number" in capsys.readouterr().err


def test_it_reads_structured_output(fake_sdk, repo):
    fake_sdk(
        [
            FakeResultMessage(
                result="fallback",
                structured_output={"done": True, "issues": []},
            )
        ]
    )
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=[])
    assert result.structured == {"done": True, "issues": []}
    assert result.output == "fallback"


def test_a_per_turn_override_does_not_mutate_the_shared_options(fake_sdk, repo):
    module = fake_sdk([FakeResultMessage(result="x")])
    options = module.ClaudeAgentOptions(cwd=str(repo))
    adapter.AgentSdkBackend(options).run(repo=repo, prompt="p", allow=[], output_format={"s": 1})
    assert options.output_format is None
    assert module.last_options.output_format == {"s": 1}


def test_it_sees_a_brand_new_untracked_file(fake_sdk, repo):
    """`git diff --name-only` misses a file git has never heard of."""
    module = fake_sdk([FakeResultMessage(result="x")])

    async def query(*, prompt, options):
        (repo / "app" / "new_mod.py").write_text("x = 3\n")
        for message in [FakeResultMessage(result="x")]:
            yield message

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(repo=repo, prompt="p", allow=["app/**"])
    assert result.wrote == ["app/new_mod.py"]
