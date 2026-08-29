---
date: 2026-08-28
slug: sol2-implementer-deep-agents-testing
title: Test the Lab 2 Deep Agents implementer port
git_base: "7d1cab15d335f38e6dd8d6eb80742f3e194dbb1b"
branch: codex/sol2-deep-agents-test-plan
---

# Test plan: `sol2_implementer_deep_agents`

## Purpose and boundary

This folder is the complete Lab 2 implementer port: Python owns the ticket
loop, red gate, deterministic rubric, and Pass / Retry / Escalate decision;
LangChain Deep Agents supplies the scoped workers.  Tests must prove both
halves and, most importantly, their hand-off.  The target outcome is a
standalone folder where `task test` is an offline release gate and a separate,
explicitly opted-in check detects Deep Agents API drift.

This is not a proposal for a reusable loop framework.  Fixtures, fakes, and
test helpers stay in this folder.  Do not import a sibling solution or recreate
`loops/`.

## Starting snapshot

- The isolated worktree is
  `/private/tmp/reliable-agentic-lab-sol2-deep-agents-test-plan`, on
  `codex/sol2-deep-agents-test-plan`, based on `7d1cab1`.
- The folder currently has 54 deterministic tests: adapter/result handling,
  Deep Agents configuration and write fences, and two standalone checks.
  They use explicit `langchain` and `deepagents` module fakes and make no
  credential or network calls.
- `task table` succeeds without a target clone or SDK and prints the five
  roles.  With no target repo it deliberately has no configured writer scope;
  the test fixture with `.loop.yml` is the source of scope assertions.
- `task test` cannot yet start in this new worktree because neither the local
  virtual environment nor the system interpreter has `pytest`.  That is an
  environment bootstrap prerequisite, not a product-test failure.  Do not use
  `task setup` merely to run the offline suite: it installs the SDK as well.
- The large untested surface is the actual ticket driver and its local Python
  contract: `contract.py`, `ticket.py`, `steps.py`, `gates.py`, `rubric.py`,
  `doers.py`, and almost all of `implementer.py` and `harness.py`.

The current Deep Agents API exposes `tools`, `subagents`, `skills`, `memory`,
`permissions`, `backend`, and `checkpointer` on `create_deep_agent`.  The
application supplies the backend and persistence choices.  That makes SDK
construction a compatibility concern, but it does not require a model call to
test the Python-controlled loop.

## Testing lanes

| Lane | What it proves | Dependencies | Where it runs |
| --- | --- | --- | --- |
| Offline unit/integration | Contract, red gate, write attribution, deterministic rubric, and role fences | `pytest`, `git`, `task`; no SDK/key/clone/network | Every PR and `task test` |
| Offline reference E2E | The actual solution `Taskfile` drives a target from a ready ticket through red, green, rubric, and trace | Folder-local test venv, `pytest`, `coverage`, `git`, `task`; no SDK/key/network | Every PR and `task e2e` |
| Installed-SDK compatibility | The installed Deep Agents release accepts this folder's graph configuration without invoking a model | Folder-local venv and `deepagents`; no API key | Scheduled CI and SDK-upgrade review |
| Credentialed Deep Agents E2E | The same disposable target completes one small ticket through `--doer deep` with real role/tool evidence | SDK, API key, disposable repo | Manual/protected dispatch only |

The first two lanes are release gates.  A model that declines an unsafe action
is not evidence that the denial path works, so every negative permission case
stays deterministic and direct.

## Lane 1 — offline behavior and loop integration

Keep all existing role, skill/memory mount, response-schema, and adapter
message-shape tests.  Extend the folder-local `tests/` suite as follows.

### Foundation fixtures

Add one reusable test fixture that creates a disposable Git target repo with:

- a valid `Taskfile.yml`, `.loop.yml`, `tickets/`, `app/`, `tests/`, and
  `reports/` layout;
- ready and draft ticket variants with explicit acceptance criteria;
- JUnit and Cobertura writers or a stateful `Contract.run` seam, so tests can
  model baseline, red, green, stale, empty, and failed reports exactly; and
- a deterministic scripted backend.  On its first call it can write only the
  requested failing test; later calls can write only the requested app change,
  repeat an unchanged failure, spend a declared amount, or attempt an invalid
  write.

