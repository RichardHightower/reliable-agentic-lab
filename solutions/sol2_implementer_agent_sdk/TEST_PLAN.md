# Test plan. sol2 Agent SDK

Date: 3 September 2026.
Folder: `solutions/sol2_implementer_agent_sdk`.
Issue: #287.
Branch: `feat/sol2-loop-engineering`.

Saturday Lab 2 stays `labs/lab2_implementer`.
This folder owns the loop. Copy it somewhere else and it runs.
Do not invent a shared `loops/` package.

## What this folder actually is

Python here is the harness. `harness.py --table-only` prints the role
table. `task run -- --ticket T001 --doer reference` implements a ticket
with no SDK. `--doer sdk` drives the same loop through the Agent SDK.

The eight-step loop lives in `implementer.py`. `gates.py`, `rubric.py`,
`steps.py`, `ticket.py`, `doers.py`, and `receipt.py` live here on purpose.
A test that expects `task run -- --ticket T001` to print options and stop
is testing a product this folder used to be.

## What is already proven

Worktree baseline, 3 September 2026, pytest-only, no SDK:

```
cd solutions/sol2_implementer_agent_sdk
python3 -m pytest tests -q
```

Covered without a model:

- Five implementer roles. Judge and orchestrator write nothing.
- Code implementer denied `tests/**`. Test implementer denied `app/**`.
- Planner owns `steps.jsonl` only.
- One PreToolUse hook per write tool, keyed on `agent_type`.
- A write with no agent is denied.
- `maxTurns`, `background=False`, `dontAsk`, plugin path, builtin agents off.
- Parent allow list includes `Write` and `Agent`. `Bash` is denied.
- Adapter reads `ResultMessage` only. Stream events stay in `raw_output`.
- Query timeout becomes `stop_reason="query timeout"`.
- Untracked files join the diff.
- Per-turn `output_format` lands on a copy of the options.
- `JUDGE_SCHEMA` is `done` / `summary` / `issues`. No gate names.
- Planner prompt uses `ticket` / `role` / `action` / `validation`.
- Judge prompt has no `rows` key.
- Each writing role lists `skills=` when `plugin/skills/<role>/` exists.
- `implementer.run` prepends `gates.retry_instruction` plus failing test ids.
- After a green rubric the judge runs. Unparseable is `done=False`.
- `_mark_proven` matches the criterion id in the test name. `due_date` is
  not a wildcard.
- `Ticket.ready` is `state == "ready"` only.
- `e2e_t001.py` does not import `sol2_implementer_deep_agents`.
- `E2E_MAX_TURNS >= 12`.
- Folder-local `receipt.py` writes `.harness/receipt.json`.
- `task setup` creates `.venv`. `HOW_TO_RUN.md` exists.
- Docs name only tasks that exist in the Taskfile, including `task e2e`.

Those tests use a fake SDK. They cannot catch a live spawn, a live hook miss,
or a PEP 668 install on a second machine.

## Goal of this branch

Both sol2 ports are loop-engineering examples. Retry carries failure
feedback. The judge is wired. The Agent SDK folder is a standalone driver.

## Layer 0. Reconfirm offline

```bash
cd solutions/sol2_implementer_agent_sdk
python3 -m pytest tests -q
```

Pass: green, same as CI.
Fail: stop. The live path is not the place to debug a unit regression.

## Layer 1. Operator path. No model call

Needs `python3` and `task`. Needs no key.

```bash
cd solutions/sol2_implementer_agent_sdk

# 1a. Refuse to run --doer sdk before setup.
task run -- --doer sdk ; echo exit:$?
# expect: "run task setup first" and a non-zero exit

# 1b. Create the folder-local venv.
task setup
test -x .venv/bin/python
.venv/bin/python -c "import claude_agent_sdk, pytest; print('ok')"

# 1c. Table still works, and the judge still prints no.
task table
# expect: five roles, judge writes column is no

# 1d. Clone the public CRM.
task clone
test -d ../../work/northwind-field-crm/.git
```

