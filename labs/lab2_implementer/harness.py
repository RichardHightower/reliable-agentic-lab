"""Lab 2. The harness. The centre of the workshop.

Fill the three functions below.

The order is fixed and it is the whole point:

    tests first  ->  prove them red  ->  code until green  ->  judge  ->  gate

Read `rubric.py` and `gates.py` in this folder if you stall.
"""

from __future__ import annotations

import gates, rubric  # noqa: F401  (you will need gates)
from contract import Contract, RunResult


def red_gate(before: RunResult, after: RunResult) -> set[str]:
    """Return the test ids that are failing now and did not exist before.

    This is the proof that the new tests test something. A test that passes
    before any code is written proves nothing, so an empty result must stop the
    loop rather than let it continue.
    """
    raise NotImplementedError("fill me in")


def score_attempt(contract: Contract, **evidence) -> rubric.Score:
    """Score one attempt against the ten rubric rows.

    Every row is computed from junit.xml, coverage.xml, exit codes, steps.jsonl,
    and the diff. No model call, so no model can be talked into a pass.

    "The tests passed" is one row of ten.
    """
    raise NotImplementedError("fill me in")


def run_loop(contract: Contract, budget: int = 3) -> dict:
    """Run the harness until it passes, stalls, or runs out of budget.

    Hold the loop in Python. The model does not get to count its own retries.
    """
    raise NotImplementedError("fill me in")
