"""The backend. It must never claim a write it did not make, and it must
report what a turn cost."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import adapter
import contract as contract_mod
import harness
import implementer
import pytest
import roles
import steps
from conftest import FakeResultMessage, FakeTaskNotification, FakeTaskStarted
from contract import CoverageReport, RunResult, SuiteReport

# -- a full ticket repo, for the #567 end-to-end test below ------------------
#
# Copied from tests/test_implementer.py rather than imported, the same way
# tests/test_parity.py copies its own fixture helpers: a worker who edits one
# file should see a failure here, by name, rather than a silent import.

TICKET_TASKFILE = """\
version: '3'
tasks:
  setup:
    cmds: [echo setup]
  test:
    cmds: [echo test]
  e2e:
    cmds: [echo e2e]
  lint:
    cmds: [echo lint]
  format-check:
    cmds: [echo format-check]
"""

TICKET_LOOP_YML = """\
version: 1
roles:
  planner:
    write_allow: ["steps.jsonl"]
  test_implementer:
    write_allow: ["tests/**"]
    write_deny: ["app/**"]
  code_implementer:
    write_allow: ["app/**"]
    write_deny: ["tests/**"]
  judge:
    write_allow: []
rubric:
  coverage_floor: 80
  require_red: true
tickets:
  source: local
  path: tickets
budget:
  iterations: 3
  usd: 2.00
"""

TICKET_BODY = """\
---
id: T001
title: greet
state: ready
---

# T001 greet

## Acceptance criteria