The fixture is test support, not an engine: it must not be imported by the
solution runtime or another folder.  Use a real temporary Git repository for
changed-file assertions, including untracked files.

### Contract, ticket, plan, and gate units

Add focused tests for each standalone Python contract.

1. `test_contract.py` covers a missing repo or Taskfile, every missing required
   Task target, default-plus-override `.loop.yml` merging, an unknown role
   failing closed, and both the PyYAML and narrow-parser paths.  Parse pytest,
   Node-style, counts-only, skipped, missing, and coverage XML reports.  Test
   that `Contract.run` invokes the named Task target, returns combined output,
   chooses `junit-e2e.xml` for e2e, and refuses a report whose timestamp did
   not move.
2. `test_ticket.py` covers front matter, title extraction, success versus
   acceptance headings, generated and explicit AC ids, state defaults,
   `for_prompt()`, ready-file precedence, and missing tickets/directories.
3. `test_steps.py` covers JSONL round trips, malformed or incomplete lines,
   empty/duplicate/unknown-role/unknown-status plans, criterion coverage,
   required test step, evidence required before `done`, persistence after a
   mark, role filtering, and summaries.
4. `test_gates.py` covers all three exits: green rubric with no judge,
   agreeing and disagreeing judge verdicts, repeated failed signature, spent
   dollar budget, final iteration, and the narrowed final retry instruction.
5. `test_rubric.py` evaluates all ten rows with independently controlled
   evidence.  In particular pin absent/empty JUnit as failures, red-first as
   a requirement unless disabled, coverage threshold edges, criterion-to-test
   evidence, UI changes requiring an e2e report, format/lint exit failures,
   and phase-attributed write-scope violations.

### End-to-end Python loop tests, without a model

Add `test_implementer.py` and drive `implementer.run()` through the disposable
target and scripted backend.  These tests prove the sequence rather than only
the functions it calls.

1. **Happy path:** baseline is known, the first backend turn adds a new failing
   test, the next adds the implementation, all reports are green, every
   criterion gets a persisted test-id evidence link, and the trace ends in
   `pass` with all ten rubric rows.
2. **Red-gate exit:** no new failing test, an already-green test, or code
   written before a new red test must end in `escalate`; it must never enter a
   code iteration or claim green.
3. **Scope attribution:** a test-phase app write, code-phase test write,
   traversal, and an untracked out-of-scope file each reach the write-scope
   evidence.  In particular, assert that an early red-gate exit still records
   an unsafe test-phase write rather than silently dropping that evidence.
4. **Convergence and budgets:** unchanged rubric signature on the second
   attempt, exhausted iteration budget, and exhausted USD budget all stop with
   the matching reason and number of backend calls.  A non-converging backend
   must not consume the remaining iteration budget.
5. **Target preconditions and trace:** invalid contract, a draft ticket, a
   missing ticket, and a rejected plan fail closed.  A completed or early exit
   writes a compact `.harness/last-implementer.json` when requested and writes
   nothing when `write_trace=False`.

Use an injected backend rather than a shared fake driver.  The test needs to
exercise the actual `implementer.run()` control flow while remaining
deterministic and free of a model call.

### Deep Agents adapter and harness regressions

Keep the current content/usage extraction cases and add tests for the runtime
boundary that the full loop relies on:

- `DeepAgentsBackend` reports only changes made during one invocation,
  including a newly created untracked file.  `git diff --name-only` alone does
  not see that common agent output, so the test must start with a real empty
  Git repo and create an untracked test file during `invoke()`.
- An exception from `invoke()` is an `ok=False` result with no claimed writes
  or spend.  Add an explicit bounded-call/timeout design before treating a
  live agent as safe to run unattended.
- The backend must not merely filter `DoerResult.wrote` after the fact.  A
  fake graph that tries to write `app/**` during the test phase, or `tests/**`
  during the code phase, must be observable to the loop and fail the phase
  boundary.  Today `allow` is used only for reporting, so this is a
  deliberately high-value regression test for the hand-off design.
- Test `harness.cast`, `harness.red_gate`, `run_loop` forwarding, `--table-only`
  in a fresh interpreter with no Deep Agents import, and every documented
  `task` name.  All top-level modules must import without the optional SDK.

