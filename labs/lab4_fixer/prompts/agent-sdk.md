# Prompt for Claude Agent SDK

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`loop.py` in this folder.

Rebuild the broken-PR fixer as a Python loop on Claude Agent SDK. This is the
live unattended driver. The finished answer is
`solutions/sol4_fixer_agent_sdk/`. Read its
[SPEC.md](../../../solutions/sol4_fixer_agent_sdk/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol4_fixer_agent_sdk/HOW_TO_RUN.md), and
[DESIGN_DOC.md](../../../solutions/sol4_fixer_agent_sdk/DESIGN_DOC.md).

Do not copy these fences into this lab folder. The Deep Agents twin is a
config port of the graph, not the live loop.

Python is the harness. The model edits `app/**`. It does not edit `tests/**`,
it does not merge, and it does not run a shell.

Unattended contract is `dontAsk`, not `acceptEdits`.

```bash
cd solutions/sol4_fixer_agent_sdk
claude
```

---

## Prompt 0: the things that will waste your hour

1. `permission_mode` is `dontAsk`. `acceptEdits` still asks. Unattended means
   the hook decides, not a human in the loop.
2. Demo `broken-pr` from this folder. `task reset` checks out that branch and
   refuses if the clone still holds work from an earlier lab.
3. One PreToolUse hook. Code implementer owns `app/**` and is denied
   `tests/**`. Judge holds no write tool. No Bash. Python runs
   `contract.run("test")`.
4. Four stops, no fifth: tests green; same failures twice; budget spent;
   human merge. The loop never gets a merge tool.
5. `task setup` creates `.venv`. Homebrew Python will refuse system pip.

---

## Prompt 1: the role table

```
Create roleplan.py. Cast: orchestrator, code_implementer, judge.

code_implementer owns app/**, denied tests/**.
orchestrator and judge write nothing.

task table. The judge must print no. If it prints yes, stop.
```

---

## Prompt 2: the two fences

```
Create roles.py.

tools=[...] decides whether a role can write at all.
One PreToolUse hook decides which paths. Deny with the full
hookSpecificOutput envelope. Returning {} fails open.

Parent may only spawn a subagent. The parent does not write.
```

---

## Prompt 3: the loop

```
fixer.run: judge via contract.run("test") to junit, then code_implementer
on app/**. Optional research once (2 calls, $0.05). Write
.harness/last-fixer.json.

Human merge. Loop never gets a merge tool.

dontAsk. Not acceptEdits.
```

---

## Verify

```bash
cd solutions/sol4_fixer_agent_sdk
task setup
task table
task test
task clone
task reset          # broken-pr. Refuses a dirty clone.
task run
```

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol4_fixer_agent_sdk/, behavior first,
wording second. I will decide what to change.
```
