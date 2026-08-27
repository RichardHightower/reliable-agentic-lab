"""Lab 4. The Broken PR Fixer. Filled in.

This is the lab 4 answer, the same file as `solutions/sol4_fixer/`.

Nobody is watching this loop, so the exits matter more than the successes.
Giving up is allowed. Giving up silently is the bug.
"""

from __future__ import annotations

import fixer
from contract import Contract, RunResult


def summarize_failure(run_result: RunResult) -> str:
    """Say what is broken, in a few lines a human can act on.

    The orchestrator reads this, not the whole log. Sending the log would put
    the failure in the middle of a long context, which is where accuracy is
    worst.
    """
    return fixer.failure_summary(run_result)


def repair_until_green(contract: Contract, budget: int = 3) -> dict:
    """Repair until the suite is green, or stop and explain.

    The returned trace carries the gate and the reason. The next person to open
    this pull request has to know why the agent walked away.
    """
    return fixer.run(repo=contract.repo, budget=budget, doer="reference")
