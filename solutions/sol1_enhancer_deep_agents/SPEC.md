# Spec. Lab 1. Ticket Enhancer, on LangChain Deep Agents

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

This folder is standalone. Every module it needs is a file next to this spec:
`roleplan.py`, `contract.py`, `write_scope.py`, `roles.py`, `adapter.py`, and
`loop.py`. Nothing imports `loops.` or `solutions.`.

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

## What this folder is not

It is not a second loop engine. `loops/` holds the loop, and porting it must not
require changing `loops/`. If it does, the design leaked.
