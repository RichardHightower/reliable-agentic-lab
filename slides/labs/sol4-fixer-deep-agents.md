---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol4_fixer_deep_agents

Configuration port. It does **not** run the fixer.

No `fixer.py`, `gates.py`, `doers.py`, or tests. `task test` is `--table-only`.


---

# What it proves

```
role                writes  scope
orchestrator        no      nothing
code_implementer    yes     app/**, src/**   denied tests/**
judge               no      nothing
```

```bash
cd solutions/sol4_fixer_deep_agents
python loop.py --table-only --repo ../../work/northwind-field-crm
```

Judge must print `no`. Subagents: code-implementer gets a scoped write tool; judge gets `read_file` only. Refusal is a string.

`backend(contract)` exists. `main` never calls it. Live repair is `sol4_fixer_agent_sdk`.


---

# Recap

Same table, Deep Agents enforcement knob. Use the Agent SDK folder when you want a green branch or an honest comment.
