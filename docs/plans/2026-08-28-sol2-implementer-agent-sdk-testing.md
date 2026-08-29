---
date: 2026-08-28
slug: sol2-implementer-agent-sdk-testing
title: Test the Lab 2 Claude Agent SDK configuration port
git_base: "04e2a5a88eaf60d32b6314b31a5361f3a867148d"
branch: codex/sol2-agent-sdk-test-plan
---

# Test plan: `sol2_implementer_agent_sdk`

## Purpose and boundary

This folder is the Lab 2 *Agent SDK configuration port*: its role table,
subagent definitions, write fence, and adapter.  It needs an end-to-end test
of that port, not just configuration assertions.  The E2E runner will be a
small, hard-coded Lab 2 acceptance scenario local to this folder.  It is not a
shared ticket-loop driver and must not be imported by another solution.

## Starting snapshot

- The worktree is `/private/tmp/reliable-agentic-lab-sol2-agent-sdk-test-plan`
  on `codex/sol2-agent-sdk-test-plan`, created from `origin/main` at
  `04e2a5a`.
- The folder currently has 48 deterministic tests: 30 role/scope tests, 10
  adapter tests, and 8 harness tests.  They replace the SDK with an explicit
  `sys.modules` fake and make no network or credential calls.
- `task table` succeeds without a target clone and shows the judge and
  orchestrator as non-writing roles.
- This fresh worktree has no `pytest` available, so `task test` currently
  stops with `No module named pytest`.  That is an environment bootstrap
  prerequisite, not evidence of a failing product assertion.  Do not run
  `task setup` or a credentialed query until the implementation pass begins:
  setup installs the SDK, and a live query can incur cost.

## Testing lanes

