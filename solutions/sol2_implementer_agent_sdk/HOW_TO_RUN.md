# How to run this solution

Everything here runs from `solutions/sol2_implementer_agent_sdk/`, standalone.

You need `python3` and `task`. A live SDK run also needs an `ANTHROPIC_API_KEY`.

Python is the harness. This folder is the cast, the write scope, and the
runtime wiring. It is not the Lab 2 driver. The working loop lives in
`sol2_implementer_deep_agents`. Saturday Lab 2 is `labs/lab2_implementer`.

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

Clone the CRM if you want to print live options against a real repo:

```bash
task clone
```

## Scripts you can run without a model

```bash
task table
task test
```

`task table` prints the role table. The judge must print `no` in the writes
column. `task test` is the pytest suite. Neither needs the SDK, a key, or a
clone.

## Print this runtime's options

Needs the SDK. Refuses if you skipped `task setup`.

```bash
task run --
```

That is configuration, not a ticket run. To drive the loop, hand
`AgentSdkBackend` to the Deep Agents implementer driver, or copy that driver
into this folder. Do not invent a shared `loops/` package.

## What this folder will not do

It will not write `tests/**` from the code implementer. That fence is the
lesson. One PreToolUse hook reads `agent_type` and looks up that role's
scope. A write with no agent is denied, because the parent has no business
writing anything.
