# How to run this solution

Everything here runs from `solutions/sol4_fixer_agent_sdk/`, standalone.

You need `python3` and `task`. A live SDK run also needs an `ANTHROPIC_API_KEY`.

Python is the harness. The model edits `app/**`. It does not edit `tests/**`,
it does not merge, and it does not run a shell.

## One-time setup

Create the folder-local Python virtual environment and install the Claude
Agent SDK. This does not modify Homebrew's system Python.

```bash
task setup
```

Creates `.venv` in this folder and installs the package there. Homebrew
Python will not let `pip` write to the system interpreter (PEP 668).
`task run` uses this venv. You do not activate it.

Put the API key in the repo root `.env`, or export it in this shell.
Task loads `../../.env` first, then this folder's `.env`.

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
```

Clone the CRM and check out the broken branch:

```bash
task clone
task reset
```

`task reset` checks out `broken-pr`. It refuses if the clone still holds
work from an earlier lab. That is on purpose.

## Scripts you can run without a model

```bash
task table
task test
```

`task table` prints the role table. The judge must print `no` in the writes
column. `task test` is the pytest suite. Neither needs the SDK, a key, or a
clone.

## Repair the broken branch

Needs the SDK for `--doer sdk`. Refuses if you skipped `task setup`.

```bash
task run -- --repo ../../work/northwind-field-crm --branch broken-pr --doer reference
task run -- --repo ../../work/northwind-field-crm --branch broken-pr --doer sdk
```

`--doer sdk` needs `claude-agent-sdk`. `--research` defaults to `off`.

`permission_mode` is `dontAsk`. Both `dontAsk` and `acceptEdits` never prompt.
Only `dontAsk` fails closed.

## What this folder will not do

It will not edit a failing test into passing. The code implementer is denied
`tests/**`. A hung query times out instead of starving later attempts. Spend
comes from `total_cost_usd`, so the money gate can fire.