| Lane | What it proves | Dependencies | Where it runs |
| --- | --- | --- | --- |
| Offline unit | Role declarations, deny-by-default scope, adapter result handling, write accounting, and standalone imports | `pytest` only | Every PR and local `task test` |
| Installed-SDK compatibility | The installed `claude-agent-sdk` still accepts the options and agent-definition fields the port emits | Folder-local venv and SDK; no credentials | Scheduled CI and before an SDK upgrade |
| Fixture E2E | The complete Lab 2 scenario reaches red, scoped writes, green unit/e2e checks, and a durable report | `pytest` only | Every PR and local `task e2e-fixture` |
| Live E2E | The identical scenario runs through named real Agent SDK subagents and observes their real hook calls | SDK plus `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | Manual/protected dispatch only |

The official SDK currently bundles the Claude Code CLI when installed and
supports `query()` for one-shot queries.  It supports an SDK budget ceiling
and accepts environment-based API-key or OAuth authentication.  The plan uses
those documented boundaries rather than requiring a separately installed
global CLI.  The current reference illustrates `AgentDefinition(max_turns=…)`,
while this port deliberately uses `maxTurns` to match the SDK version for
which it was written; the installed-SDK check below is the authority on that
version-sensitive boundary.

## Lane 1 — keep the offline suite authoritative

The existing suite is the release gate.  It must remain runnable with only
`pytest`; no SDK, API key, target CRM clone, or network is allowed in this
lane.  Keep the current checks and add regressions only when a concrete bug is
found:

1. `task test` runs all 48+ tests; `task table` separately verifies the
   copy/paste attendee command.
2. The scope matrix verifies every writer's one allowed path and prohibited
   paths, parent/no-agent writes, traversal, out-of-repo paths, all three write
   tool names, and the exact deny envelope.  The test must continue to assert
   one registered hook opinion per write tool, not merely one closure in
   isolation.
3. Adapter tests keep using a real temporary Git repo and fake streaming
   messages.  They cover final `ResultMessage` extraction, cost and ceiling
   propagation, error status, timeout, raw diagnostics, immutable per-turn
   options, and both tracked and untracked changed files.
4. Harness tests retain the fresh-interpreter/no-SDK import checks and ensure
   the Taskfile and operator docs name only commands that exist.

This lane supplies the negative-path proof.  A live model is not a reliable
way to prove a denial: it may simply decline to try an invalid write.  The
direct hook tests deterministically exercise all deny branches instead.

## Lane 2 — installed-SDK compatibility check (no model call)

Add a separate, explicitly selected `sdk_compat` pytest marker and a
`task sdk-compat` target.  It should fail with a clear “run `task setup`”
message when the folder-local venv is absent, rather than silently using a
global package.  `task test` must not select this marker.

After `task setup`, the compatibility test will build a `Contract` from the
existing temporary-repo fixture and call `roles.options_for(contract)` against
the real installed module.  It will assert without calling `query()` that:

- the result and nested definitions are actual SDK types;
- the four subagents are loaded from the local plugin and receive camel-case
  `maxTurns` plus `background=False`;
- the parent options include every declared role tool, deny `Bash`, disable the
  built-in agents, set the local plugin and project setting source, and carry
  the contract budget;
- `PreToolUse` contains exactly one real `HookMatcher` for each of `Edit`,
  `Write`, and `NotebookEdit`; and
- invoking the callback directly still returns the SDK's documented denial
  envelope for an out-of-scope write.

Record the installed package version in the compatibility job log.  The
Taskfile currently installs an unpinned latest SDK, so this check should run on
a schedule (and during an intentional dependency upgrade) even if PR CI stays
deliberately dependency-free.

## Lanes 3 and 4 — one E2E scenario, fixture and live backends

Add `e2e.py`, `e2e/`, `task e2e-fixture`, and `task e2e-live` inside this
folder.  The script owns one explicit eight-step Lab 2 scenario; it is neither
a reusable framework nor an importable engine.  Both modes create a fresh,
disposable Git repository and execute the same sequence:

1. Create a ready `T001` ticket for one small public behavior, a minimal app
   whose initial behavior is wrong, a target `Taskfile.yml`, and `.loop.yml`.
   The target has separate `test` and `e2e` tasks that emit JUnit reports.
2. Have the planner produce `steps.jsonl`, then validate that its steps cover
   the ticket criterion and name the test and code roles.
3. Have the test implementer create a new unit test under `tests/unit/`.  Run
   `task test` from Python, parse `reports/junit.xml`, and require a *new*,
   assertion-based failing test before code is touched (the red gate).
4. Have the code implementer fix only `app/`.  Run `task test`, `task e2e`,
   `task lint`, and `task format-check` after the write.
5. Score fixed postconditions: the new test and the independent black-box E2E
   test are green; the planner changed only `steps.jsonl`; the test phase
   changed only the new `tests/unit/` file; the code phase changed only
   `app/`; and the pre-existing E2E assertion was not edited.
6. Ask the configured judge for its JSON verdict after Python has collected
   the evidence.  Its verdict is recorded but never overrides the deterministic
   acceptance result.

### Fixed acceptance scenario

The disposable target contains `app/due_state.py` with public
`due_state(date, today)`.  Its initial implementation returns the wrong state
for a past date.  `T001.ready.md` requires an `overdue` state only when `date`
is before `today`; equality and a future date are not overdue.

- The test implementer must add `tests/unit/test_due_state.py`.  The target's
  `test` task runs only `tests/unit` and writes `reports/junit.xml`, allowing
  the runner to prove that this *new* test became red before any app edit.
- The pre-existing immutable `tests/e2e/test_due_state_contract.py` calls only
  the public function for past, present, and future dates.  The target's `e2e`
  task runs that directory and writes `reports/junit-e2e.xml`.  It may fail at
  baseline, but it must be green after the code phase and byte-for-byte
  unchanged throughout the run.
- `lint` uses `py_compile` and `format-check` verifies the one generated app
  file's newline/encoding.  The target needs only Python and `pytest`, keeping
  the fixture E2E free of a CRM clone, a model, `ruff`, or another dependency.

The exact implementation is not snapshotted.  The public E2E behavior, JUnit
reports, phase-specific diffs, and the red gate are the acceptance oracle.

`e2e.py --mode fixture` uses a scenario-local scripted backend that performs
the planner, test, code, and judge responses in that order.  It executes the
real target tasks and validates the same on-disk reports and diffs as live
mode, so it is a deterministic PR acceptance test rather than a mock-only unit
test.  The scripted backend lives in `e2e.py`; it is not exported or shared.
`tests/test_e2e.py` calls this fixture mode with `tmp_path` and asserts the
report passes, so the existing GitHub Actions `python -m pytest tests -q` step
already makes the E2E test required.  `task e2e-fixture` is the attendee-facing
command for running the same scenario outside pytest.

`e2e.py --mode live` uses `AgentSdkBackend` and this folder's actual
`ClaudeAgentOptions`.  Each query explicitly names the intended custom
subagent (`implementer-planner`, `implementer-test-implementer`,
`implementer-code-implementer`, then `implementer-judge`), and an audit wrapper
around the existing `PreToolUse` hook records tool, path, and `agent_type`.
Live acceptance additionally requires that the expected named writer produced
the observed allowed write.  The run has a hard total cap of `$2.00` by default
and divides that cap across its four queries; the caller may lower but never
raise the cap.  A missing SDK, missing credential, timeout, SDK error, maximum
turns, or cost ceiling fails before a pass can be reported.

Both modes write a redacted `e2e-report.json` containing the phase outcomes,
JUnit counts, changed paths, hook audit metadata, package version, spend, and
exit reason.  It excludes credentials, prompts, raw model output, and target
file contents.  Fixture reports are test artifacts; live reports are uploaded
from the protected job and never committed.

## CI and acceptance sequence

1. Keep the current GitHub Actions folder matrix as the required PR gate:
   install only `pytest` and run `python -m pytest tests -q`; the new
   `tests/test_e2e.py` invokes fixture E2E from that command.  No secret is
   exposed, and a missing E2E runner cannot look green by being skipped.
2. Add a scheduled `sdk-compat` job that creates the folder-local venv,
   installs the documented SDK, and runs `task sdk-compat`.  It catches SDK
   API drift without model spend.
3. Add a manual `workflow_dispatch` live-E2E job guarded by a protected
   environment and a spend-cap input that cannot exceed the task's `$2.00`
   hard cap.  It must never run for forked pull requests.
4. Before merging the implementation, verify in order: `task test`, `task
   table`, `task e2e-fixture`, `task setup && task sdk-compat`, then one
   explicitly authorized `task e2e-live`.  A real E2E run is optional for
   ordinary doc/test-only changes; it is required when changing options, hooks,
   agent definitions, adapter streaming behavior, or the E2E scenario.

## Work items for the implementation pass

- [ ] Add the real-SDK, no-query compatibility fixture, marker registration,
  and `task sdk-compat` command.
- [ ] Make missing venv/SDK failures actionable while preserving the current
  no-SDK `task test` contract.
- [ ] Implement `e2e.py` and its disposable due-state target, including the
  red gate, phase-specific diff fences, JUnit parsing, and redacted report.
- [ ] Add `task e2e-fixture`, make it a mandatory PR check, and add regression
  tests for a deliberately red gate, a scope violation, and a missing JUnit
  report.
- [ ] Implement `task e2e-live` with real named SDK subagents, hook auditing,
  and the fixed total budget.
- [ ] Add scheduled compatibility and protected manual live-E2E workflows.
- [ ] Run the acceptance sequence, capture the package version and live report
  as CI artifacts, and update `HOW_TO_RUN.md` with the two opt-in commands.

## Explicit non-goals

- No shared `loops/` package, generic agent runner, or cross-folder helper.
- No credentialed test in the PR matrix and no automatic model spend.
- No production ticket driver: `e2e.py` is one disposable, hard-coded
  acceptance scenario and stops at the report; it is not a user-facing loop
  command.
