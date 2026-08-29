# How to run this solution

Everything here runs from `solutions/sol4_fixer_deep_agents/`, standalone. No
task in this folder depends on the repo root or on any other folder outside
it.

You need `python3`, `task`, `deepagents>=0.7`, and an `ANTHROPIC_API_KEY` for
`task run`. `task test` and `task table` need none of those extras.

This is the take-home runtime. Saturday live path is `labs/lab4_fixer`.
Do not copy these harness fences into that folder.

Python owns the role table and the write scope. The model is the
code-implementer. It does not edit `tests/**`. Deny stays the unattended
rule. There is no interrupt on this path.

## One-time setup

1. Copy the config template. The public CRM works. Change `fork_owner` if you
   cloned a fork instead.

   ```bash
   cp config.json.example config.json
   ```

2. Put the API key in the repo root `.env`. Task loads that file first, then
   this folder's `.env`. The first file that defines a variable wins.

   ```bash
   echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
   ```

3. Install the runtime.

   ```bash
   task setup
   ```

   This creates `.venv` in this folder and installs `deepagents` plus pytest.
   `task run` uses that virtual environment automatically. You do not need to
   activate it.

4. Clone the CRM and check out the broken branch:

   ```bash
   task clone
   task reset
   ```

   `task reset` checks out `broken-pr`. It refuses if the clone is dirty.
   That is on purpose.

## Scripts you can run without a model

```bash
task table
task test
```

`task table` prints the role table. The judge must print `no` in the writes
column. If it prints `yes`, stop. `task test` is the pytest suite. Neither
needs the SDK, a key, or a clone.

## Build the fixer against the clone

Needs `task setup` and the clone. Refuses if you skipped setup.

```bash
task run --
```

`task run` calls `loop.py --repo <target>`. Extra flags after `--` go to
`loop.py`. This folder is the graph. It prints the cast and builds the
agent. The Agent SDK twin is the loop that drives a repair.

## What this folder will not do

It will not edit a failing test into passing. The code implementer is denied
`tests/**`. It will not paste `SKILL.md` into a subagent prompt. The skill is
mounted. `/memory/` routes at `memory/`, not this folder.
