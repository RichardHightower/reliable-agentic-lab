"""The live T001 path wraps a local Backend. No SDK. No sibling folder."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import contract as contract_mod
import e2e_t001
import implementer
from contract import CoverageReport, RunResult, SuiteReport

# Copied from tests/test_implementer.py, not imported, the same way
# tests/test_parity.py copies its own fixtures. Block style, matching
# conftest.py's own fixture (#496).
TASKFILE = """\
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

LOOP_YML = """\
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

TICKET = """\
---
id: T001
title: greet
state: ready
---

# T001 greet

## Acceptance criteria

- (AC-1) greet() returns hello
"""


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (path / "tickets").mkdir()
    (path / "app").mkdir()
    (path / "tests").mkdir()
    (path / "tickets" / "T001.md").write_text(TICKET, encoding="utf-8")
    (path / "app" / "health.py").write_text("ok = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)
    return path


def _suite(*, passed=(), failed=()) -> SuiteReport:
    passed_ids = set(passed)
    failed_ids = set(failed)
    return SuiteReport(
        exists=True,
        tests=len(passed_ids) + len(failed_ids),
        failures=len(failed_ids),
        passed_ids=passed_ids,
        failed_ids=failed_ids,
    )


def _run(*, passed=(), failed=(), coverage=True, ok=True) -> RunResult:
    return RunResult(
        task="test",
        exit_code=0 if ok and not failed else 1,
        output="",
        junit=_suite(passed=passed, failed=failed),
        coverage=CoverageReport(exists=coverage, line_rate=100.0 if coverage else 0.0),
    )


def _patch_runs(monkeypatch, runs: list[RunResult]):
    """No `task` binary needed. `Contract.run` never shells out in this test."""
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
        return _run(passed=("tests/test_health.py::test_health",), failed=())

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


class FakeAgentSdkBackend:
    def __init__(self):
        self.prompt = ""
        self.calls = 0

    def run(self, *, repo: Path, prompt: str, allow: list[str]):
        self.prompt = prompt
        self.calls += 1
        return SimpleNamespace(
            wrote=["tests/test_due_date.py"],
            output="test created",
            usd=0.12,
            ok=True,
            stop_reason=None,
        )


def test_the_e2e_wrapper_is_a_doers_backend(tmp_path):
    """The driver must not reinterpret the SDK object as a CLI command."""
    delegate = FakeAgentSdkBackend()
    wrapper = e2e_t001.AgentSdkE2EBackend(delegate)

    assert e2e_t001.doers.build(wrapper) is wrapper

    result = wrapper.run(
        repo=tmp_path,
        prompt="Implement the ready ticket.",
        allow=["tests/**"],
    )

    assert result.wrote == ["tests/test_due_date.py"]
    assert result.usd == 0.12
    assert delegate.prompt.startswith("Delegate only to implementer-test-implementer.")
    assert wrapper.calls[0].phase == "test"


def test_the_e2e_wrapper_selects_the_backend_for_each_phase(tmp_path):
    tester = FakeAgentSdkBackend()
    coder = FakeAgentSdkBackend()
    inner = e2e_t001.adapter.AgentSdkPhaseBackend(test=tester, code=coder)
    wrapper = e2e_t001.AgentSdkE2EBackend(inner)

    wrapper.run(repo=tmp_path, prompt="test", allow=["tests/**"])
    wrapper.run(repo=tmp_path, prompt="code", allow=["app/**"])

    assert tester.calls == 1
    assert coder.calls == 1


def test_the_live_turn_ceiling_is_high_enough_for_a_green_run():
    assert e2e_t001.E2E_MAX_TURNS >= 12


def test_the_dollar_cap_is_tunable_by_environment_variable():
    """#444/#539. The cap a status note reports must be a cap an operator
    actually chose. Read at import, the same as adapter.QUERY_TIMEOUT_SECONDS,
    so this is a subprocess check, not a monkeypatch of the module attribute."""
    env = {**os.environ, "SOL2_E2E_MAX_USD": "4"}
    out = subprocess.run(
        [sys.executable, "-c", "import e2e_t001; print(e2e_t001.MAX_TOTAL_USD)"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    assert out.stdout.strip() == "4.0"


def test_a_controlled_sdk_turn_ceiling_is_not_a_failed_query(tmp_path):
    delegate = FakeAgentSdkBackend()
    original_run = delegate.run

    def stopped(**kwargs):
        result = original_run(**kwargs)
        result.ok = False
        result.stop_reason = "max turns"
        return result

    delegate.run = stopped
    wrapper = e2e_t001.AgentSdkE2EBackend(delegate)

    wrapper.run(repo=tmp_path, prompt="test", allow=["tests/**"])

    assert not wrapper.query_failed


def test_a_controlled_sdk_budget_stop_is_not_a_failed_query(tmp_path):
    """#568 follow-up (judge of PR #570, item 2). Removing "cost budget
    spent" from `CONTROLLED_STOPS` left every test in this file green; this
    is the test whose absence that was. Mirrors
    `test_a_controlled_sdk_turn_ceiling_is_not_a_failed_query` above, the
    same shape for the other named ceiling."""
    delegate = FakeAgentSdkBackend()
    original_run = delegate.run

    def stopped(**kwargs):
        result = original_run(**kwargs)
        result.ok = False
        result.stop_reason = "cost budget spent"
        return result

    delegate.run = stopped
    wrapper = e2e_t001.AgentSdkE2EBackend(delegate)

    wrapper.run(repo=tmp_path, prompt="test", allow=["tests/**"])

    assert not wrapper.query_failed


def test_the_e2e_command_refuses_before_querying_without_a_credential(tmp_path, monkeypatch, capsys):
    """A missing key is a preflight failure, not a live Agent SDK attempt."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)

    assert e2e_t001.main(["--repo", str(tmp_path)]) == 2
    assert "needs ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_the_e2e_loader_checks_local_then_parent_then_checkout_root(monkeypatch, tmp_path):
    """The direct Python command follows the documented dotenv search order."""
    folder = tmp_path / "solutions" / "sol2_implementer_agent_sdk"
    folder.mkdir(parents=True)
    (folder.parent.parent / ".env").write_text("ANTHROPIC_API_KEY=root\n", encoding="utf-8")
    (folder.parent / ".env").write_text("ANTHROPIC_API_KEY=parent\n", encoding="utf-8")
    (folder / ".env").write_text("ANTHROPIC_API_KEY=local\n", encoding="utf-8")
    monkeypatch.setattr(e2e_t001, "FOLDER", folder)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    e2e_t001._load_operator_env()

    assert e2e_t001.os.environ["ANTHROPIC_API_KEY"] == "local"