- (AC-1) greet() returns hello
"""


def _ticket_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "Taskfile.yml").write_text(TICKET_TASKFILE, encoding="utf-8")
    (path / ".loop.yml").write_text(TICKET_LOOP_YML, encoding="utf-8")
    (path / "tickets").mkdir()
    (path / "app").mkdir()
    (path / "tests").mkdir()
    (path / "tickets" / "T001.md").write_text(TICKET_BODY, encoding="utf-8")
    (path / "app" / "health.py").write_text("ok = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)
    return path


def _suite(*, passed=(), failed=()) -> SuiteReport:
    passed_ids, failed_ids = set(passed), set(failed)
    return SuiteReport(
        exists=True,
        tests=len(passed_ids) + len(failed_ids),
        failures=len(failed_ids),
        passed_ids=passed_ids,
        failed_ids=failed_ids,
    )


def _run(*, passed=(), failed=()) -> RunResult:
    return RunResult(
        task="test",
        exit_code=0 if not failed else 1,
        output="",
        junit=_suite(passed=passed, failed=failed),
        coverage=CoverageReport(exists=True, line_rate=100.0),
    )


def _patch_runs(monkeypatch, runs: list[RunResult]):
    leftover = list(runs)

    def fake_run(self, task: str, timeout: int = 900) -> RunResult:
        if task != "test":
            return RunResult(
                task=task,
                exit_code=0,
                output="",
                junit=_suite(passed=("e2e::ok",)) if task == "e2e" else SuiteReport(),
                coverage=CoverageReport(),
            )
        if leftover:
            return leftover.pop(0)
        return _run(passed=("tests/test_health.py::test_health",))

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


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


def test_the_sdk_exception_after_a_terminal_result_keeps_the_stop_reason(fake_sdk, target):
    module = fake_sdk()

    async def query(*, prompt, options):
        yield FakeResultMessage(result="", is_error=True, subtype="error_max_turns")
        raise module.ResultError("CLI exits non-zero after the terminal result")

    module.query = query
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])

    assert not result.ok
    assert result.stop_reason == "max turns"
    assert "backend failed" not in result.output


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


def test_it_does_not_join_streamed_tool_events(fake_sdk, target):
    """Joining every event is how Grep output became a candidate."""

    class StreamEvent:
        def __str__(self):
            return "30\tGrep dump of app/models.py"

    fake_sdk([StreamEvent(), FakeResultMessage(result="the answer")])
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])
    assert result.output == "the answer"
    assert "Grep dump" not in result.output
    assert "StreamEvent" in result.raw_output


def test_a_hung_query_times_out(fake_sdk, target, monkeypatch):
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached")

    module.query = query
    result = adapter.AgentSdkBackend(object(), timeout_seconds=0.05).run(
        repo=target, prompt="p", allow=[]
    )
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert "timed out" in result.output
    assert "never reached" not in result.output


def test_a_bad_timeout_env_var_falls_back_to_the_default(monkeypatch, capsys):
    """#553. A non-integer (or non-positive) value must not raise at import
    and take the whole module down with it. Covers `_timeout_env`'s own
    branches (unset, non-integer); the real variable is driven through a
    reload by the test below."""
    assert adapter._timeout_env("SOL2_QUERY_TIMEOUT_SECONDS_UNSET", 900) == 900
    monkeypatch.setenv("SOL2_QUERY_TIMEOUT_SECONDS_TEST", "abc")
    assert adapter._timeout_env("SOL2_QUERY_TIMEOUT_SECONDS_TEST", 900) == 900
    assert "abc" in capsys.readouterr().err


def test_the_real_timeout_variable_set_to_abc_leaves_the_default_and_imports(
    monkeypatch, capsys
):
    """#553, judge of PR #556. The test above proves `_timeout_env`'s
    branches but never touches `SOL2_QUERY_TIMEOUT_SECONDS` itself, so
    reverting `QUERY_TIMEOUT_SECONDS` to the unguarded
    `int(os.environ.get(...))` left it green while
    `SOL2_QUERY_TIMEOUT_SECONDS=abc python -c "import adapter"` still
    raised. Drive the real variable through a reload instead."""
    import importlib  # noqa: PLC0415

    monkeypatch.setenv("SOL2_QUERY_TIMEOUT_SECONDS", "abc")
    reloaded = importlib.reload(adapter)
    try:
        assert reloaded.QUERY_TIMEOUT_SECONDS == 900
        assert "abc" in capsys.readouterr().err
    finally:
        monkeypatch.delenv("SOL2_QUERY_TIMEOUT_SECONDS")
        importlib.reload(adapter)


# -- #539: a failure path never claims a silent 0.0 -------------------------


def test_a_timed_out_query_reports_elapsed_and_the_event_count(fake_sdk, target):
    """#578. Since #568, a `ResultMessage` (even one that used to be tagged
    this port's own test-only "partial" subtype) is a terminal record and
    ends the turn immediately, so it can no longer stand in for progress
    that arrives before a genuine hang. A non-terminal stream event ahead
    of the hang still counts toward `events`, and the timeout diagnostics
    still name the elapsed time; the cost stays unknown because no
    `ResultMessage` ever answered (see the "no cost message" test below
    for that assertion in full)."""

    class StreamEvent:
        pass

    module = fake_sdk([])

    async def query(*, prompt, options):
        yield StreamEvent()
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached", total_cost_usd=0.99)

    module.query = query
    result = adapter.AgentSdkBackend(object(), timeout_seconds=0.05).run(
        repo=target, prompt="p", allow=[]
    )
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert result.usd is None
    assert "elapsed=" in result.output
    assert "events=1" in result.output
    assert "usd=unknown" in result.output


def test_a_timed_out_query_with_no_cost_message_reports_usd_as_none(fake_sdk, target):
    module = fake_sdk([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached")

    module.query = query
    result = adapter.AgentSdkBackend(object(), timeout_seconds=0.05).run(
        repo=target, prompt="p", allow=[]
    )
    assert result.usd is None
    assert "usd=unknown" in result.output


def test_a_message_with_no_cost_field_reports_usd_as_none_not_zero(fake_sdk, target):
    """`total_cost_usd=None` is "the SDK never told us", not "this was free"."""
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=None)])
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])
    assert result.usd is None


def test_a_later_zero_cost_message_does_not_erase_an_earlier_real_cost(fake_sdk, target):
    """#539, follow-up 6. `total_cost_usd` is cumulative; a stray 0.0 in a
    later message must not overwrite a real cost a message already reported.
    #578: a second `ResultMessage` is only reachable at all now while a
    delegated task is still in flight at the first one, so that mechanism
    is what puts two frames on the wire here."""
    fake_sdk(
        [
            FakeTaskStarted(),
            FakeResultMessage(result="progress", total_cost_usd=0.50),
            FakeTaskNotification(),
            FakeResultMessage(result="done", total_cost_usd=0.0),
        ]
    )
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])
    assert result.usd == 0.50


def test_a_backend_that_raises_after_spending_reports_the_spend(fake_sdk, target, monkeypatch):
    """A crash after the query answered must not erase what it already cost."""
    fake_sdk([FakeResultMessage(result="x", total_cost_usd=0.77)])
    calls = {"n": 0}
    real_changed_files = adapter._changed_files

    def flaky(repo):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_changed_files(repo)
        raise RuntimeError("boom after spend")

    monkeypatch.setattr(adapter, "_changed_files", flaky)
    result = adapter.AgentSdkBackend(object()).run(repo=target, prompt="p", allow=[])
    assert not result.ok
    assert result.usd == 0.77
    assert "boom after spend" in result.output


# -- A9 (#437 #422): the planner scope and the planner graph -----------------


def test_the_planner_scope_routes_to_the_planner_backend():
    """`steps.jsonl` is the planner's whole write scope. `_for` must route on
    it before the tests/ and app/ branches, and refuse a scope no branch
    names, the same as before this unit."""
    test_backend = adapter.AgentSdkBackend(object())
    code_backend = adapter.AgentSdkBackend(object())
    planner_backend = adapter.AgentSdkBackend(object())
    phase = adapter.AgentSdkPhaseBackend(
        test=test_backend, code=code_backend, planner=planner_backend
    )

    assert phase._for([steps.STEPS_FILE]) is planner_backend
    assert phase._for(["tests/**"]) is test_backend
    assert phase._for(["app/**"]) is code_backend
    with pytest.raises(ValueError, match="no Agent SDK backend"):
        phase._for(["reports/**"])


def test_an_unconfigured_planner_fails_closed():
    phase = adapter.AgentSdkPhaseBackend(
        test=adapter.AgentSdkBackend(object()), code=adapter.AgentSdkBackend(object())
    )
    with pytest.raises(ValueError, match="no Agent SDK planner backend"):
        phase.plan(repo=Path("."), prompt="plan it")


def test_plan_runs_the_planner_backend_with_its_own_scope(fake_sdk, target):
    """`plan()` is `run()` scoped to `steps.jsonl`, the same shape as `judge()`
    scoping to the judge backend."""
    module = fake_sdk([FakeResultMessage(result="wrote the plan")])
    phase = adapter.AgentSdkPhaseBackend(
        test=adapter.AgentSdkBackend(object()),
        code=adapter.AgentSdkBackend(object()),
        planner=adapter.AgentSdkBackend(object()),
    )

    result = phase.plan(repo=target, prompt="write steps.jsonl")

    assert result.ok
    assert result.output == "wrote the plan"
    assert module.last_prompt == "write steps.jsonl"


def test_planner_sdk_with_doer_sdk_invokes_the_planner_graph(fake_sdk, contract, repo):
    """A9 (#437 #422), test 2 of 5. `--planner sdk --doer sdk` must reach the
    planner subagent, not the test or code one. `harness.backend` builds all
    four graphs; `.plan()` must be the one that dispatches to the one named
    `implementer-planner`."""
    module = fake_sdk([FakeResultMessage(result='{"ok": true}')])

    backend = harness.backend(contract, "T001")
    result = backend.plan(repo=repo, prompt="write the plan")

    assert result.ok
    assert list(module.last_options.agents) == ["implementer-planner"]


# -- #567: the scope hook, not a fixture's project settings, is the judge ---


def test_a_test_implementer_write_lands_through_the_real_hook_and_red_ids_populate(
    tmp_path, fake_sdk, monkeypatch
):
    """#567. The northwind-field-crm fixture's own `.claude/settings.json`
    denies `Write(./tests/**)`, and that used to reach the test implementer
    through `setting_sources=["project"]` before the scope hook this port
    writes ever got a say. This drives the real `harness.backend` (real
    `options_for`, real scope hook per role) end to end through
    `implementer.run`: the only thing a live model call would add is the CLI
    itself asking the hook before a `Write` lands, which this fake `query`
    does by calling the exact hook object `options_for` built. The write
    must land in the worktree and the red gate must see it in `red_ids`."""
    repo = _ticket_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )

    module = fake_sdk()

    async def query(*, prompt, options):
        agent = next(iter(options.agents))
        hook = options.hooks["PreToolUse"][0].hooks[0]
        if agent == "implementer-test-implementer":
            path = f"{options.cwd}/tests/test_greet.py"
            decision = await hook(
                {"tool_name": "Write", "tool_input": {"file_path": path}, "agent_type": agent},
                "id",
                None,
            )
            assert decision == {}, f"the test implementer's own write was denied: {decision}"
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("def test_ac1():\n    assert False\n", encoding="utf-8")
            yield FakeResultMessage(result="wrote the failing test", total_cost_usd=0.01)
        elif agent == "implementer-code-implementer":
            path = f"{options.cwd}/app/greet.py"
            decision = await hook(
                {"tool_name": "Write", "tool_input": {"file_path": path}, "agent_type": agent},
                "id",
                None,
            )
            assert decision == {}
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
            yield FakeResultMessage(result="wrote greet()", total_cost_usd=0.01)
        else:
            yield FakeResultMessage(result='{"done": true, "why": "looks right"}')

    module.query = query
    contract_obj = contract_mod.Contract(repo)
    backend = harness.backend(contract_obj, "T001")

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    written = Path(trace["repo"])
    assert (written / "tests" / "test_greet.py").exists()
    assert trace["red_ids"], "the test implementer's write never reached the red gate"
    assert trace["gate"] == "pass", trace.get("reason")


def test_the_code_implementer_hook_still_refuses_a_write_under_tests(fake_sdk, contract, repo):
    """#567. Project settings are gone for both write roles now (see
    tests/test_roles.py), so the code implementer's own scope hook, built by
    the same `options_for` that just refused it project settings, is the
    only thing standing between it and `tests/**`. It still says no."""
    fake_sdk()
    options = roles.options_for(contract, role_names=frozenset({"code_implementer"}))
    assert options.setting_sources == []
    hook = options.hooks["PreToolUse"][0].hooks[0]

    decision = asyncio.run(
        hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": f"{repo}/tests/test_x.py"},
                "agent_type": "implementer-code-implementer",
            },
            "id",
            None,
        )
    )
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


# -- #568: `collect()` returns on the terminal ResultMessage -----------------


def test_a_budget_stop_returns_immediately_instead_of_waiting_for_the_stream_to_close(
    fake_sdk, target
):
    """#568. Both terminal `ResultMessage`s in the round-4 raw logs read
    `subtype='error_max_budget_usd'` and the query ended in under a minute,
    but the stream itself sat open after that, quiet, until the 900 second
    ceiling: `collect()` had no break on the terminal result and kept asking
    the generator for more. Once a `ResultMessage` names a controlled stop,
    `collect()` must return right there, well inside this test's own
    generous timeout, not because that timeout finally fired."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeResultMessage(
            result="", total_cost_usd=0.3914, subtype="error_max_budget_usd"
        )
        await adapter.asyncio.sleep(30)  # the stream that never closes
        yield FakeResultMessage(result="never reached", total_cost_usd=99.0)

    module.query = query
    started = adapter.time.monotonic()
    result = adapter.AgentSdkBackend(object(), timeout_seconds=5).run(
        repo=target, prompt="p", allow=[]
    )
    elapsed = adapter.time.monotonic() - started

    assert result.stop_reason == "cost budget spent"
    assert result.usd == 0.3914
    assert not result.ok
    assert elapsed < 2, f"collect() waited {elapsed:.2f}s past the terminal result"


