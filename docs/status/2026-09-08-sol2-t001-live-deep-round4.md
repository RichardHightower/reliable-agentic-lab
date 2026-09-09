---
date: 2026-09-08
doer: deep
ticket: T001
epic: 414
story: 425
ticket_ref: 444
fix_ref: 549
round: 4
---

# Sol 2 live T001 trace: deep, round 4

Doer: deep
Gate: escalate
Spend: $1.2488 (cap $3.00 total via the target repo's `.loop.yml` `budget.usd`;
per-call cap $0.60, computed as `budget.usd / (iterations + 2)` = 3.00 / 5)
Unknown-spend turns: 0
Tests written in code phase: no
Main sha: c1f63656fd29dada53e7615e884ffe0c97d7956c

This run confirms the #549 fix. Two test-implementer attempts ran, and the
per-call dollar cutoff (`UsageCallback.on_llm_end`, `raise_error = True`)
fired on both: attempt 1 raised `DeepAgentsBudgetExceeded` at $0.6176
against the $0.60 per-call cap, attempt 2 at $0.6312. Both exceptions
reached `DeepAgentsBackend.run`, which recorded `stop_reason: "cost
budget spent"` on each, the same wording the SDK port's own cost stop
uses. The loop's own gate wording ("the test implementer backend did not
answer") still fired, because `test_result.ok` is `False` on a raised
exception; the underlying reason field carries the exception text
verbatim: `DeepAgentsBudgetExceeded: budget_exhausted: spent $0.6312
against a $0.60 per-call cap`. Neither attempt wrote a test, so the code
phase never started.

## What this confirms, and what it does not

This is the confirming live run promised at the end of the #549 trace
note carried in round 3 (`2026-09-08-sol2-t001-live-deep.md`): the
per-call cutoff now stops a real call before it reaches the recursion
limit, instead of spending through it the way the round-3 run did ($4.56
against a $3.00 cap, no per-call stop at all, because `raise_error` was
never set). It does not confirm a passing loop. The gate is an honest
escalate at the red-gate boundary, the same shape every prior round's
deep trace has shown.

## Clone status

`git -C work/northwind-field-crm status --porcelain` was empty before
this run. The per-call cap required editing the clone's own `.loop.yml`
(`budget.usd: 2.00` to `3.00`), the value `harness.py`'s `backend()`
reads to compute `max_call_usd`, so it matched the $3-per-trace
authorization for this round. That edit was reverted immediately after
the run, and the clone's status was empty again once reverted. The
loop's own writes landed only in `work/northwind-field-crm.worktrees/T001`
(a linked worktree, not the clone): `steps.jsonl`, expected from the
planner phase, matching #543's fix rooting writes at the worktree.

See `docs/status/2026-09-08-sol2-t001-live-deep.md` for the three prior
rounds this run confirms.