The two high-value negative tests above may require a small implementation
change: preserve untracked changes in adapter accounting and make a
test-versus-code phase enforceable rather than a reporting-only `allow` list.
The tests should describe the observable boundary; do not solve it by adding a
cross-folder orchestrator.

### Offline task UX and CI

Add a minimal `task test-setup` (or an equivalently clear documented command)
that creates this folder's virtual environment and installs only `pytest` and
`coverage`.
`task setup` may continue to add Deep Agents for live work.  `task test` must
either use the test environment or fail with an actionable one-line setup
message; it must never download an SDK or require a key.

The PR job installs only the offline test prerequisites and runs, from this
folder, `task test`, `task e2e`, and `task table`.  It must have no model
credential, no CRM checkout, and no network-dependent assertion.

## Lane 2 — offline reference-doer E2E

This is the repeatable end-to-end acceptance test.  It starts a new process at
the public solution command, runs the target's real Task targets, and uses the
existing `reference` doer rather than a fake backend.  It proves the complete
operator path without a model key or a network call:

```text
task run -- --ticket T001 --doer reference
  -> ready ticket and target contract
  -> baseline test
  -> reference copies only tests/**
  -> fresh red junit report
  -> reference copies only app/**
  -> fresh green test/e2e/lint/format reports
  -> deterministic rubric, pass trace, and scoped Git diff
```

### Disposable target fixture

`tests/e2e/test_reference_implementer.py` creates an initialized temporary Git
repository; it does not clone or alter the attendee CRM.  The fixture has two
local commits/refs:

- The checked-out starting commit contains a tiny, runnable app, one passing
  health test, valid `.loop.yml`, `Taskfile.yml`, and `T001.ready.md` with one
  precise acceptance criterion.
- A local `known-good` ref adds one test under `tests/` and the corresponding
  implementation under `app/`.  The new test fails against the starting
  commit and passes only after the app file is copied.  `ReferenceBackend`
  therefore performs the same two scoped calls that the real loop does,
  without a remote or a special test-only backend.

The target `test` task runs a real pytest test suite, writes `reports/junit.xml`
on both red and green outcomes, and uses `coverage` to write a real Cobertura
report.  Its `e2e`, `lint`, and `format-check` tasks also execute actual
commands and write the expected e2e JUnit report.  The fixture launches the
solution from its own directory using `TARGET=<temporary-repo>` and the
folder-local test interpreter; no call is made directly to an internal Python
function.

Before enabling this test, fix the currently conflicting operator contract:
`HOW_TO_RUN.md` says `--doer reference` needs no SDK, but `Taskfile.yml`'s
`run` target currently refuses whenever the Deep Agents virtualenv is absent.
The E2E preflight must establish that the pytest/coverage-only `test-setup`
environment is sufficient for `--doer reference`; only `--doer deep` may
require `task setup` and the SDK.

### Assertions and failure evidence

The E2E test fails if any of these observable conditions is false:

1. The subprocess exits zero and prints `gate: pass`; the trace contains the
   ready ticket id, one or more new `red_ids`, an explicit test-phase record
   followed by the expected code phase, and ten passing rubric rows.  Add that
   test-phase trace evidence before asserting it—the current trace records
   code iterations but not the initial test-doer result.
2. The baseline report is green, the report after the test phase is both fresh
   and red, and the final test plus e2e reports are fresh and green.  A stale
   report, empty suite, or a test that was green before app code changes fails
   the scenario.
3. `steps.jsonl` maps the ticket criterion to test and code steps, and the
   final persisted evidence names the passing test.  This asserts the planned
   proof rather than only a green exit code.
4. The Git delta contains the generated `steps.jsonl`, expected `tests/**`,
   expected `app/**`, and the optional harness trace—nothing outside the
   fixture's declared or harness-owned paths.  The code phase must not modify
   the test file copied in the red phase.
5. The trace is useful to an operator but contains no prompt transcript,
   environment values, or credential-like string.

Add focused E2E failure cases beside the happy path: a known-good ref missing
the test must stop at the red gate; a ref missing app code must exhaust or
repeat-fail without a false pass; and a known-good ref containing an
out-of-scope path must be reported as a write-scope failure.  Do not hide these
cases behind test retries.

