"""Checks for the stop conditions. Three exits and no fourth."""

from __future__ import annotations

from loops.gates import ESCALATE, PASS, RETRY, decide, retry_instruction


def test_a_green_rubric_passes():
    assert decide(passed=True, iteration=1).gate == PASS


def test_green_plus_an_agreeing_final_judge_passes():
    assert decide(passed=True, iteration=1, judge_done=True).gate == PASS


def test_green_but_the_final_judge_disagrees_escalates():
    """The deterministic rows can all pass on work that misses the point."""
    decision = decide(passed=True, iteration=1, judge_done=False)
    assert decision.gate == ESCALATE
    assert "not done" in decision.reason


def test_a_new_failure_retries():
    decision = decide(passed=False, iteration=1, budget=3, signature=("tests_passed",))
    assert decision.gate == RETRY
    assert decision.final_attempt is False


def test_the_same_failure_twice_escalates_without_spending_the_budget():
    decision = decide(
        passed=False,
        iteration=1,
        budget=99,
        signature=("tests_passed", "coverage_floor"),
        previous_signature=("tests_passed", "coverage_floor"),
    )
    assert decision.gate == ESCALATE
    assert decision.repeat_failure is True


def test_a_different_failure_is_progress_and_retries():
    decision = decide(
        passed=False,
        iteration=1,
        budget=3,
        signature=("coverage_floor",),
        previous_signature=("tests_passed",),
    )
    assert decision.gate == RETRY


def test_the_last_iteration_escalates():
    decision = decide(passed=False, iteration=3, budget=3, signature=("lint_clean",))
    assert decision.gate == ESCALATE
    assert "iteration budget" in decision.reason


def test_running_out_of_money_escalates_before_iterations():
    decision = decide(passed=False, iteration=1, budget=99, signature=("x",), usd_left=0.0)
    assert decision.gate == ESCALATE
    assert "money" in decision.reason


def test_the_second_to_last_attempt_is_flagged_final():
    decision = decide(passed=False, iteration=2, budget=3, signature=("x",))
    assert decision.gate == RETRY
    assert decision.final_attempt is True


def test_the_final_attempt_instruction_narrows_the_ask():
    decision = decide(passed=False, iteration=2, budget=3, signature=("tests_passed",))
    text = retry_instruction(decision, ["tests_passed"])
    assert "FINAL ATTEMPT" in text
    assert "Do not refactor" in text


def test_an_ordinary_retry_instruction_does_not_narrow():
    decision = decide(passed=False, iteration=1, budget=5, signature=("tests_passed",))
    text = retry_instruction(decision, ["tests_passed", "lint_clean"])
    assert "FINAL ATTEMPT" not in text
    assert "tests_passed, lint_clean" in text


def test_stop_is_true_for_every_gate_except_retry():
    assert decide(passed=True, iteration=1).stop is True
    assert decide(passed=False, iteration=9, budget=9, signature=("x",)).stop is True
    assert decide(passed=False, iteration=1, budget=9, signature=("x",)).stop is False
