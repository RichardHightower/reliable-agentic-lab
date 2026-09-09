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
Gate: unknown. The process hit its own outer `timeout 1800` wrapper before
`implementer.run` returned a decision.
Spend: unknown. Real money was spent across at least one completed query;
the amount was never written to disk. See below for why.
Cap applied: cap_usd 3.00, via `SOL2_E2E_MAX_USD=3` (the value this run
was invoked with; the file that normally echoes it back,
`.harness/last-sdk-e2e.md`, was never written, so this trace states the
invoked value directly).
Unknown-spend turns: at least 2. A first test-implementer attempt
completed and a second was in flight when the process was killed; neither
attempt's spend survived the kill.
Tests written in code phase: no. The code phase never started.
Main sha: c1f63656fd29dada53e7615e884ffe0c97d7956c

## What happened

`.harness/state.json` inside `work/northwind-field-crm.worktrees/T001`
shows `test_phase_attempts: 1` and `red_ids: []` at the time it was last
written: the first test-implementer query completed and did not produce a
new failing test, the same pattern every prior round's sdk trace shows (a
query that spends its own per-query budget before writing anything).
`implementer.py`'s retry loop does not stop after one empty attempt at
the shipped `iterations: 3`, so a second attempt started right after. That
second attempt did not return, checkpoint, or raise before the outer
`timeout 1800` (30 minutes) killed the whole process at the 1800-second
mark. `timeout`'s own exit code, 124, is what this run actually returned,
not a code from `e2e_t001.py` itself.

`AgentSdkE2EBackend.calls` and `.spent_usd` live only in the running
process's memory. `_write_extras`, the function that persists them to
`.harness/last-sdk-e2e.md` and the raw log directory, runs only after
`implementer.run` returns control to `e2e_t001.main`. None of that data
survived the kill: no raw event log, no `gate:` or `reason:` line, no
per-call spend figure. The per-query internal ceiling
(`SOL2_QUERY_TIMEOUT_SECONDS`, 900 seconds by default) should have ended
the second attempt with its own `stop_reason: "query timeout"` around the
15-minute mark, well inside the 30-minute outer bound. It did not visibly
do so here, or it did so too close to the kill for a checkpoint write to
land. This trace does not diagnose which; it reports what the evidence on
disk shows and no more.

## What this does and does not confirm

This run does not confirm a `cost budget spent` stop for the SDK doer.
The SDK port's own per-query budget ceiling firing mid-turn is not new
behavior from #549, and every prior round already exercised it (see
`docs/status/2026-09-08-sol2-t001-live-sdk.md`). This round's SDK attempt
neither adds to nor detracts from that earlier confirmation. It spent an
unknown amount of real money against the $3 cap and produced no gate
decision. Treat it as evidence that the outer wrapper worked as a
backstop, and nothing more.

## Clone status

`git -C work/northwind-field-crm status --porcelain` was empty both
before this run and after it finished (killed). The loop's own writes
landed only in `work/northwind-field-crm.worktrees/T001` (a linked
worktree, not the clone): `steps.jsonl`, the same artifact every prior
sdk round has produced.

The deep doer's confirming run for the same day is
`docs/status/2026-09-08-sol2-t001-live-deep-round4.md`.
