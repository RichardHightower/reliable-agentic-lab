---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol2_implementer_deep_agents

The working filled Lab 2 loop. Take-home issue 118.

Python holds Pass / Retry / Escalate. Deep Agents is the maker. The red gate is `junit.xml`.


---

# What this folder is

| File | Role |
|---|---|
| `harness.py` | `red_gate`, `run_loop`, CLI |
| `implementer.py` | eight-step loop |
| `doers.py` | `none` / `reference` / `cli` / Deep Agents |
| `rubric.py` / `gates.py` / `contract.py` | copies, not a library |
| `roles.py` | `create_deep_agent` |
| `tests/` | judge read-only, refuse `tests/**` |


---

# Why it exists

Saturday fills three stubs. There is no drop-in `harness.py`. This folder is the shipped eight-step answer.

`task loop:implementer` is gone from the root Taskfile. Demo from here. Each criterion becomes two nodes in `steps.jsonl`.


---

# Learning objectives

- Walk `implementer.run` step by step
- Prove `--doer none` escalates
- Prove `--doer reference` can pass under WriteScope
- Configure Deep Agents so the judge holds `read_file` only
- Grep for `from loops` and fail if it returns


---

# Starting architecture

```
orchestrator  writes nothing, owns budget
  planner            steps.jsonl
  test_implementer   tests/**
  code_implementer   app/**, denied tests/**
  judge              read_file only
           │
           ▼
     red gate  →  ten-row rubric  →  gates.decide
           │
           ▼
     .harness/last-implementer.json
```


---

# Eight steps in `implementer.run`

1. Read ticket. Refuse if not `ready`.
2. `plan_for`: one test step and one code step per criterion. Derived, not generated. This is Graph Engineering. Not LangGraph.
3. `test_implementer` writes under `tests/**`.
4. Red gate. Empty new-ids → escalate.
5. `code_implementer` writes `app/**` until green.
6. Ten-row rubric. No model.
7. `judge_done=None`, so a green rubric is enough. Session 2 still teaches a model judge.
8. `gates.decide`. Trace to `.harness/last-implementer.json`.


---

# Red gate

```python
def _new_test_ids(before: set[str], after_failed: set[str]) -> set[str]:
    return {test_id for test_id in after_failed if test_id not in before}
```

A test that already existed and still fails is not proof of a new contract.

`--doer none` hits this every time. If that run were green, the harness would be lying.


---

# Deep Agents wiring

```python
return create_deep_agent(
    model="anthropic:claude-sonnet-5",
    tools=[run_tests_tool(repo)],
    subagents=subagents_for(contract, loop),
)
```

Judge tools = `["read_file"]`. Code-implementer write tool refuses `tests/**` with a sentence.

`create_deep_agent` does **not** count retries. Python still owns `gates.decide`.


---

# Commands

```bash
cd solutions/sol2_implementer_deep_agents
python3 -m pytest tests -q
python3 harness.py --table-only
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer none
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer deep
```

`--doer deep` needs `deepagents` and a key. Tests do not.


---

# Expected results

`--doer none`:

```
gate: escalate
reason: red gate: no new test was observed failing.
```

`--doer reference`: copies `known-good` into `tests/**` then `app/**`, each phase bound by that role's WriteScope. Ten PASS rows. `gate: pass`.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `task loop:implementer` missing | engine deleted | run this `harness.py` |
| `--doer none` is green | red gate not stopping | empty new-ids must escalate |
| Wrote `tests/**` as coder | write tool not scoped | sentence refusal |
| `from loops` in a file | design leaked | `test_standalone.py` fails the build |


---

# Validation

- [ ] pytest: judge tools `== ["read_file"]`
- [ ] coder write to `tests/test_due.py` returns REFUSED
- [ ] `_new_test_ids({"old"}, {"old","new"}) == {"new"}`
- [ ] same signature twice → `ESCALATE`
- [ ] `--table-only` prints `judge` with no repo


---

# Recap

Same role table as Saturday. Enforcement is a missing tool, plus a path check, plus Python on the outside.

If a port imports `loops`, the design leaked.
