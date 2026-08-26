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
from loops.fixer import failure_summary, run

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
