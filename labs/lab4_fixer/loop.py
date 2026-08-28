"""Lab 4. The Broken PR Fixer.

Fill the two functions below.

This loop runs unattended. Nobody is watching to stop it, so the exits matter
more than the successes, and giving up silently is the one thing it may not do.

Read `solutions/sol4_fixer/fixer.py` only if you stall.
"""

from __future__ import annotations

from contract import Contract, RunResult


def summarize_failure(run_result: RunResult) -> str:
    """Say what is broken, in a few lines a human can act on.

    The orchestrator sees this, not the whole log. Name the failing tests and
    the first real error line.
    """
    raise NotImplementedError("fill me in")


def repair_until_green(contract: Contract, budget: int = 3) -> dict:
    """Repair until the suite is green, or stop and explain.

    Stopping is designed. Stopping without an explanation is a bug: the next
    person to look at this pull request has to know why the agent walked away.
    """
    raise NotImplementedError("fill me in")
