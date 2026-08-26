"""Checks for steps.jsonl.

The plan is a contract. These cover the ways it can be empty, vague, or
self-certifying.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loops.steps import Plan, PlanRejected, Step


def step(**over) -> Step:
    base = {
        "id": "S1",
        "ticket": "T001",
        "role": "test_implementer",
        "action": "Add a test for the due_date column",
        "validation": "tests/test_due_date.py::test_model_has_optional_due_date fails",
        "criterion": "AC-1",
    }
    base.update(over)
    return Step(**base)


def a_valid_plan() -> Plan:
    return Plan(
        steps=[
            step(id="S1", role="test_implementer", criterion="AC-1"),
            step(
                id="S2",
                role="code_implementer",
                action="Add the nullable due_date column",
                validation="tests/test_due_date.py::test_model_has_optional_due_date passes",
                criterion="AC-1",
            ),
        ]
    )


def test_a_valid_plan_passes():
    a_valid_plan().validate(criteria=["AC-1"])


def test_an_empty_plan_is_rejected():
    with pytest.raises(PlanRejected, match="no steps"):
        Plan().validate()


def test_a_step_without_a_validation_statement_is_rejected():
    plan = Plan(steps=[step(validation="   ")])
    with pytest.raises(PlanRejected, match="wish"):
        plan.validate()


def test_a_plan_with_no_test_step_is_rejected():
    """Tests come first. A plan that only writes code skips the red gate."""
    plan = Plan(steps=[step(role="code_implementer")])
    with pytest.raises(PlanRejected, match="Tests come first"):
        plan.validate()


def test_an_uncovered_acceptance_criterion_is_rejected():
    with pytest.raises(PlanRejected, match="AC-9"):
        a_valid_plan().validate(criteria=["AC-1", "AC-9"])


def test_duplicate_step_ids_are_rejected():
    plan = Plan(steps=[step(id="S1"), step(id="S1", role="code_implementer")])
    with pytest.raises(PlanRejected, match="duplicate"):
        plan.validate()


def test_an_unknown_role_is_rejected():
    with pytest.raises(PlanRejected, match="unknown role"):
        Plan(steps=[step(role="judge")]).validate()


def test_marking_done_without_evidence_is_refused():
    plan = a_valid_plan()
    with pytest.raises(PlanRejected, match="evidence"):
        plan.mark("S1", "done")


def test_marking_done_with_evidence_works():
    plan = a_valid_plan()
    marked = plan.mark(
        "S1", "done", evidence="junit:tests.test_due_date::test_model_has_optional_due_date"
    )
    assert marked.done
    assert plan.complete is False
    plan.mark("S2", "done", evidence="junit:tests.test_due_date::test_model_has_optional_due_date")
    assert plan.complete is True


def test_a_round_trip_through_disk_keeps_every_field(tmp_path: Path):
    original = a_valid_plan()
    original.mark("S1", "doing")
    original.save(tmp_path)
    loaded = Plan.load(tmp_path)
    assert [s.id for s in loaded.steps] == ["S1", "S2"]
    assert loaded.get("S1").status == "doing"
    assert loaded.get("S2").validation.endswith("passes")


def test_a_missing_file_is_rejected_not_treated_as_empty(tmp_path: Path):
    with pytest.raises(PlanRejected, match="did not run"):
        Plan.load(tmp_path)


def test_a_corrupt_line_is_rejected(tmp_path: Path):
    (tmp_path / "steps.jsonl").write_text('{"id": "S1"}\nnot json\n')
    with pytest.raises(PlanRejected):
        Plan.load(tmp_path)


def test_a_line_missing_required_fields_is_rejected(tmp_path: Path):
    (tmp_path / "steps.jsonl").write_text(
        '{"id": "S1", "ticket": "T001", "role": "code_implementer"}\n'
    )
    with pytest.raises(PlanRejected, match="missing"):
        Plan.load(tmp_path)


def test_the_summary_is_short_enough_for_an_orchestrator():
    """The orchestrator sees this, never the whole plan."""
    plan = a_valid_plan()
    plan.mark("S1", "done", evidence="junit:x")
    assert plan.summary() == "2 steps: todo 1, done 1"
