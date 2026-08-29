---
name: test-ticket-implementer
description: Test a standalone Lab 2 ticket-implementer runtime end to end, from a fast local phase-fence regression to the shared T001 CRM fixture. Use for Deep Agents, Agent SDK, or a future runtime such as CrewAI without creating a shared loop engine.
---

# Test a ticket implementer

Use this skill to validate a standalone `solutions/sol2_implementer_*` port
against the ready `T001` ticket. The test outcome is a receipt in the shared
disposable CRM clone, not model prose or a process exit code alone.

## Preserve the workshop shape

- Keep every runtime folder standalone. Do not extract this procedure into a
  shared `loops/` package or make a new runtime import a production loop from a
  sibling folder.
- Create one worktree per runtime and one CRM clone only. Track B reuses the
  Track A clone; it never clones another CRM.
- Run Track A once through the designated deterministic driver. Today that is
  `solutions/sol2_implementer_deep_agents`. A future runtime supplies its own
  folder-local adapter or wrapper for Track B.
- Treat `.harness/last-implementer.json` as the product. Preserve `.harness`
  while resetting the disposable clone so evidence remains available.
- A live model call, reset of the CRM clone, push, PR, or merge needs the
  user's authorization. A request to run this E2E plan authorizes only the
  bounded runs described below, not an unbounded retry.

## Start here

1. Read the target runtime's `Taskfile.yml`, `SPEC.md`, and test files. Confirm
   its target repo, ticket identifier, model-cost limit, and receipt location.
2. Create/confirm a dedicated worktree and branch. Keep the public CRM clone
   under the Deep Agents worktree at the canonical location in the reference
   procedure.
3. Run the runtime's local test suite before the live path. Do not spend a
   token to diagnose a failing offline suite.
4. Follow [the shared golden path](references/golden-path.md) exactly. It
   contains the current paths, commands, receipt contract, Track A, Track B,
   cleanup, and verdict rules.

## Fast phase-fence regression

When changing role scopes, phase graphs, or judge behavior, add and run a
folder-local scripted E2E before touching the shared CRM. It must complete
without an SDK, key, model call, or outer timeout.

Use one small acceptance criterion whose result is easy to inspect—for example,
rename a backend field and its UI field. The scenario should prove, in order:

- `implementer.run()` persisted a plan with a test step and a code step;
- the test phase changed a real file under `tests/**` and produced a new red
  test id;
- the code phase changed only the allowed backend/UI paths and left the test's
  final bytes intact; and
- a judge-only graph contains only the judge and its read tool. A code-doer
  attempt to rewrite that test must be refused.

Keep the fake reports and scripted backend in the runtime folder's own tests.
This is structural proof of the hand-off, not a replacement for Track A's
public-CRM receipt or Track B's bounded live check. Run the folder's `task e2e`
after adding the regression; a timeout-prone model probe is never the first
test of a permission boundary.

## Adding another runtime

Before spending on a future runtime, add a folder-local preflight that proves:

- its constructed backend passes unchanged through the implementer driver's
  concrete backend boundary;
- test and code phases cannot access each other's write paths structurally,
  rather than only by prompt wording;
- a terminal max-turn or cost ceiling is reported as a controlled loop stop,
  while a transport/query timeout is reported as a failed query;
- its artifacts redact prompts, model events, and credentials.

Use the same shared CRM and receipt assertions. Give the runtime a unique
`doer` value and record its per-call cost/stop evidence beside the standard
receipt. Do not widen the public receipt schema merely to expose raw model
output.

## Report the result

Report Track A and Track B separately. For each run, include the runtime, gate,
reason, `red_ids`, phase file changes, receipt path, query-failure status, and
recorded spend. Call Track B a pass only when it reaches a valid receipt with
the expected scope; a green implementation is stronger than, but not required
for, a bounded harness pass.

If the run changes code, leave the CRM clone clean after preserving
`.harness`. File or update a runtime-local issue before making a fix; do not
retry a live spend until the offline regression test passes.
