# Spec. Lab 1. Ticket Enhancer, on Claude Agent SDK

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

## The cast for this loop

- `orchestrator`
- `doer`
- `judge`

This folder's `roleplan.py` is where that list lives. Read it there. Do not
restate a scope anywhere else in this folder. `contract.py`, `write_scope.py`,
and `ticket.py` are flat copies of the engine's modules, so this folder needs
nothing from `loops/` and imports nothing from it.

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
   cd solutions/sol1_enhancer_agent_sdk
   task table
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
   python loop.py --repo ../../work/northwind-field-crm
   ```

## Verify

```bash
cd solutions/sol1_enhancer_agent_sdk
task test
```

Those checks need no SDK, no API key, and no cloned target repo. They stub
`claude_agent_sdk` in `sys.modules`, build a target repo in a temporary
directory, and assert the rules this port has to keep:

- The enhancer cast is `orchestrator`, `doer`, `judge`, and the judge holds no
  write tool.
- `cast()` returns the shared table, not a local restatement.
- The `PreToolUse` hook denies a write outside scope with the full
  `hookSpecificOutput` shape. Returning an empty dict lets the call through, so
  a typo anywhere in that envelope fails open.
- A path outside the target repo is denied rather than allowed by default.
- `AgentSdkBackend.run` reports a failed result when the SDK is absent, and
  never claims a write it did not make.

Run the two deterministic check scripts against their own assertions with
`task checks`.

## Run the loop

`loop.py --table-only` needs nothing. The loop itself needs three things: the
`claude-agent-sdk` package, an API key, and a clone of the target repo.

1. Copy `config.json.example` to `config.json` and fill in your GitHub username.

2. Install the runtime and clone your fork.

   ```bash
   task setup
   task clone
   task create-test-tickets
   ```

3. Run one poll-and-act step.

   ```bash
   task run
   ```

   It prints one line per ticket: `passed`, `escalated`, or `waiting`.

4. Poll on an interval, until you stop it.

   ```bash
   task poll-forever
   ```

   That script is a seminar stand-in for a scheduler. In production the trigger
   is cron, or a scheduled GitHub Actions workflow.

To work one ticket without waiting on a real comment, pass your own:

```bash
task run -- --ticket T001 --simulate-comment "due dates should be optional"
```

## What one poll does

`enhancer.py` is the orchestrator. It is Python, not a prompt, because a stop
condition trusted to a model's own judgment is a stop condition a model can talk
itself past. The model drafts and grades. Everything else is computed.

1. Find every `tickets/*.md` with `state: draft` and `loop: enhancer`. Skip
   `*.ready.md` and `*.enhancer-candidate.md`.
2. Find or create the ticket's GitHub issue.
3. Read the newest comment. If it is one this loop already acted on, stop.
4. If the issue carries `needs-human`, stop and wait for a person.
5. The judge grades the real ticket. `check_fields.py` turns its
   `{kind, present_fields}` into the authoritative `ready`.
6. Ready plus a comment of exactly `LGTM` releases the ticket to
   `state: ready`, `loop: implementer`. A red rubric never consumes an `LGTM`.
7. The doer writes `tickets/<id>.enhancer-candidate.md`. The judge grades that
   file. The draft replaces the real ticket only when its missing set is a
   proper subset of the current one. "Not worse" is not good enough.
8. `check_stop.py` decides the other two exits: budget spent, or the same gaps
   two rounds running. Either one adds `needs-human` and stops.

The doer is the only role holding `Write`, and the `PreToolUse` hook keeps it
inside `tickets/**`. The candidate file lives there, so the hook allows the one
write the loop wants and blocks every other path the doer might reach for.

## What this folder is not

It is not a second loop engine. `loops/` holds the loop, and porting it must not
require changing `loops/`. If it does, the design leaked.

It is not a Claude Code plugin either. There is no `.claude/` here. The plugin
port of this same lab lives in `solutions/sol1_enhancer/`, and the two are meant
to be read side by side: same rubric, same exits, two different runtimes.

`write_scope.build()` is a copy of the engine's role builder and the enhancer
never calls it. Leave it alone. Rewriting it to return an enhancer cast makes
this copy drift from `loops/roles.py`, which is the exact failure the shared
table exists to prevent.
