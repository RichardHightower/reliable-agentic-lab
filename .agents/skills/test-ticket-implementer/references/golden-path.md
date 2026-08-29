# Shared T001 implementer E2E golden path

Use one public CRM clone and one ready ticket, `T001`. This procedure tests the
loop, not a particular vendor SDK. It has two tracks:

- **Track A — free and deterministic.** `none` proves the red gate fails
  honestly; `reference` proves the fixture, reports, scope accounting, rubric,
  and receipt.
- **Track B — bounded live runtime.** Run each real runtime once against the
  same reset clone. A green implementation is ideal. A clean `escalate` caused
  by the red gate, the configured cost limit, or a model max-turn ceiling is a
  valid harness exit. A transport/query timeout, crash, missing receipt, or
  phase-scope violation is not.

## 1. Worktrees and the one clone

Current canonical worktrees:

| Runtime | Worktree | Branch |
| --- | --- | --- |
| Deep Agents | `/tmp/reliable-agentic-lab-sol2-test` | `test/sol2-deep-agents-live` |
| Agent SDK | `/tmp/lab-sol2-test` | `test/sol2-agent-sdk-live` |

Set the only CRM clone path once:

```bash
CRM=/tmp/reliable-agentic-lab-sol2-test/work/northwind-field-crm
```

For a new runtime, create a separate solution worktree/branch but point its
live wrapper at this same `$CRM`. Do not run a second `task clone` from the new
worktree.

## 2. Receipt contract

The required receipt is:

```text
$CRM/.harness/last-implementer.json
```

It must record `ticket` (`T001`), `doer`, all `AC-1` through `AC-7`, a
fourteen-step plan (`S1T` through `S7C`), `red_ids`, `gate`, one-sentence
`reason`, and `written_at`. Runtime-specific artifacts may sit beside it under
`.harness`, but must be redacted.

Inspect the receipt without printing secrets:

```bash
jq '{ticket,doer,criteria,plan,red_ids,gate,reason,iterations,written_at}' \
  "$CRM/.harness/last-implementer.json"
```

## 3. Prepare the deterministic driver

Run these commands from the Deep Agents worktree:

```bash
cd /tmp/reliable-agentic-lab-sol2-test/solutions/sol2_implementer_deep_agents
cp -n config.json.example config.json
task setup
task test
task clone
git -C ../../work/northwind-field-crm fetch origin
git -C ../../work/northwind-field-crm rev-parse --verify origin/known-good
```

`config.json` is local operator configuration; do not commit it. If the CRM
does not yet have its own test environment, run `task setup` inside `$CRM` and
verify `task test` before Track A. A failing fixture is a stop condition, not a
reason to spend on Track B.

Before every track/runtime, reset only the disposable clone and retain
receipts:

```bash
git -C "$CRM" checkout --force main
git -C "$CRM" clean -fd -e .harness
```

Never aim `git clean` at the seminar repository or a worktree root.

## 4. Track A — run once

From the Deep Agents solution folder:

```bash
task run -- --ticket T001 --doer none
```

The command exits non-zero because `gate: escalate` is expected. The receipt
must show `doer: none`, empty `red_ids`, and the red-gate reason.

Reset `$CRM`, then run:

```bash
task run -- --ticket T001 --doer reference
```

This must pass the full deterministic rubric. For the current fixture, seven
tests become red before code. Verify that test-phase writes are under
`tests/**`, code-phase writes are under `app/**`, and the code phase did not
write `tests/**`. If this reference path fails, stop: the fixture or driver is
broken.

## 5. Operator credentials for Track B

The primary checkout has the operator `.env`; disposable worktrees do not
inherit it. Never copy or print it. Before a direct live command, export it in
that shell only:

```bash
set -a
source /Users/richardhightower/clients/spillwave/src/seminar_harness_loop_graph_engineering/reliable-agentic-lab/.env
set +a
```

For a direct Python wrapper, load credentials in this precedence order when
they are present: solution folder `.env`, its parent, then its worktree root.
An already-exported value wins. A new worktree normally still needs the
temporary export above because the primary checkout is not its ancestor.

## 6. Track B — Deep Agents

Reset `$CRM`, then run exactly one bounded attempt:

```bash
cd /tmp/reliable-agentic-lab-sol2-test/solutions/sol2_implementer_deep_agents
timeout 420 task run -- --ticket T001 --doer deep --budget 1
```

Verify all of the following:

- a fresh receipt exists before the outer timeout;
- the test graph cannot invoke the code implementer and the code graph cannot
  write tests;
- `red_ids`, `gate`, and any `scope_violations` truthfully describe the run;
- `git diff --name-status` and `git status --short` show no out-of-scope
  changes; and
- a clean red-gate or controlled max-turn/cost escalation has no code-phase
  `tests/**` write.

## 7. Track B — Agent SDK

Do not begin until its local suite proves the wrapper backend is passed through
unchanged (`doers.build(wrapper) is wrapper`) and the runtime's real SDK
configuration can be constructed without making a model call.

Reset the same `$CRM`, then run:

```bash
cd /tmp/lab-sol2-test/solutions/sol2_implementer_agent_sdk
timeout 420 .venv/bin/python e2e_t001.py \
  --repo /tmp/reliable-agentic-lab-sol2-test/work/northwind-field-crm \
  --ticket T001 \
  --budget 1
```

The wrapper must create redacted files such as
`.harness/last-sdk-e2e.md` and `.harness/last-sdk-e2e-diff.txt`. Check that:

- only the named phase subagent is present in each live SDK configuration;
- a terminal `max turns` or `cost budget spent` result is a controlled stop;
- `query_failed: true`, a raw SDK query timeout, or an SDK crash is a failed
  query even if a generic receipt exists; and
- the hook audit contains paths and agent names only—never prompts, raw model
  events, or credentials.

## 8. Verdicts and cleanup

| Result | Verdict |
| --- | --- |
| Fresh receipt; `gate: pass`; correct phase scope | Pass |
| Fresh receipt; clean `escalate` from red gate, cost, or max turns; correct phase scope | Harness pass |
| Code phase writes `tests/**`, or test phase writes `app/**` | Fail |
| Outer timeout or crash with no fresh receipt | Fail |
| SDK `query_failed: true` or query timeout | Failed query; not a loop exit |

After inspecting the result, leave the clone clean but retain evidence:

```bash
git -C "$CRM" checkout --force main
git -C "$CRM" clean -fd -e .harness
```

When code changes are needed, add a regression test first, rerun the local
suite, then run one new bounded live attempt. Keep each runtime's fixes and
tests inside its own solution folder.
