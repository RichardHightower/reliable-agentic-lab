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

Do not copy this folder into `labs/lab2_implementer/harness.py`. The Saturday stub wants `red_gate` / `score_attempt` / `run_loop`. This file exports `cast` / `build` / `backend`.


---

# Learning objectives

- Read `roleplan.LOOPS["implementer"]`
- Wire `tools=[...]` plus PreToolUse
- Print `--table-only` with no SDK and no key
- Pair this port with `sol2_implementer_deep_agents` when you want the eight steps to run


---

# Starting architecture

```
python3 harness.py --table-only
  └── roleplan.plan(contract, "implementer")
         five RolePlans, judge can_write False

python3 harness.py --repo CRM
  └── ClaudeAgentOptions
         agents for planner, test_implementer, code_implementer, judge
         permission_mode=dontAsk
         PreToolUse scope_hook on every writing role
```

No call to `implementer.run`.


---

# Scope. Two places, both required

`tools=[...]` decides whether a role can write at all.

`scope_hook` decides which paths. Deny envelope:

```
hookSpecificOutput.hookEventName = PreToolUse
hookSpecificOutput.permissionDecision = deny
```

A typo fails **open**. `max_turns=12` is per subagent, not the harness budget.


---

# Commands

```bash
cd solutions/sol2_implementer_agent_sdk
python3 harness.py --table-only
python3 harness.py --repo ../../work/northwind-field-crm
task test    # that is --table-only
```

`--table-only` with a missing repo still prints the table and exits 0.


---

# Expected table

Judge must print `no`. Code implementer allow `app/**, src/**`, deny `tests/**`.

If judge prints `yes`, the port is wrong. Stop.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Thought this ran T001 | config port | use Deep Agents `harness.py` |
| Judge writes `yes` | tools leaked Edit | strip judge tools |
| Fail-open writes | deny shape typo | full `hookSpecificOutput` |
| Copied into lab2 stub | wrong artifact | Saturday wants three functions |


---

# Validation

- [ ] table: five roles, judge `no`
- [ ] no `implementer.py` in this folder (on purpose)
- [ ] `task test` needs no key
- [ ] you can name the folder that actually runs the loop


---

# Recap

Config port, not a filled loop. Same table, different enforcement knob.

The eight steps live in `sol2_implementer_deep_agents`. This folder proves the table survived.

---

# Prerequisites

```bash
cd solutions/sol2_implementer_agent_sdk
python3 -c "import roleplan, roles, write_scope; print('ok')"
```

No API key. No CRM clone. `claude-agent-sdk` is only needed if you call `options_for` without stubbing.

Saturday Lab 2 still fills `labs/lab2_implementer/harness.py`. This folder is take-home.

---

# Files in this folder

```
SPEC.md  Taskfile.yml
adapter.py  contract.py  harness.py
roleplan.py  roles.py  write_scope.py
```

Missing on purpose: `implementer.py`, `gates.py`, `rubric.py`, `doers.py`, `tests/`.

---

# Same table, three enforcements

| Runtime | How judge cannot write |
|---|---|
| Saturday Claude | YAML tools omit Write |
| Agent SDK (this folder) | tools omit Edit/Write, plus PreToolUse |
| Deep Agents | subagent tools = `[read_file]` |

---

# Final checklist

- [ ] `--table-only` prints judge `no`
- [ ] code_implementer deny includes `tests/**`
- [ ] you did not copy this `harness.py` over the Saturday stub
- [ ] you know `sol2_implementer_deep_agents` is the live loop
