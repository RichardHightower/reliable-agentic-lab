---
date: 2026-08-27
slug: sol1-enhancer-agent-sdk-tests
title: Unit test the Agent SDK enhancer port
epic: 01M122KB0K47AMZ4F3NJ3GWW9A
items: [01M122KB12N85PB37YF38JW928, 01M122KB12YX7Z6MBA0HGPS2ER, 01M122KB1229GVVVPXK8N9EWT1, 01M122KB12WDA12R9XG7R4JH2M, 01M122KB12DFWCC6NE926M39M6, 01M122KB12YPVHPV3X2YNXM7PN, 01M122KB12ED1H4V4FVM1PVPM0, 01M122KB12W67XKVZ1GNS5JSQC, 01M122KB12C59NPRA1HXCT9T7S, 01M122KB12QZAJP4H8R65C10ZR, 01M122KB125759RRT2WAEAS246]
git_hash: "85ff7bdcea104b6e58b54dbf382af3c6271c40fa"
---

# Make sol1_enhancer_agent_sdk standalone and unit tested

## Context

`solutions/sol1_enhancer_agent_sdk/` is the Claude Agent SDK port of lab 1. It is
already a flat, standalone folder on disk. Three problems remain.

1. It has no tests of its own. The only coverage is external, in
   `loops/tests/test_runtime_ports.py`, which loads the folder through an
   f-string list of port names and checks one thing: that `cast()` matches the
   shared table. That file skips entirely unless you clone the target CRM repo
   first, and it never touches `adapter.py`. The folder's own `task test` just
   runs `python3 loop.py --table-only`, which asserts nothing.
2. Three docstrings still point at root files the folder no longer uses.
   `SPEC.md` says to read `solutions/roleplan.py`. `loop.py`'s `cast()` says the
   same. `roleplan.py` points at `loops/tests/test_runtime_ports.py`. All three
   are stale for a standalone folder.
3. The folder cannot read a ticket. The enhancer loop grooms a draft ticket, but
   no module here parses one. The parser lives in root `loops/ticket.py`.

The outcome is a folder you can test in place, with no Claude Agent SDK
installed, no GitHub, and no CRM clone. It stays a Python Agent SDK port. It
does not become a `.claude/` plugin.

## Set up the worktree

Run these from the lab repo root. Both the path and the branch are free today,
so no `-2` fallback is needed.

```bash
git fetch origin
git worktree add ../sol1-enhancer-agent-sdk -b feature/sol1-enhancer-agent-sdk origin/main
cd ../sol1-enhancer-agent-sdk
```

Work only inside `solutions/sol1_enhancer_agent_sdk/`. Do not edit
`solutions/sol1_enhancer`, `solutions/sol1_enhancer_codex`, or
`solutions/sol1_enhancer_grok_build`. Do not import `loops.*` or root
`solutions.*` from any file in this folder.

## Open the worklog ticket

Do this before you change any file. `plan-capture` refuses to overwrite an
existing plan for the same slug and date.

```bash
bin/worklog plan-capture \
  --slug sol1-enhancer-agent-sdk-tests \
  --title "Unit test the Agent SDK enhancer port" \
  --file ~/.claude/plans/lets-work-on-this-mutable-fairy.md \
  --priority P1
bin/worklog sync --push-only
```

`plan-capture` reads the `## Tasks` section below and creates one epic plus one
item per checkbox. If you find work mid-flight that is not in that list, run
`bin/worklog add --unplanned --discovered-during <item-ulid>` before you do it.

The `--file` path is local to one machine. If it is missing, pipe the tasks in
on stdin instead, which `plan-capture` reads when you omit `--file`. Do not
block the work on it.

## Copy in the two missing pieces

Both files are self contained. Neither needs an edit after the copy.

- `loops/ticket.py` to `solutions/sol1_enhancer_agent_sdk/ticket.py`. It imports
  only `re`, `dataclasses`, and `pathlib`. It gives the folder `Ticket`,
  `Criterion`, `parse()`, and `load()`, which is the frontmatter, `state`, and
  acceptance criteria parsing the tests need.
