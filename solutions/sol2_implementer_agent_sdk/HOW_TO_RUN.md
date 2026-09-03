# How to run this solution

Everything here runs from `solutions/sol2_implementer_agent_sdk/`, standalone.
Copy this folder somewhere else and it still runs. This folder owns the loop.

You need `python3` and `task`. `--doer reference` and `--doer none` need no
SDK and no key. `--doer sdk` also needs `claude-agent-sdk` and an
`ANTHROPIC_API_KEY`.

This is the take-home runtime. Saturday live path is `labs/lab2_implementer`.

Python is the harness. The model writes tests and then code. It does not score
the rubric, and it does not decide Pass, Retry, or Escalate.

## One-time setup

Create the folder-local Python virtual environment and install the Claude
Agent SDK. This does not modify Homebrew's system Python.

```bash
task setup
```

Creates `.venv` in this folder and installs the package there. Homebrew
Python will not let `pip` write to the system interpreter (PEP 668).
`task run -- --doer sdk` uses this venv. You do not activate it.

Put the API key in the repo root `.env`, or export it in this shell.
Task loads `../../.env` first, then this folder's `.env`.

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
```

Clone the CRM:

```bash
task clone
```

## Scripts you can run without a model

```bash
task table
task test
task e2e
```

`task table` prints the role table. The judge must print `no` in the writes
column. `task test` is the pytest suite. `task e2e` is the offline loop
against a disposable fixture. None of them need the SDK, a key, or a clone.

## Run the implementer

Needs the clone. `--doer none` and `--doer reference` need no key and no
SDK venv. `--doer sdk` needs `task setup` and the key. That path refuses if
you skipped `task setup`.

```bash
task run -- --ticket T001 --doer reference
task run -- --ticket T001 --doer sdk
```

`task run` calls `harness.py --repo <target>`. Extra flags after `--` go to
`harness.py`. Python still owns the red gate and `gates.decide`. Same
signature twice means stop. A retry carries the failed rubric rows and the
failing test ids. After a green rubric the judge subagent answers in JSON;
unparseable is a fail.

## What this folder will not do

It will not write `tests/**` from the code implementer. That fence is the
lesson. One PreToolUse hook reads `agent_type` and looks up that role's
scope. A write with no agent is denied, because the parent has no business
writing anything. It will not paste `SKILL.md` into a subagent prompt. The
skill is listed on `AgentDefinition.skills`.