def test_the_e2e_summary_lands_in_the_worktree(tmp_path, monkeypatch):
    """#506. `implementer.run` does its work in `<repo>.worktrees/<ticket>`,
    never against the clone `--repo` names, and writes `.harness/` there.
    `_write_extras` used to receive the clone path anyway, so
    `last-sdk-e2e.md` landed beside a tree the run never touched, naming
    paths that resolved against the wrong directory. Offline: `Contract.run`
    is patched, so no `task` binary and no live Agent SDK credential are
    needed."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)
    monkeypatch.setattr(
        e2e_t001,
        "_build_backend",
        lambda repo, budget, ticket_id: (e2e_t001.AgentSdkE2EBackend(FakeAgentSdkBackend()), []),
    )

    exit_code = e2e_t001.main(["--repo", str(repo), "--ticket", "T001", "--budget", "1"])

    assert exit_code == 1  # escalate: no new red observed at budget 1

    worktree = repo.parent / f"{repo.name}.worktrees" / "T001"
    assert worktree.is_dir()
    summary = worktree / ".harness" / "last-sdk-e2e.md"
    assert summary.is_file()
    assert "gate: escalate" in summary.read_text(encoding="utf-8")
    assert (worktree / ".harness" / "last-sdk-e2e-diff.txt").is_file()

    # The regression this test pins: the summary must not land next to the
    # clone the run never touched.
    assert not (repo / ".harness" / "last-sdk-e2e.md").exists()


def test_the_query_failed_message_names_the_absolute_worktree_path(tmp_path, monkeypatch, capsys):
    """#506 follow-up, judge of PR #527, item 4. The "see .harness/last-sdk-
    e2e.md" message printed on a failed query used to be a bare relative
    path, which reads as living next to wherever this command was invoked
    from, not the worktree `_write_extras` actually wrote the summary to."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)

    class FailingBackend:
        def run(self, *, repo: Path, prompt: str, allow: list[str]):
            return SimpleNamespace(wrote=[], output="boom", usd=0.0, ok=False, stop_reason="crashed")

    monkeypatch.setattr(
        e2e_t001,
        "_build_backend",
        lambda repo, budget, ticket_id: (e2e_t001.AgentSdkE2EBackend(FailingBackend()), []),
    )

    exit_code = e2e_t001.main(["--repo", str(repo), "--ticket", "T001", "--budget", "1"])

    assert exit_code == 2
    worktree = repo.parent / f"{repo.name}.worktrees" / "T001"
    err = capsys.readouterr().err
    assert str(worktree / ".harness" / "last-sdk-e2e.md") in err
    assert "see .harness/last-sdk-e2e.md\n" not in err  # the old bare relative path


