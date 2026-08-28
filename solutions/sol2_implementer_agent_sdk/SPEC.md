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

`solutions/roleplan.py` is where that list lives. Read it there. Do not restate
a scope in this folder.

## How this runtime enforces scope

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The judge holds neither Edit nor Write, so there is nothing left for a
hook to guard.

## Build it step by step

1. Install the runtime.

   ```bash
   pip install -r requirements-takehome.txt
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
```

Those checks need no SDK and no key. They assert that this port and the
in-process roles read the same table, and that the judge holds no write tool in
either.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a shared engine.
