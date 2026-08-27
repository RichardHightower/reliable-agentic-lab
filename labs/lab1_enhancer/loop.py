"""Lab 1. The Ticket Enhancer.

Fill the two functions below. Everything else is written.

Read `loops/criteria.py` only if you stall. It is the answer.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import criteria, gates
from loops.ticket import Ticket


def judge_ticket(ticket: Ticket) -> criteria.Verdict:
    """Score one ticket. Return a Verdict.

    A judge holds no write tools. Read the ticket, decide, and report.

    Decide three things:
      1. What kind of ticket is this? Bug, feature, or user interface.
      2. Which required parts are missing for that kind?
      3. Is it ready?

    A user-interface ticket needs a wireframe. One acceptance criterion is not
    acceptance criteria.
    """
    raise NotImplementedError("fill me in")


def decide_next(
    verdict: criteria.Verdict,
    iteration: int,
    previous: tuple[str, ...] | None,
    budget: int = 3,
) -> gates.Decision:
    """Choose the next move: pass, retry, or escalate.

    There is no fourth exit. The one people miss is stable failure: when this
    round finds exactly the same gaps as the last one, another round changes
    nothing, so stop rather than spending the budget.
    """
    raise NotImplementedError("fill me in")