def test_a_successful_result_also_returns_immediately_instead_of_waiting_for_silence(
    fake_sdk, target
):
    """#568 follow-up (judge of PR #570, item 1). The first fix broke only
    on a controlled stop (`if stop:`), so a successful terminal
    `ResultMessage` followed by the same quiet stream still ran to the
    ceiling and reported "query timeout" instead of the answer it already
    had. Every `ResultMessage` the real SDK yields is terminal, success
    included; `collect()` must return on this one too."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeResultMessage(result='{"done": true}', total_cost_usd=0.25)
        await adapter.asyncio.sleep(30)  # the stream that never closes
        yield FakeResultMessage(result="never reached", total_cost_usd=99.0)

    module.query = query
    started = adapter.time.monotonic()
    result = adapter.AgentSdkBackend(object(), timeout_seconds=5).run(
        repo=target, prompt="p", allow=[]
    )
    elapsed = adapter.time.monotonic() - started

    assert result.ok
    assert result.output == '{"done": true}'
    assert result.usd == 0.25
    assert result.stop_reason is None
    assert elapsed < 2, f"collect() waited {elapsed:.2f}s past the terminal result"


def test_a_result_with_a_task_in_flight_does_not_end_the_run(fake_sdk, target):
    """#578. A `ResultMessage` that arrives while a delegated `Task` this
    run spawned is still going only closes that turn, not the run: the
    installed SDK's own `Query._read_messages` (upstream #1088) holds the
    close back the same way, and a later result frame arrives once the
    task drains. The first result here must not be mistaken for the
    answer, and the stream must not be cut off before the second, real
    terminal result arrives -- nor should `collect()` wait out the
    ceiling once that second result is in hand."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeTaskStarted()
        yield FakeResultMessage(result="turn one", total_cost_usd=0.10)
        yield FakeTaskNotification()
        yield FakeResultMessage(result="the real answer", total_cost_usd=0.20)
        await adapter.asyncio.sleep(30)  # the stream that never closes

    module.query = query
    started = adapter.time.monotonic()
    result = adapter.AgentSdkBackend(object(), timeout_seconds=5).run(
        repo=target, prompt="p", allow=[]
    )
    elapsed = adapter.time.monotonic() - started

    assert result.ok
    assert result.output == "the real answer"
    assert result.usd == 0.20
    assert elapsed < 2, f"collect() waited {elapsed:.2f}s past the terminal result"


