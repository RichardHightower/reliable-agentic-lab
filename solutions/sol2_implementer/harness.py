"""Lab 2. The harness. Filled in.

This is the lab 2 answer, the same file as `solutions/sol2_implementer/`. The order is the lesson:

    tests first  ->  prove them red  ->  code until green  ->  judge  ->  gate

Read `loops/implementer.py` for the full run, and `loops/rubric.py` for the
ten rows.
"""

from __future__ import annotations

import gates, implementer, rubric
from contract import Contract, RunResult


def red_gate(before: RunResult, after: RunResult) -> set[str]:
    """Return the test ids that are failing now and did not exist before.

    An empty result is not a small problem. It means the new tests passed
    against code that was never written, so they prove nothing and the loop
    must stop rather than continue to the code implementer.
    """
    seen = before.junit.passed_ids | before.junit.failed_ids
    return implementer._new_test_ids(seen, after.junit.failed_ids)


def score_attempt(contract: Contract, **evidence) -> rubric.Score:
    """Score one attempt against the ten rubric rows.

    Every argument left out becomes a failing row. Absent evidence is never a
    pass, which is why this forwards the keywords instead of filling defaults.
    """
    return rubric.score(contract=contract, **evidence)


def run_loop(contract: Contract, budget: int = 3, ticket_id: str = "T001") -> dict:
    """Run the harness until it passes, stalls, or runs out of budget.

    Python holds the loop. `implementer.run` plans, writes the tests, checks
    the red gate, writes the code, scores, and asks the gate what to do next.
    """
    return implementer.run(
        repo=contract.repo,
        ticket_id=ticket_id,
        budget=budget,
        doer="reference",
    )


def decide(score: rubric.Score, iteration: int, previous=None, budget: int = 3) -> gates.Decision:
    """The gate. Kept here so the three exits stay visible in this file."""
    return gates.decide(
        passed=score.passed,
        iteration=iteration,
        budget=budget,
        signature=score.signature(),
        previous_signature=previous,
    )
