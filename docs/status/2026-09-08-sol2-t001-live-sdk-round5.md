---
date: 2026-09-08
doer: sdk
ticket: T001
epic: 414
story: 425
ticket_ref: 444
fix_ref: 567
also_ref: 568
round: 5
---

# Sol 2 live T001 trace: sdk, round 5

Doer: sdk
Gate: escalate
Spend: $2.0880 (cap $3.96, applied via `SOL2_E2E_MAX_USD=3.96`)
Unknown-spend turns: 0
Tests written in code phase: no
Main sha: d5dd9c810de88f90babe4a0811b4ed2e24ffd815

This is the final sdk-only confirming run named in the round-4 trace's
Limitations line, after #567 and #568 landed in PR #570.

## The test write reaches the red gate

The test-implementer query wrote `tests/test_t001_due_dates.py` inside
the worktree, and the write held: no permission deny fired. `red_ids`
populated with all seven acceptance-criterion test ids
(`test_ac_1_...` through `test_ac_7_...`), and the code phase then ran
against those seven, the first time a live sdk round on this ticket has
reached the code phase at all. This confirms #567: the fixture's own
`.claude/settings.json` deny list no longer blocks the test implementer's
own scope.

## The queries end with their real reason

None of the four queries this run made (one test, three code) reported a
timeout. Each stop is `none` in the run's own summary, `ok=True`, with a
real dollar figure: $0.6929, $0.4932, $0.2794, $0.6225. This confirms
#568: `AgentSdkBackend.collect` now returns on the terminal result
instead of reading the stream past it, so a query that ends on a
controlled reason is reported as one, not relabeled by the outer
`asyncio.wait_for` ceiling.

## The gate itself

Three code-phase iterations ran. Iteration 1 hit its turn limit mid-work
and resumed; iteration 2 fixed the failing test and every rubric row but
`ui_has_e2e`; iteration 3, told to fix only that row, left it failing
again. The loop escalated on `gates.decide`'s repeat-failure rule: "the
same rows failed twice: ui_has_e2e. The loop is not converging." This is
a rubric-level stop, not a budget or timeout artifact. Ten rubric rows
ran; nine passed, including `tests_passed`, `coverage_floor` (80.35%
against a 78% floor), `criteria_covered`, and `write_scope`.

`cap_usd` echoed 3.96 and matches what this run was invoked with. Total
spend $2.0880, under the cap.

The four raw event logs are checked in beside this file
(`last-sdk-e2e-raw-0-test-round5.txt`, `last-sdk-e2e-raw-1-code-round5.txt`,
`last-sdk-e2e-raw-2-code-round5.txt`, `last-sdk-e2e-raw-3-code-round5.txt`),
copied via `SOL2_E2E_RAW_LOG_DIR` with the operator's home directory and
any key-shaped text stripped, including one instance of a model-written
`/Users/...` shorthand that the checked-in redaction pass did not catch,
removed by hand before commit.

## Clone status

`git -C work/northwind-field-crm status --porcelain` was empty before
this run and empty after. The loop's own writes, including the test file
that finally reached the red gate, landed only in
`work/northwind-field-crm.worktrees/T001` (a linked worktree, not the
clone).

The round-4 trace for this doer is
`docs/status/2026-09-08-sol2-t001-live-sdk-round4.md`.
