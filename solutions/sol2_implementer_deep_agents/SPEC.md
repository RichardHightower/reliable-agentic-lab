# Spec. Lab 2. Ticket Implementer on LangChain Deep Agents

The same eight steps as the Module 2 implementer. A different runtime
for the makers. Python still owns the red gate and the three exits.

## Cast

orchestrator, planner, test_implementer, code_implementer, judge.

`create_deep_agent` is the harness. The orchestrator holds `run_tests` and
`task`. It holds no write tool. Each subagent gets its own `tools` list, which
**replaces** the parent. The judge's list is `read_file` only.

## How this runtime enforces scope

This port scopes in three places. All three have to hold, not just one.

No role holds `Bash`. This runtime has no `Bash` tool to grant or refuse. The
nearest built-in is `execute`, and `ORCHESTRATOR_EXCLUDED_TOOLS` removes it
from the orchestrator (`roles.py:43`, `roles.py:254`). No subagent spec adds
`execute` back. `subagents_for` attaches only the shared reader and, for a
writing role, one scoped write tool (`roles.py:201-203`). `execute` never
reaches any role in this cast.

A subagent tool list replaces the parent list. `subagents_for` builds a
`tools` list per role and stores it on that role's spec (`roles.py:201-208`).
A subagent runs with that list only. It does not inherit the orchestrator's
tools, and the orchestrator does not inherit a subagent's. The orchestrator
itself never holds a built-in write tool. `ORCHESTRATOR_EXCLUDED_TOOLS` names
`write_file`, `edit_file`, `delete`, and `execute` (`roles.py:43`), and
`build_agent` passes that set into the harness profile the orchestrator's
model runs under (`roles.py:254`).

Tool access answers whether a role can write at all. It does not answer
which paths. `scoped_write_tool` builds each writer's write tool around a
`WriteScope` made from that role's own `allow` and `deny` lists
(`roles.py:110-131`). `WriteScope.check` refuses a path outside that scope
before the tool ever calls `_inside` or touches disk. `permission_rules`
declares the same scope again, for the harness's own permission layer
(`roles.py:170-190`). It denies a role's `deny` patterns first, allows its
`allow` patterns second, and falls through every role to `DENY_EVERY_WRITE`
last. Deny wins over allow in both layers, so they cannot disagree.

The judge holds `read_file` only. The judge cannot write, so `subagents_for`
skips the write branch for it and leaves `tools = [reader]`
(`roles.py:201-203`). `reader` is the `read_file` tool (`roles.py:134-147`).
The judge subagent gets that one tool and nothing else.

`virtual_mode` is routing, not a security boundary. `build_agent` mounts the
target repo with `FilesystemBackend(root_dir=str(repo), virtual_mode=True)`
(`roles.py:281`). A built-in filesystem tool then sees paths relative to the
repo root, not the real filesystem root. The mount does not stop a
custom tool from walking `..` off the repo on its own. `_inside` is the real
boundary. It resolves the requested path against the repo root and refuses
anything that lands outside it. Both `read_file` and the scoped write tool
call `_inside` before they touch disk (`roles.py:92-107`, `roles.py:124`,
`roles.py:140`).

Orchestrator `permissions` deny writes. `build_agent` passes
`permissions=[FilesystemPermission(**DENY_EVERY_WRITE)]` to
`create_deep_agent` (`roles.py:293`). `DENY_EVERY_WRITE` denies every write
path (`roles.py:47`). This is a second layer under
`ORCHESTRATOR_EXCLUDED_TOOLS`. Even if a later change gave the orchestrator a
write tool, the declared permission would still refuse the call.

The general-purpose subagent is off. Deep Agents ships one by default, with
its own filesystem tools. `build_agent` registers a harness profile with
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`
(`roles.py:255`). Without that line, the harness would still offer a generic
subagent that can write anywhere in the repo.

## What Python still owns

1. Ready ticket in.
2. Plan schema in `steps.jsonl`.
3. Red gate over `reports/junit.xml`.
4. Ten-row rubric. No model.
5. The final judge's JSON. Unparseable is `done=False`.
6. `gates.decide`. Pass, retry, escalate. Same signature twice means stop.
   A retry carries the failed rows and the failing test ids.

LangChain `usage_metadata` has token counts, not dollars. This port prices
those tokens at Sonnet-class rates so the money exit can fire. That number is
an estimate, not a bill.

## Run

See `HOW_TO_RUN.md`. The short path:

```bash
cd solutions/sol2_implementer_deep_agents
cp config.json.example config.json
task test
task table
task setup
task clone
task run -- --ticket T001 --doer reference
task run -- --ticket T001 --doer deep
```

`task test` and `task table` need no SDK. `--doer deep` needs `task setup`.

Each writing role with a skill directory mounts `/skills/<role>/`. The body
is not pasted into the system prompt. `/memory/` routes at `memory/`, not
this folder.

## The run, resumed, cleaned up, and planned

`implementer.main` takes four flags beyond `--repo`, `--ticket`, and
`--budget`. `--doer` accepts `none`, `reference`, `reference:<ref>`, or
`judge-no`. It never accepts a CLI name; a coding CLI is not a doer this
folder builds. `--planner` accepts `derived`, `sdk`, or `deep`, and defaults
to `derived`, which is `plan_for` and calls no model. `--doer none` and
`--doer reference` force `derived` regardless of the flag.

Every run happens inside an isolated git worktree at
`<repo>.worktrees/<ticket>`, on branch `implementer/<ticket>`. The target
repo you pass with `--repo` is never written to. `--cleanup` removes the
worktree and its branch after the run; without it, the worktree stays so
you can inspect it, or push from it. `--resume` re-enters a killed run from
that worktree's own `.harness/state.json`, instead of starting over.

`state.json` sits beside the receipt. It carries the run count, the last
gate, the last reason, the last run time, the loop name, the phase, the
red test ids, the preexisting files, the test-phase files, and the
test-phase attempt count: ten fields in all. A `state.json` that will not
parse, or holds the wrong type for one of those fields, is corrupt, and a
corrupt state starts no work.

`main` returns one of three exit codes: `0` on pass, `2` on escalate, `1`
on a `ContractError` or a corrupt state. Retry never becomes an exit code,
because `run()` only returns on a terminal gate.

## What this folder is not

Not a second loop engine. Not Saturday's lab. Saturday fills `harness.py` under
`labs/lab2_implementer` with Claude Code.
