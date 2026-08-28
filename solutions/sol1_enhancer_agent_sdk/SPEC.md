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
task run --
```

## What one poll does

`enhancer.py` is the orchestrator. It is Python, not a prompt, because a stop
condition trusted to a model's own judgment is a stop condition a model can talk
itself past. The model drafts and grades. Everything else is computed.

1. List open GitHub issues. A UI-created issue is a ticket. Write a local
   draft if one is missing (`[Txxx]` from the title, or `T{number}`), then
   keep every `tickets/*.md` with `state: draft` and `loop: enhancer`. Skip
   `*.ready.md` and `*.enhancer-candidate.md`.
2. Find the ticket's GitHub issue. Never create one. Add the `enhanced` label on first touch, not at create time.
3. Read the newest human comment only to detect exact `LGTM`. Comments never start an enhance round.
4. If the issue carries `needs-human`, stop and wait for a person.
5. The judge grades the real ticket. `check_fields.py` turns its
   `{kind, present_fields}` into the authoritative `ready`.
6. Ready plus a comment of exactly `LGTM` releases the ticket to
   `state: ready`, `loop: implementer`. A red rubric never consumes an `LGTM`.
7. The doer returns the rewritten ticket as its final message. Python writes
   `tickets/<id>.enhancer-candidate.md`. The judge grades that file. The draft
   replaces the real ticket only when its missing set is a proper subset of the
   current one. "Not worse" is not good enough.
8. `check_stop.py` decides the remaining exits: round budget spent, cost budget
   spent, max turns, or the same gaps two rounds running. Completing a ticket
   (rubric green and `LGTM`) is the other exit. Cost and max turns also stop
   the SDK `query()` itself via `max_budget_usd` and `max_turns`. Either
   computed stop adds `needs-human`.

The doer holds no `Write`. Python writes the candidate, matching the Claude
Code plugin. A `PreToolUse` hook is still registered so a leaked Write fails
closed instead of writing `app/`. The parent session may only spawn a
subagent (`allowed_tools=["Agent"]`).

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a shared engine.

It is not a Claude Code plugin either. The same agents and skill live under
`plugin/`, loaded with `plugins=` because `cwd` is the CRM. The plugin port of
this same lab lives in `solutions/sol1_enhancer/`, and the two are meant to be
read side by side: same rubric, same agents, two different runtimes. Python is
the harness. The skill is not invoked.

`write_scope.build()` is a copy of the engine's role builder and the enhancer
never calls it. Leave it alone. Rewriting it to return an enhancer cast makes
this copy drift from `loops/roles.py`, which is the exact failure the shared
table exists to prevent.

## Deploy on GitHub Actions (ticket change events)

Saturday still polls. Production is an event: `issues` opened / edited /
labeled, and `issue_comment` created.

Copy-me workflow and the backend matrix (Claude, Codex, OpenCode, Agent
SDK, Deep Agents) live in the Saturday lab notes, not here:

- `labs/lab1_enhancer/GITHUB-ACTIONS.md`
- `labs/lab1_enhancer/workflows/enhance-on-issue.yml`

Copy the YAML onto **your CRM fork**. Do not enable it on the shared
instructor repo. The trigger starts one poll. This folder still owns the
exits. Skip comments that contain `<!-- enhancer-loop -->`. Set
`ENHANCER_BACKEND` to the name of this port.

Grok on hosted runners is a poor fit. Prefer Claude Code, Agent SDK, or
Deep Agents in Actions. Keep Grok on a laptop or `ext_5_digitalocean`.

