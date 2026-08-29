# Spec. Lab 2. Ticket Implementer and the harness, on Claude Agent SDK

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

## The cast for this loop

- `orchestrator`
- `planner`
- `test_implementer`
- `code_implementer`
- `judge`

`roleplan.py`, in this folder, is where that list lives. Read it there. Do not
restate a scope anywhere else.

Three roles write and each one writes somewhere different, which is the whole
lesson of this lab. The test implementer owns `tests/**`. The code implementer
owns `app/**` and is denied `tests/**`, so it cannot edit a failing test into
passing. The planner owns `steps.jsonl` and neither of the other two.

No role holds `Bash`. Python runs the suite through `contract.run("test")`, so
a shell buys the cast nothing and costs it the whole fence: the hook below
matches `Edit`, `Write`, and `NotebookEdit`, and none of those is `sed -i`.

## How this runtime enforces scope

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The orchestrator and the judge hold neither `Edit` nor `Write`, so for
them there is nothing left for a hook to guard.

One hook serves the whole cast, not one per writer. That distinction is the
reason this folder was rewritten. Registering one hook per writing role does
not survive three writers: every hook runs on every `Write`, an empty dict
means "no opinion", and the code implementer writing `tests/test_x.py` was
denied by its own hook and waved through by the test implementer's. The
effective scope was the union of all three allow lists, and the separation this
lab teaches did not hold at runtime.

The hook reads `agent_type` off the tool call, which the SDK populates whenever
the call comes from inside a spawned subagent, and looks up that role's scope.
A write that arrives with no `agent_type` came from the parent, and the parent
has no business writing anything.

How the CLI combines several hook opinions is not something this port can read
off the Python SDK, so it does not rely on knowing. It registers one opinion,
and `tests/test_roles.py` pins that.

## Build it step by step

1. Install the runtime.

   ```bash
   task setup
   ```

2. Read the cast before you configure anything.

   ```bash
   cd solutions/sol2_implementer_agent_sdk
   python harness.py --table-only --repo ../../work/northwind-field-crm
   ```

   The judge must print `no` in the writes column. If it prints `yes`, stop.
   Nothing downstream is worth building on that.

3. Translate the cast into this runtime, one role at a time. `cast(contract)`
   returns a `RolePlan` per role, carrying the tools, the allow list, and the
   deny list. `build(contract)` turns those into the runtime's own objects.

4. Give the writing roles their path check. A role holding `Edit` or `Write`
   without a path check can reach any file in the repo, and the first thing an
   agent under pressure reaches for is the failing test.

5. Print the configuration and read it.

   ```bash
   python harness.py --repo ../../work/northwind-field-crm
   ```

## Verify

```bash
task test
task table
```

Those checks need no SDK, no key, no network, and no clone. `task test` used to
be `harness.py --table-only`, which printed a table and asserted nothing while
this section claimed otherwise. It runs pytest now, and the suite asserts:

- The cast is exactly the five implementer roles, and the judge and the
  orchestrator hold no write path.
- The code implementer is denied `tests/**` and the test implementer is not.
- One write produces exactly one hook opinion, and a write with no
  `agent_type` is denied.
- No role holds `Bash`, and `Bash` is denied at the options level.
- `maxTurns` reaches the SDK, not `max_turns`, which raises `TypeError` on the
  real thing. The fake in `conftest.py` is an explicit dataclass for that
  reason: a `**kwargs` fake accepts any spelling and hides the bug.
- The adapter reads a `ResultMessage`, reports what a turn cost, and sees a
  brand new untracked file.
- Every module imports with no SDK installed.
- Every `task` this document names exists in the Taskfile.
- `task setup` creates `.venv` in this folder. Homebrew Python will not let pip write to the system interpreter.

The live operator path is [HOW_TO_RUN.md](HOW_TO_RUN.md). This folder is the
cast, not the driver. `task run` prints this runtime's options. It does not
drive tickets.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a
shared engine.

It is not the driver. There is no `implementer.py`, no `gates.py`, and no
`rubric.py` here, and that is deliberate. This folder is the cast, the write
scope, and the runtime wiring. The working Lab 2 loop lives in
`sol2_implementer_deep_agents`, and Saturday Lab 2 is `labs/lab2_implementer`.

An earlier docstring pointed `backend()` at `loops.implementer.run(...)`. That
package was deleted in #130.
