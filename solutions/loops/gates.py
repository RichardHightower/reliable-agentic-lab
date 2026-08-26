from __future__ import annotations

PASS = "pass"
RETRY = "retry"
ESCALATE = "escalate"
DEFAULT_BUDGET = 3


def decide(*, passed: bool, iteration: int, repeat: bool, budget: int = DEFAULT_BUDGET) -> str:
    if passed:
        return PASS
    if repeat:
        return ESCALATE
    if iteration >= budget:
        return ESCALATE
    return RETRY
