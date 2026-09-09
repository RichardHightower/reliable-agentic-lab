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


def test_a_bad_timeout_env_var_falls_back_to_the_default(monkeypatch, capsys):
    """#553. A non-integer (or non-positive) value must not raise at import
    and take the whole module down with it. Covers `_timeout_env`'s own
    branches (unset, non-integer); the real variable is driven through a
    reload by the test below."""
    assert adapter._timeout_env("SOL3_QUERY_TIMEOUT_SECONDS_UNSET", 900) == 900
    monkeypatch.setenv("SOL3_QUERY_TIMEOUT_SECONDS_TEST", "abc")
    assert adapter._timeout_env("SOL3_QUERY_TIMEOUT_SECONDS_TEST", 900) == 900
    assert "abc" in capsys.readouterr().err


def test_the_real_timeout_variable_set_to_abc_leaves_the_default_and_imports(
    monkeypatch, capsys
):
    """#553, judge of PR #556. The test above proves `_timeout_env`'s
    branches but never touches `SOL3_QUERY_TIMEOUT_SECONDS` itself, so
    reverting `QUERY_TIMEOUT_SECONDS` to the unguarded
    `int(os.environ.get(...))` left it green while
    `SOL3_QUERY_TIMEOUT_SECONDS=abc python -c "import adapter"` still
    raised. Drive the real variable through a reload instead."""
    import importlib  # noqa: PLC0415

    monkeypatch.setenv("SOL3_QUERY_TIMEOUT_SECONDS", "abc")
    reloaded = importlib.reload(adapter)
    try:
        assert reloaded.QUERY_TIMEOUT_SECONDS == 900
        assert "abc" in capsys.readouterr().err
    finally:
        monkeypatch.delenv("SOL3_QUERY_TIMEOUT_SECONDS")
        importlib.reload(adapter)


def test_a_missing_cost_field_is_not_a_free_turn(fake_sdk, work):
    fake_sdk([FakeResultMessage(result="x")])
    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert result.cost_reported is False
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.0)])
    reported = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert reported.cost_reported is True
    assert reported.usd == 0.0


# -- a transient provider error at the model-call boundary (#409) -----------


def test_a_transient_connection_error_twice_then_an_answer_completes_the_turn(
    fake_sdk, work, monkeypatch
):
    """A dropped CLI connection twice, then a normal reply. Both retries are
    logged and the turn carries their count."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise module.CLIConnectionError("dropped")
        yield FakeResultMessage(result="the answer", total_cost_usd=0.10)

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert result.ok
    assert result.output == "the answer"
    assert result.retries == 2
    assert waits == [5.0, 15.0]
    assert calls["n"] == 3


def test_each_retry_is_logged_with_its_wait(fake_sdk, work, monkeypatch, capsys):
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise module.CLIConnectionError("dropped")
        yield FakeResultMessage(result="ok")

    module.query = query
    monkeypatch.setattr(adapter, "_sleep", lambda seconds: None)

    adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[], role="writer")
    err = capsys.readouterr().err
    assert "role=writer" in err
    assert "retry 1/3" in err and "after 5s" in err
    assert "retry 2/3" in err and "after 15s" in err


def test_the_backoff_sequence_is_five_fifteen_forty_five(fake_sdk, work, monkeypatch):
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise module.CLIConnectionError("dropped")
        yield FakeResultMessage(result="ok", total_cost_usd=0.01)

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])
    assert result.ok
    assert result.retries == 3
    assert waits == [5.0, 15.0, 45.0]


def test_a_transient_error_four_times_ends_the_turn_gracefully(fake_sdk, work, monkeypatch):
    """A fourth failure is not retried a fourth time. It is not silently
    dropped either: it surfaces as this port's ordinary graceful turn
    failure (the same path any other backend exception already takes), which
    the caller retries at the unit level, not by resending the same request."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        raise module.CLIConnectionError("dropped")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert not result.ok
    assert "dropped" in result.output
    assert calls["n"] == 4, "every attempt must actually have been made"
    assert waits == [5.0, 15.0, 45.0]


def test_a_plain_bug_is_not_retried(fake_sdk, work, monkeypatch):
    """A non-transient exception must escape on the first raise, with no
    backoff sleep, the same way a gate failure would."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        raise ValueError("not a transient error")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert not result.ok
    assert calls["n"] == 1, "a non-transient error must not be retried"
    assert waits == []


def test_a_missing_cli_is_not_retried(fake_sdk, work, monkeypatch):
    """`CLINotFoundError` is a `CLIConnectionError`, but a permanent one: no
    installed binary is not fixed by resending the same request."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        raise module.CLINotFoundError("not found")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert not result.ok
    assert calls["n"] == 1
    assert waits == []


def test_a_max_turns_result_error_is_not_retried(fake_sdk, work, monkeypatch):
    """A `ResultError` for `error_max_turns` is a legitimate stop, not a
    dropped connection or a rate limit."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        raise module.ResultError("too many turns", terminal_reason="error_max_turns")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert not result.ok
    assert calls["n"] == 1
    assert waits == []


def test_an_api_error_result_is_retried(fake_sdk, work, monkeypatch):
    """A `ResultError` for `api_error` is the CLI reporting a live provider
    failure (overloaded, rate limited, or a dropped connection) mid-run."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] == 1:
            raise module.ResultError("rate limited", terminal_reason="api_error")
        yield FakeResultMessage(result="ok")

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert result.ok
    assert result.retries == 1
    assert waits == [5.0]


def test_a_401_is_not_retried(fake_sdk, work, monkeypatch):
    """#482: a `ResultError` with `terminal_reason == "api_error"` used to
    retry unconditionally, so a bad key burned the whole 65-second backoff
    and four attempts before it finally failed. `api_error_status` is
    already on the exception; a 4xx other than 408 or 429 is the provider
    rejecting the request, not a dropped connection, and escapes on the
    first raise with no sleep."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        raise module.ResultError(
            "invalid x-api-key (401)", terminal_reason="api_error", api_error_status=401
        )
        yield  # pragma: no cover - unreachable, keeps this an async generator

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert not result.ok
    assert calls["n"] == 1, "a permanent 4xx must not be retried"
    assert waits == []
    assert "401" in result.output


def test_a_429_is_still_retried(fake_sdk, work, monkeypatch):
    """429 is the one 4xx a retry can plausibly outlive."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] == 1:
            raise module.ResultError(
                "rate limited", terminal_reason="api_error", api_error_status=429
            )
        yield FakeResultMessage(result="ok")

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert result.ok
    assert result.retries == 1
    assert waits == [5.0]


def test_a_5xx_api_error_is_still_retried(fake_sdk, work, monkeypatch):
    """A 5xx is the provider's own failure, not the request's. Still
    transient."""
    module = fake_sdk([])
    calls = {"n": 0}

    async def query(*, prompt, options):
        calls["n"] += 1
        if calls["n"] == 1:
            raise module.ResultError(
                "overloaded", terminal_reason="api_error", api_error_status=529
            )
        yield FakeResultMessage(result="ok")

    module.query = query
    waits: list[float] = []
    monkeypatch.setattr(adapter, "_sleep", waits.append)

    result = adapter.AgentSdkBackend(object()).run(root=work, prompt="p", allow=[])

    assert result.ok
    assert result.retries == 1
    assert waits == [5.0]
