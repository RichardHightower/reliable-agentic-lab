# E2E plan. sol2 Agent SDK on T001

Date: 3 September 2026.
Folder under test: `solutions/sol2_implementer_agent_sdk`.
Issue: #287.
Branch: `feat/sol2-loop-engineering`.

Saturday Lab 2 stays `labs/lab2_implementer`.
Do not invent a shared `loops/` package.
This folder owns the loop. `implementer.py` lives here.

## What e2e means here

A ready ticket goes in. The harness plans, writes tests, trips the red gate,
writes code, scores the rubric, asks the judge, and exits.

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

## What the loop will do to T001

`implementer.run` is eight steps. Python owns every gate.

1. Load T001 ready. Refuse if it is still a draft.
2. Derive `steps.jsonl`. One test step and one code step per AC.
3. Test implementer writes under `tests/**` only.
4. Red gate. New failing ids in `reports/junit.xml`. No new red test means
   escalate. Stop. Do not write app code.
5. Code implementer writes under `app/**` only. Denied `tests/**`. A retry
   carries `gates.retry_instruction` plus the failing test ids.
6. Rubric. Ten rows. No model.
7. After a green rubric the judge subagent answers in JSON. Unparseable is
   `done=False`. Green plus `judge_done=False` is escalate.
8. `gates.decide`. Pass, retry, or escalate. Same signature twice means stop.

`implementer.run` calls the backend twice for the makers, then once for the
judge. Attribution is by which files appeared in which phase, not by
`result.wrote`.

## Worktree

```bash
git fetch origin feat/sol2-loop-engineering
git worktree add /tmp/lab-sol2-test feat/sol2-loop-engineering
```

```
/tmp/reliable-agentic-lab          main
/tmp/lab-sol2-test                 feat/sol2-loop-engineering
/tmp/lab-sol2-test/work/northwind-field-crm
```

Key goes in `/tmp/lab-sol2-test/.env`. Task loads `../../.env` first.

## Layer E0. Fixture proof. No Agent SDK

From `solutions/sol2_implementer_agent_sdk`:

```bash
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
code phase. No `tests/**` write in the code phase. Judge ran. Receipt at
`$CRM/.harness/receipt.json`.
Trace: `$CRM/.harness/last-implementer.json`.

If E0b escalates on the red gate, that is a fixture bug. Fix it before any
SDK call.

## Layer E1. Offline loop. No model

```bash
python3 -m pytest tests -q
task setup
task table
task e2e
```

Pass: pytest green, table prints `judge` / `no`, `task e2e` is the
scripted-backend loop. Fail: a `sys.path` bridge back to Deep Agents, or
a Taskfile task the docs name that does not exist.

## Layer E2. Operator path for the SDK folder

```bash
python3 -m pytest tests -q
task setup
task table
```

## Layer E3. Live T001. Costs money

Cap it. One ticket. One budget. Hard wall 420 seconds.
`E2E_MAX_TURNS` is the same as `DEFAULT_MAX_TURNS` (12). A ceiling of 2
cannot go green.

```bash
CRM=/tmp/lab-sol2-test/work/northwind-field-crm
git -C $CRM checkout --force main && git -C $CRM clean -fd
cd /tmp/lab-sol2-test/solutions/sol2_implementer_agent_sdk
timeout 420 .venv/bin/python e2e_t001.py --repo $CRM --ticket T001 --budget 1
```

Or, same loop through Task:

```bash
task run -- --ticket T001 --doer sdk
```

Watch six things: query started, no `app/**` in the test phase, no `tests/**`
in the code phase, output is not a Grep dump, `usd` is not zero, the run stops.

First live attempt is not required to reach `gate: pass`.
Honest escalate on red gate, cost, or max turns is a pass if the fence held.
Hang, traceback, or a code-phase write to `tests/**` is a fail.

## What we will not do

- A shared `loops/` package.
- Saturday `labs/lab2_implementer`.
- Importing `sol2_implementer_deep_agents` at runtime.
- Spending a key before E0b is green.

## When this earns a PR

`implementer.py` lives here. `e2e_t001.py` does not import the sibling
folder. Offline pytest is green. E0a and E0b have traces. A failing live
fence is still a result.
