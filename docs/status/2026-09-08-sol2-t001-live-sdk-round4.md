---
date: 2026-09-08
doer: sdk
ticket: T001
epic: 414
story: 425
ticket_ref: 444
fix_ref: 549
round: 4
---

# Sol 2 live T001 trace: sdk, round 4

Doer: sdk
Gate: escalate
Spend: $0.7911 (cap $1.75, applied via `SOL2_E2E_MAX_USD=1.75`)
Unknown-spend turns: 0
Tests written in code phase: no
Main sha: c1f63656fd29dada53e7615e884ffe0c97d7956c

A first attempt at this cap, under an outer `timeout 1800`, was killed by
that wrapper before it returned a decision and produced no usable
evidence; the rerun below, under `timeout 3600`, is the recorded result
for this round.

## What the raw logs actually show

Both test-implementer queries ended on the SDK's own per-query dollar
ceiling in about a minute, not on a 900-second wall clock. The checked-in
raw logs carry the terminal `ResultMessage` for each: `subtype
'error_max_budget_usd'`, `terminal_reason 'budget_exhausted'`, `errors
['Reached maximum budget ($0.35)']`, `duration_ms 59317` and `71806`, and
`total_cost_usd 0.39136775` and `0.399731`, the exact numbers `$0.3914`
and `$0.3997` this trace reports as spend. $0.35 is `SOL2_E2E_MAX_USD /
(iterations + 2)`, 1.75 / 5.

The trace's own reported reason, "agent sdk query timed out after 900
seconds", is wrong about the cause. `AgentSdkBackend.collect` does not
stop at the terminal `ResultMessage`; it keeps iterating the event stream
until the generator ends, and the stream in both raw logs goes quiet
after the query already finished, so `asyncio.wait_for`'s 900-second
timeout fires on a query that had already ended a minute in. The
"cost budget spent" reason `collect` had already set from the terminal
message is discarded when the timeout branch runs and replaced with
`stop_reason "query timeout"`. Because "query timeout" is not one of
`e2e_t001.CONTROLLED_STOPS`, the wrapper reports `query_failed: True` and
exits 2 for what was a controlled cost stop. Filed as #568.

Neither query wrote a test, but not for lack of trying. Each attempted a
`Write` to `tests/test_due_date.py` inside the worktree, and each write
came back `is_error=True`, `File is in a directory that is denied by your
permission settings.` The fixture's own tracked `.claude/settings.json`
denies `Write(./tests/**)` and `Edit(./tests/**)`, and
`roles.options_for` passes `setting_sources=["project"]`, so the CLI
loads that deny list and applies it to the test implementer, whose
entire scope is `tests/**`. The write target was correctly resolved
inside `work/northwind-field-crm.worktrees/T001`, confirming #543 holds
on aim; the write was refused before it ever reached disk, so the red
gate had nothing to see. Filed as #567. No live sdk round can reach the
code phase until it lands.

Both queries' raw event logs are checked in beside this file
(`last-sdk-e2e-raw-0-test-round4.txt`, `last-sdk-e2e-raw-1-test-round4.txt`), copied via
`SOL2_E2E_RAW_LOG_DIR` with the operator's home directory and any
key-shaped text stripped.

## Clone status

`git -C work/northwind-field-crm status --porcelain` was empty before
this run and empty after. The loop's own writes landed only in
`work/northwind-field-crm.worktrees/T001` (a linked worktree, not the
clone): `steps.jsonl`, the same artifact every prior sdk round has
produced.

## Limitations

This trace corrects the stated cause; it does not rerun the doer. A
final sdk-only confirming run follows #567 (the project deny list) and
#568 (`collect` past the terminal message), not before.

The deep doer's confirming run for the same day is
`docs/status/2026-09-08-sol2-t001-live-deep-round4.md`.

The final sdk-only confirming run, after #567 and #568 landed, is
`2026-09-08-sol2-t001-live-sdk-round5.md`: the test write reached the
red gate, and the loop escalated on a rubric row, not on a timeout.
