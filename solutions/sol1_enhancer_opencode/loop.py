"""Lab 1. The Ticket Enhancer. Filled in.

This is the lab 1 answer, the same file as `solutions/sol1_enhancer/`. Each function hands the work to the reference
implementation, because that is where the lesson lives and duplicating it here
would let the two drift apart.

Read `loops/criteria.py` to see how the judge decides.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import criteria, gates
from loops.ticket import Ticket


def judge_ticket(ticket: Ticket) -> criteria.Verdict:
    """Score one ticket. Return a Verdict.

    `criteria.judge` classifies the ticket, looks up the parts that kind of
    ticket needs, and reports what is missing. It writes nothing.
    """
    return criteria.judge(ticket)


def decide_next(
    verdict: criteria.Verdict,
    iteration: int,
    previous: tuple[str, ...] | None,
    budget: int = 3,
) -> gates.Decision:
    """Choose the next move: pass, retry, or escalate.

    The signature is what is missing, not how it was worded. Two equal
    signatures mean the last round changed nothing, so the gate escalates
    rather than spending the rest of the budget on an identical failure.
    """
    return gates.decide(
        passed=verdict.ready,
        iteration=iteration,
        budget=budget,
        signature=verdict.signature(),
        previous_signature=previous,
    )
