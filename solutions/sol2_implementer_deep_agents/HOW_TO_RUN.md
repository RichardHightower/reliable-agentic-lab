# How to run this solution

Everything here runs from `solutions/sol2_implementer_deep_agents/`, standalone. No
task in this folder depends on the repo root or on any other folder outside
it.

You need `python3` and `task`. `--doer reference` and `--doer none` need no
SDK and no key. `--doer deep` also needs `deepagents>=0.7` and an
`ANTHROPIC_API_KEY`.

This is the take-home runtime. Saturday live path is `labs/lab2_implementer`.
Do not copy these harness fences into that folder.

Python is the harness. The model writes tests and then code. It does not score
the rubric, and it does not decide Pass, Retry, or Escalate.

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

3. Install what you need.

   ```bash
   task test-setup
   ```

   That creates `.venv` in this folder and installs pytest plus coverage.
   Use it for `task test` and for `--doer none` / `--doer reference`.

   ```bash
   task setup
   ```

   That adds `deepagents` to the same virtual environment. Only `--doer deep`
   needs this step. You do not need to activate the venv.

4. Clone the CRM:

   ```bash
   task clone
   ```

   This reads `fork_owner` and `repo_name` from `config.json` and clones that
   repo into `../../work/northwind-field-crm`. Default `TARGET` is that path.

## Scripts you can run without a model

```bash
task table
task test
task e2e
```

`task table` prints the role table. The judge must print `no` in the writes
column. If it prints `yes`, stop. `task test` is the pytest suite. `task e2e`
is the offline loop against a disposable fixture. None of them need the SDK,
a key, or a clone of the public CRM.

## Run the implementer

Needs the clone. `--doer none` and `--doer reference` need no key and no
Deep Agents venv. `--doer deep` needs `task setup` and the key. That path
refuses if you skipped `task setup`.

```bash
task run -- --ticket T001 --doer reference
task run -- --ticket T001 --doer deep
```

`task run` calls `harness.py --repo <target>`. Extra flags after `--` go to
`harness.py`. Python still owns the red gate and `gates.decide`. Same
signature twice means stop.

## What this folder will not do

It will not write `tests/**` from the code implementer. That fence is the
lesson. It will not paste `SKILL.md` into a subagent prompt. The skill is
mounted, and Deep Agents loads the body when the role is invoked.