- `solutions/sol1_enhancer/.claude/skills/enhancer-loop/scripts/check_fields.py`
  and `check_stop.py` to the folder root. Copy the files. Do not import them
  from the plugin folder. Both already carry a `demo()` self check, so the
  pytest cases just lift those assertions and add the error paths.

## Add the test suite

Create `solutions/sol1_enhancer_agent_sdk/tests/`. Use pytest. Never call the
real SDK, real `git`, real `task`, or real GitHub.

### conftest.py

Follow the shim already used by `work/northwind-field-crm/tests/conftest.py`:
insert the folder root into `sys.path` so `import roleplan` resolves to the
local copy. Add three fixtures.

- `repo(tmp_path)` builds a fake target repo: a `Taskfile.yml` declaring the
  five tasks in `contract.REQUIRED_TASKS`, a small `.loop.yml` with `roles`,
  `rubric`, `tickets`, and `budget` keys, a `tickets/T001.md` draft with YAML
  frontmatter and a `## Success criteria` section, and a `reports/` directory.
- `contract(repo)` returns `Contract(repo)`.
- `fake_sdk(monkeypatch)` installs a stub module at
  `sys.modules["claude_agent_sdk"]` holding plain dataclasses named
  `AgentDefinition`, `ClaudeAgentOptions`, and `HookMatcher`, plus a `query`
  that is an async generator. Remove the entry on teardown. This is the only way
  to reach `roles.options_for`, since that function imports the SDK lazily.

### The test files

| File | What it covers |
| --- | --- |
| `test_roleplan.py` | The enhancer cast is exactly `orchestrator`, `doer`, `judge`. `judge.can_write` is `False`. `orchestrator.can_write` is `False`. `doer.allow` falls back to `tickets/**` when `.loop.yml` never mentions it. An unknown loop name raises `ValueError`. `plan(None, "research")` works with no contract. `table()` renders `no` in the judge's writes column and shows a `denied:` suffix. |
| `test_write_scope.py` | `WriteScope.permits` for a plain glob, a `tests/**` prefix that must match `tests/a.py` and `tests/a/b/c.py`, a bare `**`, an empty allow list, and deny beating allow. `check()` raises `ScopeViolation`. `Doer.write` refuses an out of scope path and creates parent directories for one in scope. `Doer.violations` returns only the disallowed paths. `Judge` has no `write` attribute. `Orchestrator` budget arithmetic and `exhausted`. |
| `test_contract.py` | `Contract` on a missing directory raises `ContractError`. `missing_tasks()` on a Taskfile that omits one. `validate()` raises with the missing names. `.loop.yml` deep merges over `DEFAULTS` instead of replacing them. `role()` returns deny `**` for an unknown name. `parse_junit` on a pytest shape, a Node shape with cases but no counts, a counts-only suite, a skipped case, and a missing file. `parse_coverage` on a Cobertura file and a missing file. Force the `_mini_yaml` path with `monkeypatch.setitem(sys.modules, "yaml", None)` or an import block, then assert it reads the same `.loop.yml`. |
| `test_ticket.py` | `parse()` reads `id` and `state` from frontmatter, falls back to `state: draft` with no criteria and `ready` with them, picks the title from the first `# ` line, numbers bullets `AC-1` upward, and honors an explicit `(AC-7)` id. `load()` prefers `.ready.md` by default and prefers the draft when `prefer_ready=False`. A missing folder and a missing id both raise `FileNotFoundError`. |
| `test_checks.py` | `check_fields.check` for each kind, a missing field list, an invented field that is dropped, and an unknown kind raising `ValueError`. `check_stop.check` for the three exits: not stopping, the repeated signature, and the spent budget. Drive `main()` once through `sys.argv` and once through stdin, and assert the JSON on stdout. |
| `test_roles.py` | `scope_hook` denies a write outside scope with the full `hookSpecificOutput` shape, allows one inside scope with `{}`, returns `{}` for a `Read`, returns `{}` when no path key is present, and denies an absolute path outside the repo with `outside the target repo` in the reason. Drive the hook with `asyncio.run`, the way `loops/tests/test_runtime_ports.py` already does. With `fake_sdk` active, assert `options_for` builds one agent per non orchestrator role, uses hyphenated agent names, sets `cwd`, sorts `allowed_tools` into a deduplicated set, and registers a `HookMatcher` for each of `Edit`, `Write`, and `NotebookEdit` on every writing role. |
| `test_adapter.py` | Patch `adapter._changed_files` or `subprocess.run` so the second call reports a superset of the first. On the success path, with `fake_sdk`, `run()` returns `ok=True`, joins the message chunks into `output`, and lists only the in scope new paths in `wrote`. Assert that a file changed outside the allow list is not reported. With no `claude_agent_sdk` in `sys.modules` and imports blocked, `run()` returns `ok=False` and an output starting `agent sdk backend failed:`. With a `query` that raises, the same. |
| `test_loop.py` | `loop.cast(contract)` returns the three enhancer roles and matches `roleplan.plan(contract, "enhancer")`. `loop.main(["--table-only", "--repo", str(repo)])` returns `0` and prints a table containing `judge` and `orchestrator`, captured with `capsys`. `loop.backend` imports `adapter` lazily, so assert `"adapter" not in sys.modules` after a `--table-only` run in a clean interpreter state. `loop.LOOP == "enhancer"`. |

