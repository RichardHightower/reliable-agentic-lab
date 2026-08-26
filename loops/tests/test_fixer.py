"""Checks for the Broken PR Fixer.

It runs unattended, so the exits matter more than the successes. Nobody is
watching to stop it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from loops import gates
from loops.contract import CoverageReport, RunResult, SuiteReport
from loops.fixer import checkout, failure_summary, run

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_crm() -> Path | None:
    for path in (
        Path(os.environ["LOOP_TEST_REPO"]) if os.environ.get("LOOP_TEST_REPO") else None,
        REPO_ROOT / "work" / "northwind-field-crm",
        REPO_ROOT.parent / "northwind-field-crm",
    ):
        if path and (path / ".loop.yml").is_file():
            return path
    return None


CRM = _find_crm()
has_crm = pytest.mark.skipif(CRM is None, reason="no target repo; run `task setup`")


@pytest.fixture()
def broken():
    def reset(branch: str):
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
        subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
        subprocess.run(["git", "checkout", "-q", branch], cwd=CRM, check=False)

    reset("broken-pr")
    yield CRM
    reset("main")


def test_the_failure_summary_names_the_failing_tests_and_the_error():
    result = RunResult(
        task="test",
        exit_code=1,
        output="E   AttributeError: 'NoneType' object has no attribute 'date'",
        junit=SuiteReport(exists=True, tests=3, failures=1, failed_ids={"tests.t::a"}),
        coverage=CoverageReport(),
    )
    summary = failure_summary(result)
    assert "1 failing" in summary
    assert "tests.t::a" in summary
    assert "AttributeError" in summary


@has_crm
def test_the_fixer_repairs_a_broken_branch(broken):
    trace = run(repo=broken, doer="reference", write_trace=False)
    assert trace["gate"] == gates.PASS, trace["reason"]
    assert trace["green"] is True


@has_crm
def test_the_fixer_gives_up_with_an_explanation_when_it_cannot_fix(broken):
    """Stopping is designed. Leaving no explanation is not."""
    trace = run(repo=broken, doer="none", write_trace=False)
    assert trace["gate"] == gates.ESCALATE
    assert trace["green"] is False
    assert "A human should take this one" in trace["comment"]
    assert trace["comment"].count("test_overdue_ignores_tasks_with_no_due_date") >= 1


@has_crm
def test_the_fixer_stops_on_a_repeat_failure_without_spending_the_budget(broken):
    trace = run(repo=broken, doer="none", budget=99, write_trace=False)
    assert trace["gate"] == gates.ESCALATE
    assert len(trace["attempts"]) <= 3, "it must not burn 99 attempts to learn nothing"


@has_crm
def test_a_fix_that_writes_outside_scope_is_refused(broken):
    """Reaching green by editing the test that failed is not a fix."""
    trace = run(repo=broken, doer="reference:known-good", write_trace=False)
    assert trace["gate"] == gates.PASS
    assert all(not path.startswith("tests/") for path in trace["changed"]), trace["changed"]


def test_checkout_fails_loudly_on_a_branch_that_does_not_exist(tmp_path):
    """A fixer that silently stays on the wrong branch reports a false pass."""
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit) as caught:
        checkout(tmp_path, "no-such-branch")
    assert "no-such-branch" in str(caught.value)


def test_a_suite_that_never_ran_is_not_a_test_failure(tmp_path, monkeypatch):
    """The bug this catches: two rounds of a missing report used to escalate as
    'the same rows failed twice: unknown', which reads as a flaky test.
    """
    repo = tmp_path / "target"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n"
        + "".join(
            f"  {name}:\n    cmds: ['true']\n"
            for name in ("setup", "test", "e2e", "lint", "format-check")
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)

    # `task test` exits 0 and writes no report. That is the silent skip.
    trace = run(repo=repo, doer="none", budget=3, write_trace=False)

    assert trace["gate"] == gates.ESCALATE
    assert "never ran" in trace["reason"]
    assert "unknown" not in trace["reason"]
    # It stops on the first round. Iterating proves nothing.
    assert len(trace["attempts"]) == 1


def test_checkout_refuses_to_delete_an_earlier_lab_s_work(tmp_path):
    """After Module 2 the target repo holds work somebody did.

    A loop that quietly cleans the tree to make its own job easier is the
    behaviour this workshop exists to prevent. The refusal has to name both
    ways out, because an attendee reads it mid-lab with a clock running.
    """
    repo = tmp_path / "target"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "keep.py").write_text("A = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--quiet", "-m", "one"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "checkout", "--quiet", "-b", "other"], cwd=repo, check=True)
    (repo / "app" / "conflict.py").write_text("B = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--quiet", "-m", "two"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "checkout", "--quiet", "main"], cwd=repo, check=True)

    # The untracked file an earlier lab left behind.
    (repo / "app" / "conflict.py").write_text("MINE = 1\n", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        checkout(repo, "other")
    message = str(caught.value)
    assert "stash" in message
    assert "clean -fd" in message
    # The work is still there. The loop did not decide for the human.
    assert (repo / "app" / "conflict.py").read_text() == "MINE = 1\n"