def test_a_stream_with_no_terminal_result_still_times_out(fake_sdk, target):
    """#568, the other half. A query that never produces a `ResultMessage` at
    all (a hung tool call, a dropped connection) must still hit the outer
    ceiling and report a timeout, not hang forever waiting for a terminal
    record that is never coming."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield "still working"
        await adapter.asyncio.sleep(30)
        yield "unreachable"

    module.query = query
    result = adapter.AgentSdkBackend(object(), timeout_seconds=0.05).run(
        repo=target, prompt="p", allow=[]
    )
    assert result.stop_reason == "query timeout"
    assert not result.ok


# -- #543: the live doer works where implementer.run reads its writes back --


def test_a_live_backends_write_lands_in_the_worktree_not_the_clone(tmp_path, fake_sdk):
    """#543. `implementer.run` executes every phase in `<repo>.worktrees/<ticket>`.
    `harness.backend` used to build `ClaudeAgentOptions(cwd=...)` and the
    scope hook rooted at the `--repo` clone instead, so a live doer's writes
    landed where the red gate never looks, and the run reported "wrote
    nothing" for work it actually did."""
    clone_root = tmp_path / "clone"
    clone_root.mkdir()
    clone = git_repo(clone_root)
    worktree = implementer._worktree_path(clone, "T001")
    worktree.mkdir(parents=True)
    git_repo(worktree)  # a plain repo stands in for what `_worktree` itself
    # would have checked out from the clone's HEAD; this test is only about
    # where a write lands, not about worktree creation, which is tested
    # elsewhere.

    module = fake_sdk()

    async def query(*, prompt, options):
        target = Path(options.cwd) / "tests" / "test_due.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def test_due(): assert False\n", encoding="utf-8")
        yield FakeResultMessage(result="wrote a test", total_cost_usd=0.01)

    module.query = query
    contract_obj = contract_mod.Contract(clone)
    backend_obj = harness.backend(contract_obj, "T001")

    result = backend_obj.run(repo=worktree, prompt="write a test", allow=["tests/**"])

    assert result.wrote == ["tests/test_due.py"]
    assert (worktree / "tests" / "test_due.py").exists()
    assert not (clone / "tests" / "test_due.py").exists()


def test_no_backend_from_harness_backend_roots_at_the_clone(tmp_path, fake_sdk):
    """#549. Every write tool a live doer receives (`ClaudeAgentOptions.cwd`
    plus the scope hook it roots `scope_hook` at) must derive from
    `implementer._worktree_path`, never `contract.repo`, for every phase
    `harness.backend` builds, not just the test implementer #543 follow-up
    already pinned."""
    fake_sdk()  # `options_for` imports claude_agent_sdk unconditionally
    clone_root = tmp_path / "clone"
    clone_root.mkdir()
    clone = git_repo(clone_root)
    worktree = implementer._worktree_path(clone, "T001")

    contract_obj = contract_mod.Contract(clone)
    backend_obj = harness.backend(contract_obj, "T001")

    checked = 0
    for name in ("test", "code", "judge_backend", "planner"):
        sub = getattr(backend_obj, name)
        assert sub.options.cwd == str(worktree), f"{name} did not root at the worktree"
        assert sub.options.cwd != str(clone.resolve()), f"{name} rooted at contract.repo"
        checked += 1

    assert checked == 4