Match the house style in `loops/tests/`: `from __future__ import annotations` at the
top, full sentence test names, a docstring saying why a check exists, and an
assertion message naming the failure mode. `ruff.toml` sets line length 100 and
target Python 3.10, and the root `task lint` already covers `solutions/`, so the
new tests must pass `ruff check`.

Two facts shape what is worth testing. Three of the six modules are byte
identical copies of root files: `roleplan.py` copies `solutions/roleplan.py`,
`contract.py` copies `loops/contract.py`, and `write_scope.py` copies
`loops/roles.py`. Only `loop.py` and `adapter.py` are specific to this folder,
and `adapter.py` has no coverage anywhere in the repo today. Inside
`write_scope.py`, the module level `build()` hardcodes the implementer's five
roles. The enhancer never calls it, and `loop.py` never imports it. Test
`WriteScope`, `Doer`, `Judge`, and `Orchestrator`, and leave `build()` alone
rather than writing a test that pretends it belongs here.

Do not rewrite `write_scope.build()` to return an enhancer cast. It stays
uncalled. Changing it makes this copy drift from `loops/roles.py`, which is the
exact failure the shared table exists to prevent.

The `contract.py` and `write_scope.py` tests cover more than an enhancer strictly
needs, including JUnit parsing, coverage parsing, and the implementer's
`Doer.write`. That is deliberate. The folder owns those files now, so it owns
their behavior.

While you are in the folder, delete the stale
`__pycache__/_root.cpython-314.pyc`. There is no `_root.py`, so it is a leftover
from an earlier layout.

## Update the Taskfile

Replace the `test` task and keep the table print as its own task.

```yaml
# Standalone. No dependency on the root Taskfile and no SDK installed.
# The tests need pytest. Activate the repo .venv or `pip install pytest` first.
version: '3'

tasks:
  default:
    cmds: [task --list]

  test:
    desc: Unit tests for this folder. No SDK and no API key.
    dir: '{{.TASKFILE_DIR}}'
    cmds:
      - python3 -m pytest tests -q

  table:
    desc: Print the role table and exit, with no SDK installed.
    dir: '{{.TASKFILE_DIR}}'
    cmds:
      - python3 loop.py --table-only
```

Leave the root `Taskfile.yml` `test` task unchanged.

## Fix the stale references

Three edits, all cross references to root files this folder no longer uses.

- `SPEC.md`: change "`solutions/roleplan.py` is where that list lives" to name the
  local `roleplan.py`. Replace the **Verify** block's
  `task test, loops/tests/test_runtime_ports.py` with `task test` run from this
  folder, and say those checks need no SDK, no key, and no CRM clone.
- `loop.py`: the `cast()` docstring says "Read from `solutions/roleplan.py`".
  Change it to the local `roleplan.py`.
- `roleplan.py`: the module docstring points at
  `loops/tests/test_runtime_ports.py`. Point it at this folder's `tests/`.

## Verify

Run every step. The repo `.venv` has pytest 8.3.5. It does not have
`pytest-cov` and it does not have `claude-agent-sdk`, which is the point: the
suite must be green without either.

