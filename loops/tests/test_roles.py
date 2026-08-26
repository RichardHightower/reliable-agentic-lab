"""Checks for role write scope.

The separation between roles is the harness. If scope leaks, nothing else in
the loop means anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loops.contract import Contract
from loops.roles import Judge, ScopeViolation, WriteScope, build


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  setup:\n  test:\n  e2e:\n  lint:\n  format-check:\n"
    )
    (tmp_path / ".loop.yml").write_text(
        "roles:\n"
        "  test_implementer:\n"
        '    write_allow: ["tests/**"]\n'
        "  code_implementer:\n"
        '    write_allow: ["app/**"]\n'
        '    write_deny: ["tests/**"]\n'
        "budget:\n"
        "  iterations: 2\n"
        "  usd: 1.50\n"
    )
    return tmp_path


def test_a_judge_has_no_write_method():
    """Not 'must not write'. Cannot write. There is no path to call."""
    assert not hasattr(Judge, "write")


def test_the_code_implementer_cannot_touch_tests(target: Path):
    roles = build(Contract(target))
    coder = roles["code_implementer"]
    coder.write("app/models.py", "x = 1\n")
    with pytest.raises(ScopeViolation):
        coder.write("tests/test_smoke.py", "assert True\n")


def test_the_test_implementer_cannot_touch_app_code(target: Path):
    roles = build(Contract(target))
    tester = roles["test_implementer"]
    tester.write("tests/test_due_date.py", "assert True\n")
    with pytest.raises(ScopeViolation):
        tester.write("app/models.py", "x = 1\n")


def test_deny_beats_allow():
    scope = WriteScope(allow=["**"], deny=["tests/**"])
    assert scope.permits("app/main.py") is True
    assert scope.permits("tests/test_a.py") is False


def test_a_shallow_glob_matches_the_directory_itself():
    """`tests/**` must cover tests/a.py, not only tests/deep/a.py."""
    scope = WriteScope(allow=["tests/**"])
    assert scope.permits("tests/a.py") is True
    assert scope.permits("tests/deep/a.py") is True
    assert scope.permits("app/a.py") is False


def test_an_empty_allow_list_permits_nothing():
    scope = WriteScope()
    assert scope.permits("anything.py") is False


def test_violations_reports_every_out_of_scope_path(target: Path):
    coder = build(Contract(target))["code_implementer"]
    changed = ["app/main.py", "tests/test_a.py", "Taskfile.yml"]
    assert coder.violations(changed) == ["tests/test_a.py", "Taskfile.yml"]


def test_the_orchestrator_runs_out_of_iterations(target: Path):
    boss = build(Contract(target))["orchestrator"]
    assert boss.budget_iterations == 2
    assert boss.budget_usd == 1.5
    boss.start_iteration()
    assert boss.exhausted is False
    boss.start_iteration()
    assert boss.exhausted is True


def test_the_orchestrator_runs_out_of_money(target: Path):
    boss = build(Contract(target))["orchestrator"]
    boss.spend(1.60)
    assert boss.usd_left == 0.0
    assert boss.exhausted is True


def test_scope_survives_a_path_that_tries_to_escape(target: Path):
    coder = build(Contract(target))["code_implementer"]
    with pytest.raises(ScopeViolation):
        coder.write("../outside.py", "x = 1\n")
