# Spec. Lab 1. Ticket Enhancer, on LangChain Deep Agents

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

This folder is standalone. Every module it needs is a file next to this spec:
`roleplan.py`, `contract.py`, `write_scope.py`, `roles.py`, `adapter.py`, and
`loop.py`. Nothing imports a shared engine.

## The cast for this loop

- `orchestrator`
- `doer`
- `judge`

`roleplan.py`, in this folder, is where that list lives. Read it there. Do not
restate a scope anywhere else.

## How this runtime enforces scope

Deep Agents scopes by handing each subagent its own tool list. A subagent can
only call what it was given. Path scope moves inside the write tool, which
checks the scope before it touches the disk.

## Build it step by step

1. Create the environment. The tests need pytest and nothing else.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pytest
   ```

   Install the runtime only when you are ready for step 5. The table and the
   tests do not need it.

   ```bash
   pip install -r ../../requirements-takehome.txt
   ```

2. Read the cast before you configure anything.

   ```bash
   cd solutions/sol1_enhancer_deep_agents
   python3 loop.py --table-only
   ```

   The judge must print `no` in the writes column. If it prints `yes`, stop.
   Nothing downstream is worth building on that.

   `--repo` is optional. It defaults to `../../work/northwind-field-crm`. When
   that repo is absent, the table falls back to the scopes in
   `roleplan.FALLBACK_SCOPE` and says so on stderr. For this cast the two tables
   read the same, because no `.loop.yml` declares a `doer`. Point `--repo` at a
   real target when you want the declared scope instead.

3. Translate the cast into this runtime, one role at a time. `cast(contract)`
   returns a `RolePlan` per role, carrying the tools, the allow list, and the
   deny list. `build(contract)` turns those into the runtime's own objects.

4. Give the writing roles their path check. A role holding `Edit` or `Write`
   without a path check can reach any file in the repo, and the first thing an
   agent under pressure reaches for is the failing test.

5. Print the configuration and read it. This step needs `deepagents` and a real
   target repo.

   ```bash
   python3 loop.py --repo ../../work/northwind-field-crm
   ```

## Verify

```bash
python3 -m pytest tests -q
python3 loop.py --table-only
```

Or run the same two through Task:

```bash
task test
task table
```

Those checks need no SDK, no key, and no clone of the target repo. They assert
that the judge holds no write tool, that the doer's write tool refuses a path
outside `tickets/**`, that `.loop.yml` merges over the defaults, and that the
backend drops any file the scope does not permit.

## Run the loop

`loop.py --table-only` needs nothing. The loop itself needs three things: the
`deepagents` package, an API key, and a clone of the target repo.

1. Copy `config.json.example` to `config.json` and fill in your GitHub username.

2. Clone your fork and seed a few draft tickets.

   ```bash
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

`enhancer.py` is the orchestrator, and it is the same file the Agent SDK port
runs, give or take the comment marker in step 3. It never imports a runtime. It
takes a backend, and both ports hand it one with the same
`run(repo, prompt, allow)` surface. That is the claim this folder makes: the
loop did not change, only the wiring did.

It is Python, not a prompt, because a stop condition trusted to a model's own
judgment is a stop condition a model can talk itself past. The model drafts and
grades. Everything else is computed.

1. Find every `tickets/*.md` with `state: draft` and `loop: enhancer`. Skip
   `*.ready.md` and `*.enhancer-candidate.md`.
2. Find or create the ticket's GitHub issue. The lookup order is the state
   file, then the ticket's `github_issue`, then a title search across every
   state. Never only the open ones: a closed issue is still that ticket's
   issue, and skipping it is what opens a duplicate.
3. Read the newest comment the loop did not write itself. Every comment it
   posts ends with `<!-- enhancer-loop -->` and this query skips those, so the
   loop cannot spend every poll answering its own last reply.
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

The doer is the only role holding a write tool, and the scope check inside that
tool keeps it within `tickets/**`. The candidate file lives there, so the one
write the loop wants lands and every other path the doer might reach for is
refused.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a shared engine.
