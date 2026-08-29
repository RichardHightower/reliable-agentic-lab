# E2E plan. sol2 Agent SDK on T001

Date: 28 August 2026 evening.
Main: `02fbb50`.
Folder under test: `solutions/sol2_implementer_agent_sdk`.
Driver that owns the loop: `solutions/sol2_implementer_deep_agents`.
Issue: #222.
Branch: `test/sol2-agent-sdk-live`.

Saturday Lab 2 stays `labs/lab2_implementer`.
Do not invent a shared `loops/` package.
Do not copy `implementer.py` into the Agent SDK folder on this branch.

## What e2e means here

A ready ticket goes in. The harness plans, writes tests, trips the red gate,
writes code, scores the rubric, and exits.

The object is T001, due dates on a sales task. Seven acceptance criteria.
Fixture is the public CRM.

```
https://github.com/RichardHightower/northwind-field-crm
```

| Ref | What it is |
|---|---|
| `main` | no due dates |
| `known-good` | green due-date implementation |
| `tickets/T001.md` | draft. The enhancer's input. |
| `tickets/T001-due-dates.ready.md` | ready contract. `state: ready`. AC-1 through AC-7. |

`ticket.load(..., prefer_ready=True)` picks the ready file. That is the
implementer default. Loading the draft makes the loop refuse.

The Agent SDK folder cannot run that loop by itself. `task run` prints
`ClaudeAgentOptions`. There is no `implementer.py` here. E2E is this folder's
`AgentSdkBackend` plugged into the Deep Agents driver.

## The plug-in is not drop-in today

`HOW_TO_RUN.md` says hand `AgentSdkBackend` to the Deep Agents driver.
`doers.build` does this:

```python
if isinstance(spec, Backend):
    return spec
```

`Backend` is `sol2_implementer_deep_agents.doers.Backend`.
`AgentSdkBackend` subclasses `sol2_implementer_agent_sdk.adapter.Backend`.
Those are different classes. `isinstance` is false. `doers.build` then treats
the object as a string and builds a `CliBackend`. That is a live miss, not a
doc miss.

Both folders also ship `adapter.py`, `harness.py`, `contract.py`, `roles.py`.
Putting both on `sys.path` shadows one of them. A glue script must load one
folder as `sys.path` and the other by file path.

E2E therefore starts with a 20-line wrapper, not with T001.

## What the loop will do to T001

`implementer.run` is eight steps. Python owns every gate.

1. Load T001 ready. Refuse if it is still a draft.
2. Derive `steps.jsonl`. One test step and one code step per AC.
3. Test implementer writes under `tests/**` only.
4. Red gate. New failing ids in `reports/junit.xml`. No new red test means
   escalate. Stop. Do not write app code.
5. Code implementer writes under `app/**` only. Denied `tests/**`.
6. Rubric. Ten rows. No model call.
7. Final model judge exists and is not wired. `judge_done` stays `None`.
   That is #190. A green rubric is enough. Do not treat that as an SDK bug.
8. `gates.decide`. Pass, retry, or escalate. Same signature twice means stop.

`implementer.run` calls the backend twice. First call is the test phase.
Second call is the code phase. Attribution is by which files appeared in
which phase, not by `result.wrote`.

## Worktree

```bash
git fetch origin test/sol2-agent-sdk-live
git worktree add /tmp/lab-sol2-test test/sol2-agent-sdk-live
```

```
/tmp/reliable-agentic-lab          main
/tmp/lab-sol2-test                 test/sol2-agent-sdk-live
/tmp/lab-sol2-test/work/northwind-field-crm
```

Key goes in `/tmp/lab-sol2-test/.env`. Task loads `../../.env` first.

## Layer E0. Fixture proof. No Agent SDK

From `solutions/sol2_implementer_deep_agents`:

```bash
cp config.json.example config.json
task setup
task clone
git -C ../../work/northwind-field-crm fetch origin
git -C ../../work/northwind-field-crm rev-parse --verify --quiet origin/known-good^{commit}
test -f ../../work/northwind-field-crm/tickets/T001-due-dates.ready.md
```

Reset before every run.

```bash
CRM=../../work/northwind-field-crm
git -C $CRM checkout --force main
git -C $CRM clean -fd
```

**E0a. Honest failure.**

```bash
task run -- --ticket T001 --doer none
```

Pass: `gate: escalate`. Reason names the red gate. `app/` and `tests/`
unchanged except `steps.jsonl`.

**E0b. Classroom path.**

```bash
git -C $CRM checkout --force main && git -C $CRM clean -fd
task run -- --ticket T001 --doer reference
```

Pass: `gate: pass`. Tests appear in the test phase. App files appear in the
code phase. No `tests/**` write in the code phase.
Trace: `$CRM/.harness/last-implementer.json`.

If E0b escalates on the red gate, that is a fixture bug. Fix it before any
SDK call.

## Layer E1. Wrapper. No model

Add `solutions/sol2_implementer_agent_sdk/e2e_t001.py` on this branch.

Rules for that file:

- `sys.path` gets the Deep Agents folder only.
- Load `adapter.py` from this folder with `importlib.util.spec_from_file_location`.
- Wrap `AgentSdkBackend` in a `doers.Backend` subclass so `doers.build`
  accepts it.
- CLI: `--repo`, `--ticket`, `--budget`, `--table-only`.
- Call `implementer.run(repo=..., ticket_id=..., doer=wrapper, budget=...)`.
- Print `gate`, `reason`, and the rubric.
- Do not import `solutions`. Do not import `loops`.

Pin the wrapper with a unit test that does not need the SDK.
Pass: `doers.build(wrapper) is wrapper`.
Fail: `CliBackend` comes back.

## Layer E2. Operator path for the SDK folder

```bash
python3 -m pytest tests -q
task setup
task table
```

## Layer E3. Live T001. Costs money

Cap it. One ticket. One budget. Hard wall 420 seconds.

```bash
CRM=/tmp/lab-sol2-test/work/northwind-field-crm
git -C $CRM checkout --force main && git -C $CRM clean -fd
cd /tmp/lab-sol2-test/solutions/sol2_implementer_agent_sdk
timeout 420 .venv/bin/python e2e_t001.py --repo $CRM --ticket T001 --budget 1
```

Watch six things: query started, no `app/**` in the test phase, no `tests/**`
in the code phase, output is not a Grep dump, `usd` is not zero, the run stops.

First live attempt is not required to reach `gate: pass`.
Honest escalate on red gate, cost, or max turns is a pass if the fence held.
Hang, traceback, or a code-phase write to `tests/**` is a fail.

## What we will not do

- Teach Agent SDK `task run` to drive tickets on this branch.
- Copy `implementer.py` onto this branch.
- A shared `loops/` package.
- Saturday `labs/lab2_implementer`.
- Wiring the model judge into `gates.decide` (#190).
- Spending a key before E0b is green.

## When this earns a PR

`e2e_t001.py` exists. Wrapper test is green. E0a, E0b, and E3 have traces.
A failing live fence is still a result.