```bash
cd solutions/sol1_enhancer_agent_sdk

# 1. The table still prints and exits 0.
python3 loop.py --table-only

# 2. The suite is green with no SDK installed.
../../.venv/bin/python -m pytest tests -q

# 3. No root imports leaked in.
grep -rn "from loops\|import loops\|from solutions\|import solutions" . ; echo "exit $?"
# grep exits 1 when it finds nothing. Exit 1 is the pass here, not a failure.
# Say that in the pull request body so nobody "fixes" a green verify.

# 4. The SDK really is absent, so the tests proved what they claim.
../../.venv/bin/python -c "import claude_agent_sdk" ; echo "expect ModuleNotFoundError"

# 5. Lint.
../../.venv/bin/python -m ruff check .

# 6. The copied scripts still self check.
python3 check_fields.py --demo
python3 check_stop.py --demo
```

Optional coverage, only if you install `pytest-cov`, which is pinned in
`requirements.txt` but is not in the `.venv` today:

```bash
../../.venv/bin/python -m pytest tests -q --cov=. --cov-report=term-missing
```

Aim high on `write_scope.py`, `roleplan.py`, `ticket.py`, `check_fields.py`, and
`check_stop.py`. Do not gate the task on a number. `roles.options_for` and
`adapter.run` only reach full coverage through the stub SDK, and a hard gate
turns a missing optional dependency into a red build.

## Close out

Do not push until step 2 passes with no `claude-agent-sdk` installed.

```bash
bin/worklog close <item-ulid>       # per finished item
bin/worklog roadmap-render
git add -A && git commit            # the commit message must cite an item
git push -u origin feature/sol1-enhancer-agent-sdk
gh pr create --base main
```

Commit `.work/todo.jsonl` and `docs/roadmap.md` together. The `hooks/pre-commit`
hook checks roadmap freshness, and `hooks/commit-msg` requires an item reference.

## Out of scope for this pass

Do not build the GitHub poll loop yet. Once the unit tests are green, a later
pass can add an orchestrator driven by a fake `Backend` and a fake `gh` wrapper,
using the same ready rule as the plugin: rubric first, then LGTM, persisting
`last_comment_id` and skipping `*.enhancer-candidate.md`.

## Tasks

- [ ] (P1) Create the worktree and branch for the Agent SDK enhancer tests
  Branch feature/sol1-enhancer-agent-sdk from origin/main into ../sol1-enhancer-agent-sdk.
- [ ] (P1) Copy ticket.py, check_fields.py, and check_stop.py into the folder
  Copy loops/ticket.py and the two plugin check scripts in without edits, so the folder can parse a ticket and decide its exits on its own.
- [ ] (P1) Write tests/conftest.py with the sys.path shim and the repo fixtures
  Add the repo, contract, and fake_sdk fixtures. The fake_sdk fixture stubs sys.modules so roles.options_for and adapter.run are reachable with no SDK installed.
- [ ] (P1) Test roleplan.py and write_scope.py
  Cover the enhancer cast, the judge write ban, the scope fallback, glob matching, deny beating allow, and the orchestrator budget.
- [ ] (P1) Test contract.py and ticket.py
  Cover .loop.yml merge, the mini YAML fallback, junit and coverage parsing, and ticket frontmatter, state, and criteria ids.
- [ ] (P1) Test check_fields.py and check_stop.py
  Cover every ticket kind, the unknown kind error, the three stop exits, and both CLI entry paths.
- [ ] (P1) Test roles.py scope_hook and options_for
  Assert the full deny shape, the allow and read pass through, the path outside the repo, and the built options under the stub SDK.
- [ ] (P1) Test adapter.py and loop.py
  Cover the success path, the missing SDK, a raising query, out of scope files excluded from wrote, and main --table-only exiting 0.
- [ ] (P2) Replace the Taskfile test task and add a table task
  test runs pytest. table keeps the --table-only print.
- [ ] (P2) Fix the stale root references in SPEC.md, loop.py, and roleplan.py
  Point all three at the local files and the local tests instead of solutions/roleplan.py and loops/tests.
- [ ] (P2) Verify, render the roadmap, and open the pull request
  Run the full verify list, confirm no root imports leaked in, render the roadmap, and open a pull request against main.
