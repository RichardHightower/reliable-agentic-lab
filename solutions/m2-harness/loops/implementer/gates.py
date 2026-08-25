from __future__ import annotations


PASS = "pass"
RETRY = "retry"
ESCALATE = "escalate"

DEFAULT_BUDGET = 3


def decide(
    *,
    passed: bool,
    iteration: int,
    failed_node_ids: list[str],
    previous_failed_node_ids: list[str] | None,
    budget: int = DEFAULT_BUDGET,
) -> dict:
    """Quality gate for one orchestrator step.

    Pass if the hidden grader is green.
    Retry if the failure is new and budget remains.
    Escalate on a repeated failure signature or a spent budget.
    """
    repeat = previous_failed_node_ids is not None and failed_node_ids == previous_failed_node_ids
    if passed:
        gate = PASS
    elif repeat:
        gate = ESCALATE
    elif iteration >= budget:
        gate = ESCALATE
    else:
        gate = RETRY
    return {
        "gate": gate,
        "repeat_failure": repeat and not passed,
        "iteration": iteration,
        "budget": budget,
    }
