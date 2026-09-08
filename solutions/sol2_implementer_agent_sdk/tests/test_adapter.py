"""The backend. It must never claim a write it did not make, and it must
report what a turn cost."""

from __future__ import annotations

import subprocess
from pathlib import Path

import adapter
import contract as contract_mod
import harness
import implementer
import pytest
import steps
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


# -- #539: a failure path never claims a silent 0.0 -------------------------


def test_a_timed_out_query_reports_elapsed_events_and_spend_so_far(fake_sdk, target):
    """A query that already told us it had spent something before it hung
    must not lose that number just because the ceiling then cut it off."""
    module = fake_sdk([])

    async def query(*, prompt, options):
        yield FakeResultMessage(result="progress", total_cost_usd=0.33, subtype="partial")
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="never reached", total_cost_usd=0.99)

    module.query = query
    result = adapter.AgentSdkBackend(object(), timeout_seconds=0.05).run(
        repo=target, prompt="p", allow=[]
    )
    assert not result.ok
    assert result.stop_reason == "query timeout"
    assert result.usd == 0.33
    assert "elapsed=" in result.output
    assert "events=1" in result.output
    assert "usd=0.3300" in result.output


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
    later message must not overwrite a real cost a message already reported."""
    fake_sdk(
        [
            FakeResultMessage(result="progress", total_cost_usd=0.50, subtype="partial"),
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