Expose this suite as `task e2e` (for example, a selected pytest `e2e` marker)
and run it after `task test` in PR CI.  It remains folder-local and uses no
shared fixture package.  The successful E2E result should retain the temporary
trace and report XML only long enough for pytest failure diagnostics; CI can
upload them as an artifact on failure.

## Lane 3 — installed Deep Agents compatibility, no model call

Add a separately selected `sdk_compat` pytest marker and `task sdk-compat`.
It requires the folder-local virtual environment created by `task setup`; when
that environment or the package is absent, it should fail with an instruction
to run setup rather than fall back to a global package.  `task test` must not
select this marker.

Against the actual installed package, construct the graph from a temporary
contract but do not invoke it.  Assert that:

- `roles.build_agent()` accepts the installed constructors and returns a
  compiled graph;
- the four named subagents have their intended tools, response schema,
  per-role permissions, skill mount, and memory mount;
- the orchestrator's only custom tool is `run_tests`, built-in write/execute
  tools are excluded, and the general-purpose subagent is disabled;
- the default target backend plus `/skills/` and `/memory/` routes use virtual
  filesystem mode; and
- a permission object preserves deny-before-allow and a terminal
  deny-every-write rule.

Log the installed Deep Agents version in the job.  Run this lane on a schedule
and when `deepagents>=0.7.0` is deliberately upgraded, because the Taskfile
does not pin an exact release.

## Lane 4 — credentialed Deep Agents E2E

This is not a PR requirement and must never run for an untrusted fork.  After
the deterministic and compatibility lanes are green, run the exact same
disposable target through `task run -- --ticket T001 --doer deep` in a manual,
protected `task e2e-live` job (or documented operator procedure).  It is a
full ticket-loop E2E test, not merely a single-write probe.  It must:

1. Check the local SDK and API credential before creating an agent; it never
   prints credential values.
2. Uses the one-criterion temporary target from Lane 2, but without its
   `known-good` ref influencing writes.  It never touches the attendee CRM
   clone.
3. Uses a caller-controlled iteration cap, a wall-clock timeout, and a
   provider/model token or spend ceiling where supported.  If the runtime
   cannot enforce a hard dollar cap, document that fact rather than claiming
   the loop budget is a provider billing limit.
4. Verifies the complete sequence: a fresh red test before app code, final
   green target reports, a passing deterministic rubric, persisted evidence,
   and no out-of-scope Git change.  Capture role/tool activity from the
   existing scoped write and test tools so the outcome establishes that the
   Deep Agents graph actually delegated work; do not infer delegation solely
   from a green test suite.
5. Emits a redacted JSON result with package version, elapsed time, outcome,
   gate, rubric signature, observed role/tool names, changed paths, and
   reported cost.  Store it as a protected CI artifact, not in the repository.

The current implementation generates `steps.jsonl` deterministically in
Python.  The live E2E must assert that current behavior, not claim that the
planner subagent wrote the plan until the runtime actually delegates planning.
Likewise, a live failure is diagnostic evidence—not a reason to retry
automatically and spend again.

Any timeout, provider error, missing final result, out-of-scope write, or
unbounded-spend configuration is a failed live E2E.

## Delivery order and acceptance

1. Add the pytest/coverage-only bootstrap and the disposable `known-good`
   target fixture; make the reference-doer command work without Deep Agents.
2. Add the offline unit/integration tests, beginning with the highest-risk
   full-loop paths and the two adapter/phase gaps.
3. Make `task test`, `task e2e`, and `task table` pass from a fresh folder
   with no SDK/key, then add them to the PR job.
4. Add the opt-in installed-SDK compatibility marker, Task target, and
   scheduled job; record its package version.
5. Add the protected manual Deep Agents E2E only after its hard prerequisites
   and
   redacted report are in place.
6. Before merging an implementation pass, run in order:
   `task test`, `task e2e`, `task table`, `task setup && task sdk-compat`, then
   one explicitly authorized `task e2e-live` when changing graph construction,
   permissions, backend invocation, or model-facing adapter behavior.

## Explicit non-goals

- No shared `loops/` package, generic agent runner, or cross-folder test
  support.
- No real Deep Agents/model call in the normal test suite or PR workflow.
- No use of the real attendee CRM checkout in tests or smoke runs.
- No attempt to replace deterministic red/rubric/gate checks with a model
  judge.
