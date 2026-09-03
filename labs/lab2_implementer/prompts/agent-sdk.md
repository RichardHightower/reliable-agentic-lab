# Prompt for Claude Agent SDK

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`harness.py` in this folder.

Rebuild the Module 2 implementer as a Python loop on Claude Agent SDK. The
finished answer is `solutions/sol2_implementer_agent_sdk/`. Read its
[SPEC.md](../../../solutions/sol2_implementer_agent_sdk/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol2_implementer_agent_sdk/HOW_TO_RUN.md),
and [DESIGN_DOC.md](../../../solutions/sol2_implementer_agent_sdk/DESIGN_DOC.md).

This port is a standalone driver, the same eight-step loop as the Deep Agents
twin. Demo T001 from this folder with `--doer reference` (no key) or
`--doer sdk` (needs the SDK). Do not copy these fences into this lab folder.

Python holds the loop. The model writes tests, then code. It does not score
the rubric. It does not decide Pass, Retry, or Escalate.

```bash
cd solutions/sol2_implementer_agent_sdk
claude
```

There is also a fill-one-file stub at `labs/takehome/agent-sdk/`. Use that if
you only want to fill `loop.py`. Use this prompt if you are building the
whole port.

---

## Prompt 0: the things that will waste your hour

1. One hook for the whole cast, not one per writer. Registering one hook per
   writing role does not survive three writers: every hook runs on every
   Write, `{}` means "no opinion", and the code implementer writing
   `tests/test_x.py` is denied by its own hook and waved through by the test
   implementer's. The effective scope becomes the union of all three allow
   lists.
2. The hook reads `agent_type` off the tool call. A write with no
   `agent_type` came from the parent. The parent does not write.
3. No role holds `Bash`. Python runs the suite through `contract.run("test")`.
   A shell buys the cast nothing and costs it the fence: the hook matches
   Edit, Write, and NotebookEdit, and none of those is `sed -i`.
4. `task setup` creates `.venv`. Homebrew Python will refuse system pip
   (PEP 668).

---

## Prompt 1: the role table

```
Create roleplan.py. Cast: orchestrator, planner, test_implementer,
code_implementer, judge.

test_implementer owns tests/**.
code_implementer owns app/** and is denied tests/**.
planner owns steps.jsonl.
orchestrator and judge write nothing.

python harness.py --table-only --repo ../../work/northwind-field-crm
The judge must print no. If it prints yes, stop.
```

---

## Prompt 2: the two fences

```
Create roles.py.

tools=[...] decides whether a role can write at all.
One PreToolUse hook decides which paths it may write. Deny with the full
hookSpecificOutput envelope. Returning {} fails open.

Translate the cast one role at a time. cast(contract) returns a RolePlan.
build(contract) turns those into ClaudeAgentOptions.
```

---

## Prompt 3: the loop

```
Fill the eight-step loop. Plan, write tests, check the red gate, write code,
score with the local rubric, then decide with the local gates.

red_gate(before, after) is new failing ids, not any failing ids. A test that
already existed and still fails is not proof of a new contract.

Three exits, no fourth: every rubric row passes; the same rows fail twice;
the iteration or money budget is spent.
```

---

## Verify

```bash
cd solutions/sol2_implementer_agent_sdk
task setup
task table
task test
```

Live T001 from this folder:

```bash
cd solutions/sol2_implementer_agent_sdk
task run -- --ticket T001 --doer reference
task run -- --ticket T001 --doer sdk
```

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol2_implementer_agent_sdk/, behavior
first, wording second. I will decide what to change.
```