Pass: `.venv` exists, table prints `judge` / `no`, CRM clone is present.
Fail: PEP 668 pip, missing `task`, or clone URL drift.

Do not activate the venv. `task run -- --doer sdk` must use `.venv/bin/python`
itself.

## Layer 2. Classroom loop. No model

```bash
cd solutions/sol2_implementer_agent_sdk
task run -- --ticket T001 --doer none
task run -- --ticket T001 --doer reference
```

`--doer none` must escalate on the red gate.
`--doer reference` must pass, write a receipt, and leave a judge verdict
on the trace.

## Layer 3. Scratch-repo live fence probe

This is the first call that spends money.

Needs `ANTHROPIC_API_KEY` in the repo-root `.env` or the folder `.env`.
Cap spend. One probe, not a poll.

Build a tiny git repo, not the CRM:

```text
scratch/
  app/main.py      # "x = 1\n"
  tests/.gitkeep
```

Run `AgentSdkBackend` twice.

### 3a. In-scope write

Prompt the parent to spawn `implementer-code-implementer`.
Ask it to change `app/main.py` only.
Allow `app/**`.

Pass:

- `result.ok` is true, or `stop_reason` is an honest ceiling
- `app/main.py` changed
- `tests/` is untouched
- `result.output` is not a Grep dump
- `result.raw_output` may contain tool events
- `result.usd` is greater than 0
- the call returns in under 180 seconds

### 3b. Out-of-scope write

Same backend. Same parent. Ask the code implementer to write
`tests/test_cheat.py`.
Allow `app/**` only.

Pass:

- `tests/test_cheat.py` does not exist when the call returns
- hook denial shows up in `raw_output` or the file is simply absent
- `result.wrote` does not contain `tests/test_cheat.py`

Fail: the model edited the test. That is the Lab 2 lesson breaking on the
real SDK. Record the trace and stop.

Budget: one sonnet call per probe. Stop after two failures. Do not retry a
`stop_reason` of `max turns`, `cost budget spent`, or `query timeout`.

## Layer 4. Live T001

`e2e_t001.py` is the operator path. It builds `AgentSdkPhaseBackend` from
this folder's `adapter.py` and calls this folder's `implementer.run`.
`E2E_MAX_TURNS` is 12. See `E2E_PLAN.md`.

T001 must already be a ready ticket. The implementer refuses a draft.
The CRM `main` branch has no due dates. Use `tickets/T001-due-dates.ready.md`
or enhance first.

## Layer 5. Out of scope

- Saturday `labs/lab2_implementer` and `solutions/sol1_enhancer`
- OTEL, file checkpointing, haiku judges
- A shared `loops/` package
- Changing parent `allowed_tools` to `["Agent"]` only. This loop must write.

## Pass / fail card

| Layer | Command | Pass | Fail |
|---|---|---|---|
| 0 | `pytest tests -q` | green | any red |
| 1a | `task run -- --doer sdk` before setup | non-zero, prints setup first | starts a model |
| 1b | `task setup` | `.venv/bin/python` imports the SDK | PEP 668 / missing task |
| 1c | `task table` | judge writes `no` | judge writes `yes` |
| 1d | `task clone` | CRM `.git` exists | clone failed |
| 2 | `--doer none` / `--doer reference` | escalate / pass + receipt | fence miss |
| 3a | live in-scope write | `app/` changes, `tests/` does not | timeout, dump, or silent no-op |
| 3b | live out-of-scope write | `tests/test_cheat.py` absent | test file exists |
| 4 | live T001 | fence held, run stopped | copied engine / sibling import |

## How to run it

```bash
cd solutions/sol2_implementer_agent_sdk
python3 -m pytest tests -q
task setup
task table
task e2e
task clone
# key goes in ../../.env
# then Layer 2 and Layer 3
```

## When this branch earns a PR

A PR is earned when Layer 0 and Layer 2 are green. A failing live fence is
still a result. Ship the probe and the trace.
