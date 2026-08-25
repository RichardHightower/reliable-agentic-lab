from __future__ import annotations

PASS = "pass"
RETRY = "retry"
ESCALATE = "escalate"

DEFAULT_MAX_LOOPS = 3
DEFAULT_MAX_BUDGET = 8.0
CALL_COST = 1.0


def decide(
    *,
    passed: bool,
    iteration: int,
    failed_ids: list[str],
    previous_failed_ids: list[str] | None,
    cost: float,
    max_loops: int = DEFAULT_MAX_LOOPS,
    max_budget: float = DEFAULT_MAX_BUDGET,
) -> dict:
    repeat = previous_failed_ids is not None and failed_ids == previous_failed_ids
    budget_spent = cost >= max_budget
    if passed:
        gate = PASS
    elif repeat or budget_spent or iteration >= max_loops:
        gate = ESCALATE
    else:
        gate = RETRY
    return {
        "gate": gate,
        "repeat_failure": repeat and not passed,
        "budget_spent": budget_spent and not passed,
        "iteration": iteration,
        "cost": cost,
    }
