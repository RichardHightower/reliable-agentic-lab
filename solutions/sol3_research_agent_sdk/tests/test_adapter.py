"""The backend. It must never claim a write it did not make."""

from __future__ import annotations

import time
from pathlib import Path

import adapter
from conftest import FakeResultMessage


def test_it_reads_the_result_message_not_its_repr(fake_sdk, work):
    """`str(message)` is how a verdict gets lost in a dump of tool events."""
    fake_sdk(
        [FakeResultMessage(result="the answer", total_cost_usd=0.25, structured_output={"a": 1})]
    )
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert result.ok
    assert result.output == "the answer"
    assert result.usd == 0.25
    assert result.structured == {"a": 1}


def test_a_runtime_ceiling_comes_back_as_a_stop_reason(fake_sdk, work):
    for subtype, expected in (
        ("error_max_turns", "max turns"),
        ("error_max_budget_usd", "cost budget spent"),
    ):
        fake_sdk([FakeResultMessage(result="", subtype=subtype)])
        result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
        assert result.stop_reason == expected
        assert not result.ok


def test_an_error_result_is_not_ok(fake_sdk, work):
    fake_sdk([FakeResultMessage(result="boom", is_error=True)])
    assert not adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[]).ok


def test_it_fails_gracefully_with_no_sdk(work, monkeypatch):
    import sys  # noqa: PLC0415  (blocked below)

    monkeypatch.delitem(sys.modules, "claude_agent_sdk", raising=False)
    real = __import__

    def blocked(name, *args, **kwargs):
        if name == "claude_agent_sdk":
            raise ImportError("no sdk")
        return real(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert not result.ok
    assert "agent sdk backend failed" in result.output
    assert result.wrote == []


def test_a_per_turn_override_does_not_mutate_the_shared_options(fake_sdk, work):
    """One turn's `output_format` leaking into every later turn is the bug."""
    module = fake_sdk([FakeResultMessage(result="x")])
    options = module.ClaudeAgentOptions(cwd=str(work))
    adapter.AgentSdkBackend(options).run(root=work, prompt="p", allow=[], output_format={"s": 1})
    assert options.output_format is None
    assert module.last_options.output_format == {"s": 1}


def test_it_reports_only_writes_inside_scope(fake_sdk, work):
    module = fake_sdk([FakeResultMessage(result="x")])

    async def query(*, prompt, options):
        (Path(work) / "paper.md").write_text("in scope")
        (Path(work) / "secret.md").write_text("out of scope")
        for message in [FakeResultMessage(result="x")]:
            yield message

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=["paper.md"])
    assert result.wrote == ["paper.md"]


def test_the_snapshot_ignores_the_disposable_directories(work):
    (Path(work) / ".cache").mkdir()
    (Path(work) / ".cache" / "big.bin").write_text("x")
    (Path(work) / "paper.md").write_text("x")
    assert sorted(adapter._snapshot(work)) == ["paper.md"]


def test_the_snapshot_notices_a_same_length_overwrite(work):
    """A name-only listing misses an edit that keeps the file the same size."""
    path = Path(work) / "paper.md"
    path.write_text("aaa")
    before = adapter._snapshot(work)
    time.sleep(0.01)
    path.write_text("bbb")
    assert adapter._changed(before, adapter._snapshot(work)) == ["paper.md"]


def test_it_does_not_join_streamed_tool_events(fake_sdk, work):
    """Joining every event is how tool dump became a paper section."""

    class StreamEvent:
        def __str__(self):
            return "tool dump of every search hit"

    fake_sdk(
        [
            StreamEvent(),
            FakeResultMessage(
                result="the answer",
                structured_output={"done": True, "issues": []},
            ),
        ]
    )
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert result.output == "the answer"
    assert result.structured == {"done": True, "issues": []}
    assert "tool dump" not in result.output
    assert "StreamEvent" in result.raw_output


def test_a_hung_query_times_out(fake_sdk, work, monkeypatch):
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached")

    module.query = query
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.05)
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert "timed out" in result.output
    assert "never reached" not in result.output


def test_the_timeout_names_the_role_the_elapsed_time_and_the_event_count(
    fake_sdk, work, monkeypatch
):
    """A timeout that says only "timed out" leaves nothing to diagnose (#305)."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeResultMessage(result="partial")
        await adapter.asyncio.sleep(1)

    module.query = query
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.05)
    result = adapter.AgentSdkBackend(object()).run(
        root=work, prompt="a long prompt", allow=[], role="outliner"
    )
    assert result.stop_reason == "query timeout"
    assert "role=outliner" in result.output
    assert "events=1" in result.output
    assert f"prompt={len('a long prompt')} chars" in result.output
    assert result.events == 1
    assert result.elapsed_s > 0
    assert result.prompt_chars == len("a long prompt")
    # The diagnostics carry the shape of the prompt, never the prompt itself.
    assert "a long prompt" not in result.output


def test_a_slow_query_writes_a_heartbeat(fake_sdk, work, monkeypatch, capsys):
    """A query that stalls emits no events, which is when a heartbeat matters."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(0.12)
        yield FakeResultMessage(result="done", total_cost_usd=0.5)

    module.query = query
    monkeypatch.setattr(adapter, "HEARTBEAT_SECONDS", 0.02)
    result = adapter.AgentSdkBackend(object()).run(
        root=work, prompt="p", allow=[], role="outliner"
    )
    assert result.output == "done"
    assert "[sol3] t+" in capsys.readouterr().err


def test_the_heartbeat_says_unknown_cost_not_zero(fake_sdk, work, monkeypatch, capsys):
    """`usd=0.00` for ten minutes reads as free. It means nothing told us yet."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(0.08)
        yield FakeResultMessage(result="done", total_cost_usd=0.5)
        await adapter.asyncio.sleep(0.08)

    module.query = query
    monkeypatch.setattr(adapter, "HEARTBEAT_SECONDS", 0.02)
    adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[], role="outliner")
    beats = [line for line in capsys.readouterr().err.splitlines() if "[sol3] t+" in line]
    assert any("usd=?" in line for line in beats), beats
    assert any("usd=0.50" in line for line in beats), beats
    assert not any("usd=0.00" in line for line in beats), beats


def test_the_query_timeout_reads_the_environment(monkeypatch):
    """Without an override the next live run is another ten minutes of guessing."""
    import importlib  # noqa: PLC0415

    monkeypatch.setenv("SOL3_QUERY_TIMEOUT_SECONDS", "1234")
    reloaded = importlib.reload(adapter)
    try:
        assert reloaded.QUERY_TIMEOUT_SECONDS == 1234
    finally:
        monkeypatch.delenv("SOL3_QUERY_TIMEOUT_SECONDS")
        importlib.reload(adapter)


def test_the_default_timeout_clears_one_real_outline_query():
    """180 seconds killed every live run before the first phase finished (#301)."""
    assert adapter.QUERY_TIMEOUT_SECONDS >= 900


def test_a_missing_cost_field_is_not_a_free_turn(fake_sdk, work):
    fake_sdk([FakeResultMessage(result="x")])
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert result.cost_reported is False
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.0)])
    reported = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert reported.cost_reported is True
    assert reported.usd == 0.0
