---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol4_fixer_deep_agents

Configuration port. It does **not** run the fixer.

This is the role graph. The live harness is `sol4_fixer_agent_sdk`.

No `fixer.py`, `gates.py`, or `doers.py`. `task test` runs the folder's own suite.


---

# What it proves

```
role                writes  scope
orchestrator        no      nothing
code_implementer    yes     app/**, src/**   denied tests/**
judge               no      nothing
```

Live repair is `sol4_fixer_agent_sdk`. `backend(contract)` exists. `main` never calls it.


---

# Learning objectives

- Read `LOOPS["fixer"]` (three roles, no planner)
- Hand the coder a scoped write tool
- Hand the judge `read_file` only
- Refuse `tests/**` with a sentence
- Name the folder that actually repairs `broken-pr`


---

# Starting architecture

```
python loop.py --table-only
  └── three RolePlans

python loop.py --repo CRM
  └── create_deep_agent subagents
         code-implementer: read_file + write_code_implementer
         judge: read_file
```

No while loop. No junit. No comment.


---

# Scoped write tool

```python
@tool(f"write_{role.name}")
def write(path: str, content: str) -> str:
    try:
        scope.check(path)
    except ScopeViolation:
        return f"REFUSED. {role.name} may write {allowed}. {path} is outside that scope."
```

Deny `tests/**`. Allow `app/**`, `src/**`. Refusal is a string, not an exception.


---

# Commands

```bash
cd solutions/sol4_fixer_deep_agents
python loop.py --table-only --repo ../../work/northwind-field-crm
python loop.py --repo ../../work/northwind-field-crm
task test
```

Missing repo plus `--table-only`: prints declared scopes, exit 0. Without `--table-only`, `ContractError` raises.


---

# Expected table

Judge prints `no`. Code implementer prints `yes` with deny `tests/**`.

If judge prints `yes`, stop.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Expected a green branch | config port | Agent SDK folder |
| Judge writes `yes` | write tool handed to judge | tools = `[read_file]` |
| Raises on missing repo | forgot `--table-only` | table-only is the self-check |


---

# Validation

- [ ] table: three roles
- [ ] judge `no`
- [ ] coder denied `tests/**`
- [ ] you can name `sol4_fixer_agent_sdk` as the live loop


---

# Recap

Same table, Deep Agents enforcement knob. This is graph without a loop. Use the Agent SDK folder when you want a green branch or an honest comment.

---

# Prerequisites

```bash
cd solutions/sol4_fixer_deep_agents
python loop.py --table-only
```

`DEFAULT_LOOP` and `LOOP` are both `"fixer"`. They were not. This copy inherited `"implementer"` from the shared `roleplan.py` the repo deleted, so a bare `roleplan.plan(contract)` built five roles instead of three.

A caller still names its loop at every site. The default agreeing with it is the belt to that suspenders, and a test in the folder pins both.

---

# Files in this folder

```
SPEC.md  Taskfile.yml
adapter.py  contract.py  loop.py
roleplan.py  roles.py  write_scope.py
skills/  memory/  tests/
```

Missing on purpose: `fixer.py`, `doers.py`, `gates.py`. This port is the graph
without the loop. The tests pin the graph.

`skills/` and `memory/` are mounts, not a fourth fence. A skill loads its
instructions when the role is invoked, rather than sitting in every prompt from
the start. `memory/` holds one file, so routing it does not hand the agent this
folder's own source.

---

# Why three roles, not five

The work is already defined by what is red. No planner. No test implementer. The judge reads junit. The coder may write `app/**` and may not write `tests/**`.

---

# Final checklist

- [ ] `LOOP = "fixer"`
- [ ] table: three rows, judge `no`
- [ ] coder write tool refuses `tests/**`
- [ ] live repair is `sol4_fixer_agent_sdk`
