# Prompt for LangChain Deep Agents

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`harness.py` in this folder.

Rebuild the Module 2 implementer as a Python loop on LangChain Deep Agents.
This is the driver of T001. The finished answer is
`solutions/sol2_implementer_deep_agents/`. Read its
[SPEC.md](../../../solutions/sol2_implementer_deep_agents/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol2_implementer_deep_agents/HOW_TO_RUN.md),
and
[DESIGN_DOC.md](../../../solutions/sol2_implementer_deep_agents/DESIGN_DOC.md).

Do not copy these harness fences into this lab folder.

Python holds the loop. The model writes tests, then code. It does not score
the rubric.

Needs `deepagents>=0.7`.

```bash
cd solutions/sol2_implementer_deep_agents
claude
```

There is also a fill-one-file stub at `labs/takehome/deep-agents/`. Use that if
you only want to fill `loop.py`.

---

## Prompt 0: the things that will waste your hour

1. Three fences, all required. Tool list per subagent. Path check inside the
   write tool. Harness profile that hides `write_file` / `edit_file` /
   `delete` / `execute` and turns the default `general-purpose` subagent off.
   Leaving that subagent on is how a scoped agent writes `tests/**`.
2. Skills are mounted, not pasted. `skills/planner/SKILL.md`,
   `skills/test_implementer/SKILL.md`, `skills/code_implementer/SKILL.md`,
   `skills/judge/SKILL.md`. Do not paste them into subagent prompts.
3. `--doer reference` and `--doer none` need no SDK and no key. `--doer deep`
   needs both. Prove the loop with `--doer none` before you spend a token.
4. `task test-setup` creates `.venv`. Homebrew Python will refuse system pip.

---

## Prompt 1: the role table

```
Create roleplan.py. Cast: orchestrator, planner, test_implementer,
code_implementer, judge.

test_implementer owns tests/**.
code_implementer owns app/** and is denied tests/**.
planner owns steps.jsonl.

task table. The judge must print no. If it prints yes, stop.
```

---

## Prompt 2: the three fences

```
Create roles.py. Use all three layers from SPEC.md.

The code implementer cannot weaken a test to reach green, because it holds
no write path to one. Pin that with tests that need no SDK.
```

---

## Prompt 3: the eight-step loop

```
Plan, write tests, check the red gate, write code, score, decide.

red_gate(before, after) is new failing ids, not any failing ids.

Three exits, no fourth: pass, retry, escalate.
```

---

## Verify

```bash
cd solutions/sol2_implementer_deep_agents
task test-setup
task table
task test
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer none
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
```

Then, with a key: `--doer deep`.

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol2_implementer_deep_agents/, behavior
first, wording second. I will decide what to change.
```
