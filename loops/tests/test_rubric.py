"""Checks for the rubric.

Every row has to be able to fail. A row that cannot fail is decoration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loops.contract import Contract, CoverageReport, RunResult, SuiteReport
from loops.rubric import score
from loops.steps import Plan, Step


@pytest.fixture()
def contract(tmp_path: Path) -> Contract:
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  setup:\n  test:\n  e2e:\n  lint:\n  format-check:\n"
    )
    (tmp_path / ".loop.yml").write_text(
        'rubric:\n  coverage_floor: 78\n  require_red: true\n  ui_paths: ["app/templates/**"]\n'
    )
    return Contract(tmp_path)


def run(task="test", *, exit_code=0, tests=5, failures=0, passed=None, coverage=90.0, empty=False):
    report = SuiteReport(
        exists=True,
        tests=0 if empty else tests,
        failures=failures,
        errors=0,
        passed_ids=set(passed or {"tests.t::a", "tests.t::b"}),
        failed_ids=set() if not failures else {"tests.t::bad"},
    )
    return RunResult(
        task=task,
        exit_code=exit_code,
        output="",
        junit=report,
        coverage=CoverageReport(exists=True, line_rate=coverage),
    )


def good_plan() -> Plan:
    return Plan(
        steps=[
            Step(
                id="S1",
                ticket="T001",
                role="test_implementer",
                action="write the test",
                validation="tests.t::a fails",
                criterion="AC-1",
                status="done",
                evidence="tests.t::a",
            )
        ]
    )


def full(contract, **over):
    args = {
        "contract": contract,
        "plan": good_plan(),
        "criteria": ["AC-1"],
        "test_run": run(),
        "e2e_run": run("e2e"),
        "lint_run": run("lint"),
        "format_run": run("format-check"),
        "red_ids": {"tests.t::a"},
        "scope_violations": [],
        "changed": ["app/models.py"],
    }
    args.update(over)
    return score(**args)


def test_a_complete_attempt_passes_every_row(contract):
    result = full(contract)
    assert result.passed, result.report()
    assert len(result.rows) == 10


def test_a_missing_junit_report_fails_two_rows(contract):
    result = full(contract, test_run=None)
    names = {r.name for r in result.failed_rows}
    assert {"tests_ran", "tests_passed", "coverage_floor"} <= names


def test_an_empty_suite_is_not_a_pass(contract):
    result = full(contract, test_run=run(empty=True))
    assert not result.passed
    assert "zero tests" in {r.name: r.detail for r in result.rows}["tests_ran"]


def test_a_failing_test_fails_the_row(contract):
    result = full(contract, test_run=run(failures=2))
    assert not result.passed
    assert "tests_passed" in result.signature()


def test_no_red_phase_fails_the_red_gate(contract):
    result = full(contract, red_ids=set())
    assert not result.passed
    assert "red_first" in result.signature()


def test_the_red_gate_can_be_waived_by_the_target_repo(tmp_path: Path):
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  setup:\n  test:\n  e2e:\n  lint:\n  format-check:\n"
    )
    (tmp_path / ".loop.yml").write_text("rubric:\n  require_red: false\n  coverage_floor: 10\n")
    result = full(Contract(tmp_path), red_ids=set())
    assert "red_first" not in result.signature()


def test_coverage_below_the_floor_fails(contract):
    result = full(contract, test_run=run(coverage=60.0))
    assert "coverage_floor" in result.signature()


def test_a_criterion_with_no_step_fails(contract):
    result = full(contract, criteria=["AC-1", "AC-2"])
    assert "criteria_covered" in result.signature()


def test_a_criterion_whose_test_never_passed_fails(contract):
    """A step can claim done. The rubric checks the test actually passed."""
    plan = good_plan()
    plan.steps[0].evidence = "tests.t::never_ran"
    result = full(contract, plan=plan, test_run=run(passed={"tests.t::something_else"}))
    assert "criteria_covered" in result.signature()


def test_an_unfinished_step_fails(contract):
    plan = good_plan()
    plan.steps[0].status = "todo"
    result = full(contract, plan=plan)
    assert "steps_done" in result.signature()


def test_touching_a_template_without_an_e2e_test_fails(contract):
    result = full(contract, changed=["app/templates/task_form.html"], e2e_run=None)
    assert "ui_has_e2e" in result.signature()


def test_touching_a_template_with_a_green_e2e_test_passes(contract):
    result = full(contract, changed=["app/templates/task_form.html"])
    assert "ui_has_e2e" not in result.signature()


def test_writing_outside_scope_fails(contract):
    result = full(contract, scope_violations=["tests/test_a.py"])
    assert "write_scope" in result.signature()


def test_an_unchecked_scope_is_a_failure_not_a_pass(contract):
    """Forgetting to check is not the same as finding nothing."""
    result = full(contract, scope_violations=None)
    assert "write_scope" in result.signature()


def test_lint_and_format_failures_are_separate_rows(contract):
    result = full(
        contract, lint_run=run("lint", exit_code=1), format_run=run("format-check", exit_code=1)
    )
    assert {"lint_clean", "format_clean"} <= set(result.signature())


def test_the_signature_is_stable_across_identical_failures(contract):
    first = full(contract, test_run=run(failures=1))
    second = full(contract, test_run=run(failures=1))
    assert first.signature() == second.signature()
    assert first.signature() != full(contract).signature()
