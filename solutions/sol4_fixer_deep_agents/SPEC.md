# Spec. Lab 4. Broken PR Fixer, unattended, on LangChain Deep Agents

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

## The cast for this loop

- `orchestrator`
- `code_implementer`
- `judge`

`roleplan.py`, in this folder, is where that list lives. Read it there. Do not
restate a scope anywhere else.

## How this runtime enforces scope

Deep Agents scopes three ways. This port uses all three, because any one of
them left off is a hole the other two cannot see.

1. Each subagent gets its own tool list. The judge is never handed a write
   tool. That is the same separation every other runtime uses.
2. Path scope lives inside the code implementer's write tool. The tool checks
   the role's allow and deny lists before it touches the disk, and it returns
   a refusal sentence rather than raising, because a raw traceback in an
   agent's context starts a retry loop.
3. The harness is fenced the way the product actually works in 0.7:

   - `FilesystemBackend(root_dir=repo, virtual_mode=True)` so `..` cannot
     walk off the repo through a **built-in** filesystem tool. A custom
     tool is not covered, so `read_file` and the write tool resolve and
     contain the path themselves.
   - `CompositeBackend` routes `/skills/` and `/memory/`. A role with a skill
     directory mounts it and does not also paste the body into its prompt: the
     mount exists so instructions load when the role is invoked, not always.
     `/memory/` routes at `memory/`, one file, rather than at this folder.
     walk off the target repo.
   - `permissions=` deny every write on the orchestrator. Each subagent
     carries its own rules: the deny list first, the allow list second, and a
     deny-everything rule last. First match wins, so allow first would let an
     overlapping pattern make `tests/**` writable again.
   - A harness profile hides `write_file`, `edit_file`, `delete`, and
     `execute` from the orchestrator, and turns off the default
     `general-purpose` subagent. That subagent ships with the harness
     filesystem tools. Leaving it on is how a scoped fixer edits the failing
     test instead of the broken code, and neither of the first two layers can
     see it happen.

(1) and (2) are what `task test` pins down with no SDK installed. (3) is what
`build_agent` does on a real run, and the tests read it back off a fake
`create_deep_agent` so the fence cannot rot silently.

Needs `deepagents>=0.7`.

## Build it step by step

See `HOW_TO_RUN.md`. The short path:

```bash
cd solutions/sol4_fixer_deep_agents
cp config.json.example config.json
task setup
task table
task clone
task reset
task run --
```

`task test` and `task table` need no SDK. `task reset` checks out `broken-pr`
and refuses if the clone is dirty. `task run` needs the folder venv.

## Verify

```bash
task test
task table
```

Or the same two directly:

```bash
python3 -m pytest tests -q
python3 loop.py --table-only
```

Those checks need no SDK, no key, no network, and no clone. They assert that
the cast is exactly the three fixer roles, that the judge and the orchestrator
hold no write path, that the write tool refuses `tests/**` and says so in a
sentence, and that all four fencing facts reach the SDK: the general-purpose
subagent off, the built-in write tools excluded, the backend in virtual mode,
and the orchestrator denied every write.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a shared engine.