# -- #539: a failure path never claims a silent 0.0, the cap is the one --
# -- applied, and the raw event log a failed call collected survives -----


class TimedOutBackend:
    """A phase backend whose query timed out: no cost, a raw event log."""

    def run(self, *, repo: Path, prompt: str, allow: list[str]):
        return SimpleNamespace(
            wrote=[],
            output="agent sdk query timed out after 900 seconds (elapsed=900s, events=3)",
            usd=None,
            ok=False,
            stop_reason="query timeout",
            structured=None,
            raw_output="## AssistantMessage\n\nsome tool call\n",
        )


def test_a_timed_out_call_reports_usd_as_none_not_zero(tmp_path):
    wrapper = e2e_t001.AgentSdkE2EBackend(TimedOutBackend())

    result = wrapper.run(repo=tmp_path, prompt="p", allow=["tests/**"])

    assert result.usd is None
    assert wrapper.calls[0].usd is None
    assert wrapper.spent_usd == 0.0
    assert wrapper.query_failed
    # #546. The count that says `spent_usd` is a floor, not a total.
    assert wrapper.unknown_spend_turns == 1


def test_a_budget_exhausted_call_reports_a_known_zero_not_unknown(tmp_path):
    """#539, follow-up 4. This call never reaches the backend, so its cost
    is known to be exactly zero, not unreported. Reporting a known zero as
    `usd=None` would be the mirror of the defect this ticket exists to fix."""
    wrapper = e2e_t001.AgentSdkE2EBackend(TimedOutBackend(), max_total_usd=0.0)

    result = wrapper.run(repo=tmp_path, prompt="p", allow=["tests/**"])

    assert result.usd == 0.0
    assert wrapper.calls[0].usd == 0.0
    assert wrapper.calls[0].stop_reason == "cost budget spent"


def test_a_negative_reported_cost_does_not_walk_spent_usd_backwards(tmp_path):
    """#539, follow-up 5. The SDK has never emitted a negative cost, but the
    old `float(... or 0.0)` line carried a `max(usd, 0.0)` clamp that the
    `None`-preserving rewrite dropped."""

    class NegativeCostBackend:
        def run(self, *, repo: Path, prompt: str, allow: list[str]):
            return SimpleNamespace(
                wrote=[], output="x", usd=-1.0, ok=True, stop_reason=None, raw_output=""
            )

    wrapper = e2e_t001.AgentSdkE2EBackend(NegativeCostBackend())

    wrapper.run(repo=tmp_path, prompt="p", allow=["tests/**"])

    assert wrapper.spent_usd == 0.0


