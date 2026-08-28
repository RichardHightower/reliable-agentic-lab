---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol2_implementer_agent_sdk

Take-home **configuration port**. It does not run the eight-step loop.

It prints the role table and builds `ClaudeAgentOptions`. There is no `implementer.py`, no `gates.py`, no `rubric.py`, no `tests/`.


---

# What it proves

The role table survived the runtime swap.

```
role                writes  scope
orchestrator        no      nothing
planner             yes     steps.jsonl
test_implementer    yes     tests/**
code_implementer    yes     app/**, src/**   denied tests/**
judge               no      nothing
```

```bash
cd solutions/sol2_implementer_agent_sdk
python3 harness.py --table-only
python3 harness.py --repo ../../work/northwind-field-crm
```

`--table-only` needs no SDK and no key. `task test` is that command.


---

# Scope. Two places, both required

`tools=[...]` decides whether a role can write at all.

`PreToolUse` `scope_hook` decides which paths. Deny envelope:

```
hookSpecificOutput.hookEventName = PreToolUse
hookSpecificOutput.permissionDecision = deny
```

A typo fails **open**. `permission_mode="dontAsk"`. `max_turns=12` is per subagent, not the harness budget.

Do not copy this folder into `labs/lab2_implementer/harness.py`. The Saturday stub wants `red_gate` / `score_attempt` / `run_loop`. This file exports `cast` / `build` / `backend`.


---

# Recap

Config port, not a filled loop. Pair it with `sol2_implementer_deep_agents` when you want the eight steps to actually run. Same table, different enforcement knob.
