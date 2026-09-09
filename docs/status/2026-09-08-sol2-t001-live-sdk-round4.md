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
evidence; that timeout was too tight for two 900-second query ceilings
plus overhead, and the rerun below, under `timeout 3600`, is the real
result for this round.

Two test-implementer queries ran and both spent real money: $0.3914 and
$0.3997. Each hit `SOL2_QUERY_TIMEOUT_SECONDS` (900 seconds, the default)
before it produced a final answer: `agent sdk query timed out after 900
seconds (elapsed=900s, events=45, usd=0.3997)`. Neither wrote a test, so
the loop escalated naming the timeout rather than the generic red-gate
wording. The code phase never started. `cap_usd` echoed 1.75 and matches
what this run was invoked with.

## A query timeout is not a `cost budget spent` stop

`e2e_t001.CONTROLLED_STOPS` only names `"max turns"` and `"cost budget
spent"` as deliberate cutoffs; `"query timeout"` is not among them, so
`AgentSdkE2EBackend.query_failed` reads `True` here and `e2e_t001.main`
exits 2 ("Agent SDK query failed"), the same as a crashed query would.
The loop's own gate, read from `implementer.run`'s trace, is still
`escalate`: a real, evidenced stop with real spend and a named reason,
not a hang and not a silent zero. This run does not confirm the SDK
port's own dollar ceiling firing mid-turn; every prior round already
covers that (see `2026-09-08-sol2-t001-live-sdk.md`). It confirms the
15-minute per-query wall clock does what its own code says, twice in a
row, at a $1.75 total cap.

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

The deep doer's confirming run for the same day is
`docs/status/2026-09-08-sol2-t001-live-deep-round4.md`.