def test_the_summary_reports_the_cap_it_applied_and_keeps_the_raw_event_log(
    tmp_path, monkeypatch
):
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)
    monkeypatch.setattr(
        e2e_t001,
        "_build_backend",
        lambda repo, budget, ticket_id: (
            e2e_t001.AgentSdkE2EBackend(TimedOutBackend(), max_total_usd=2.0),
            [],
        ),
    )

    e2e_t001.main(["--repo", str(repo), "--ticket", "T001", "--budget", "1"])

    worktree = repo.parent / f"{repo.name}.worktrees" / "T001"
    summary = (worktree / ".harness" / "last-sdk-e2e.md").read_text(encoding="utf-8")
    assert "cap_usd: 2.00" in summary
    assert "usd=unknown" in summary
    # #546. `TimedOutBackend` answers `usd=None` on its one call, so the
    # summary has to say `spent_usd` is a floor, not a total.
    assert "unknown_spend_turns: 1" in summary
    raw = worktree / ".harness" / "last-sdk-e2e-raw-0-test.txt"
    assert raw.is_file()
    assert "some tool call" in raw.read_text(encoding="utf-8")
    assert "raw: .harness/last-sdk-e2e-raw-0-test.txt" in summary


def test_redact_widens_to_tilde_home_ghp_tokens_and_bearer_headers():
    """#545 follow-up. The judge's own probe table showed a `~/`-shorthand
    home path, a `ghp_...` token, and a `Bearer ...` header all passing
    through `_redact` unchanged. Close the gap it measured."""
    text = (
        "cwd: ~/work/northwind-field-crm\n"
        "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789\n"
        "Authorization: Bearer abc.def.ghi\n"
    )

    redacted = e2e_t001._redact(text)

    assert "~/work" not in redacted
    assert "<HOME>" in redacted
    assert "ghp_" not in redacted
    assert "<REDACTED-KEY>" in redacted
    assert "Bearer abc.def.ghi" not in redacted
    assert "Bearer <REDACTED-TOKEN>" in redacted


def test_redact_strips_a_slugified_home_path_with_no_slashes():
    """#444 step 2 finding. A live run's own tooling (Claude Code's own
    transcript directory, a scratchpad tmp path) names the home directory
    with `-` in place of `/`, e.g. `-Users-jdoe-work-crm`. The literal
    `str(Path.home())` replace never matches that string; only the bare
    account name is common to every encoding of the same path."""
    name = e2e_t001.Path.home().name
    text = f"output_file: /private/tmp/claude-501/-Users-{name}-clients-crm/tasks/x.output\n"

    redacted = e2e_t001._redact(text)

    assert name not in redacted
    assert "<HOME>" in redacted


def test_the_raw_log_survives_cleanup_via_raw_log_dir_with_secrets_stripped(
    tmp_path, monkeypatch
):
    """#543. The worktree's own copy of the raw event log is cleaned up
    between runs by hand; a status note that only points there stops
    resolving the moment that happens. `--raw-log-dir` copies it somewhere
    durable, with the operator's home directory and anything key-shaped
    stripped first."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)

    class LeakyBackend:
        def run(self, *, repo, prompt, allow):
            return SimpleNamespace(
                wrote=[],
                output="agent sdk query timed out after 900 seconds",
                usd=None,
                ok=False,
                stop_reason="query timeout",
                structured=None,
                raw_output=(
                    f"cwd: {Path.home()}/work/northwind-field-crm\n"
                    "key: sk-ant-abc123DEF456\n"
                ),
            )

    monkeypatch.setattr(
        e2e_t001,
        "_build_backend",
        lambda repo, budget, ticket_id: (e2e_t001.AgentSdkE2EBackend(LeakyBackend()), []),
    )

    raw_log_dir = tmp_path / "docs-status"
    e2e_t001.main(
        [
            "--repo", str(repo), "--ticket", "T001", "--budget", "1",
            "--raw-log-dir", str(raw_log_dir),
        ]
    )

    copied = raw_log_dir / "last-sdk-e2e-raw-0-test.txt"
    assert copied.is_file()
    text = copied.read_text(encoding="utf-8")
    assert str(Path.home()) not in text
    assert "<HOME>" in text
    assert "sk-ant-" not in text
    assert "<REDACTED-KEY>" in text

    # The worktree's own copy stays exactly as reported; only the durable
    # copy is redacted.
    worktree_raw = (
        repo.parent / f"{repo.name}.worktrees" / "T001" / ".harness"
        / "last-sdk-e2e-raw-0-test.txt"
    )
    assert str(Path.home()) in worktree_raw.read_text(encoding="utf-8")
