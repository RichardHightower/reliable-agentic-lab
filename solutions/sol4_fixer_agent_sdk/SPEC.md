# Spec. Lab 4. Unattended PR fixer on Claude Agent SDK

A failing branch in, a green one out, or an honest explanation.

Use `query()`, not `ClaudeSDKClient`. Nobody is chatting. Merge is never a
tool.

## The cast for this loop

- `orchestrator`
- `code_implementer`
- `judge`

`roleplan.py`, in this folder, is where that list lives. Read it there. Do not
restate a scope anywhere else.

The code implementer owns `app/**` and is denied `tests/**`. A fixer that can
edit the failing test does not have to fix anything. The judge holds no write
path at all.

No role holds `Bash`. The judge used to, and a shell is the path around the
hook below: the hook matches `Edit`, `Write`, and `NotebookEdit`, and none of
those is `sed -i`. Python runs the suite through `contract.run("test")` and
parses the report, so the judge reads files and nothing else.

## How this runtime enforces scope

Two places, and you need both.

    permission_mode + tools     decides whether a role can write at all
    PreToolUse hook             decides which paths it may write

`permission_mode` is `dontAsk`.

It used to be `acceptEdits`, and that is the single most important line in this
folder. `acceptEdits` auto-accepts every file edit *before* the allow list is
consulted, so the hook became the only fence. The hook fails open on a typo, by
its own docstring. One gate, on a loop that runs with nobody watching.

The argument for `acceptEdits` was "nobody is chatting". That is the argument
for `dontAsk`. The SDK defines the two as:

    acceptEdits   auto-accept file edit operations
    dontAsk       do not prompt; deny anything not pre-approved

Both never prompt. Only one fails closed. Under `dontAsk`, `allowed_tools` is
the enforced boundary, which is the second gate `acceptEdits` gave away.

One hook serves the cast, and it reads `agent_type`. This loop has one writer,
so a closure bound per role would be correct today and would stop being correct
the moment a second writer existed. A write that arrives with no `agent_type`
came from the parent, and the parent has no business writing anything.

## What Python still owns

`summarize_failure` from junit. Three exits: the suite is green; the same
failing ids twice; the budget spent, with a comment that says so. Giving up
silently is the bug.

The money exit was unreachable until now. `fixer.py` calls
`boss.spend(result.usd)` and `gates.decide` has a live `usd_left <= 0` branch,
but `adapter.py` called `str(message)` and never read `total_cost_usd`, so
`usd` was always `0.0`. An unattended fixer with a dead money gate is the
surprise bill `gates.py` says it exists to prevent. The adapter reads
`ResultMessage` now, and `max_budget_usd` reaches the SDK.

## Build it step by step

1. Install the runtime.

   ```bash
   task setup
   ```

2. Read the cast before you configure anything.

   ```bash
   task table
   ```

   The judge must print `no` in the writes column. If it prints `yes`, stop.

3. Run the checks.

   ```bash
   task test
   ```

## Verify

```bash
task test
task table
```

Those checks need no SDK, no key, no network, and no clone. They assert:

- The cast is exactly the three fixer roles, and the judge and the
  orchestrator hold no write path.
- The code implementer is denied `tests/**`, and the deny envelope is correct
  key by key, because a typo in it fails open.
- A write with no `agent_type` is denied, and one hook is registered per write
  tool.
- `permission_mode` is `dontAsk`. That assertion used to read `acceptEdits`
  and was pinning the bug.
- No role holds `Bash`, and `Bash` is denied at the options level.
- `maxTurns` reaches the SDK, not `max_turns`, which raises `TypeError` on the
  real thing. The fake is an explicit dataclass for that reason. The old one
  took `**kwargs`, so it accepted any spelling and the suite passed over a call
  that could never run.
- The adapter reports what a turn cost, and the money gate fires on it.
- Every module imports with no SDK, no two modules are byte-identical, and
  every `task` this document names exists in the Taskfile.

## Run

The live operator path is [HOW_TO_RUN.md](HOW_TO_RUN.md). `task setup` creates
`.venv` in this folder. `task clone` then `task reset` checks out `broken-pr`.

```bash
cd solutions/sol4_fixer_agent_sdk
task table
task run -- --repo ../../work/northwind-field-crm --branch broken-pr --doer reference
task run -- --repo ../../work/northwind-field-crm --branch broken-pr --doer sdk
```

`--doer sdk` needs `claude-agent-sdk`. The tests stub it.

`--research` defaults to `off`. It defaulted to `fixture` and pointed at
`fixtures/research.json`, a file this folder has never had, so the documented
default could not run. Asking for it now names the missing file.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a
shared engine.

`loop_roles.py` used to be a byte-for-byte copy of `write_scope.py`, 180 lines
reached through three import names. One of them is gone, and a test keeps two
modules from ever being identical again.
