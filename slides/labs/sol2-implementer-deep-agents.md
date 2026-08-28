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

# What this folder actually is

| File | Role |
|---|---|
| `harness.py` | `red_gate`, `run_loop`, CLI `--table-only` / `--doer` |
| `implementer.py` | eight-step loop (278 lines) |
| `doers.py` | `none` / `reference` / `cli` / Deep Agents backend |
| `rubric.py` / `gates.py` / `contract.py` | copies, not imports from a library |
| `roles.py` | `create_deep_agent`, per-subagent tools |
| `tests/` | judge read-only, refuse `tests/**`, red-gate ids, same-signature escalate |


---

# Eight steps in `implementer.run`

1. Read ticket. Refuse if not `ready`.
2. Planner writes `steps.jsonl`. `Plan.validate` requires a validation statement and at least one `test_implementer` step.
3. `test_implementer` writes under `tests/**`.
4. Red gate on `reports/junit.xml`. Empty new-ids → escalate.
5. `code_implementer` writes `app/**`, denied `tests/**`, until green.
6. Ten-row rubric. No model.
7. Final judge is described in the Session 2 deck. This port passes `judge_done=None`, so a green rubric is enough.
8. `gates.decide`. Trace → `.harness/last-implementer.json`.


---

# Deep Agents wiring

```python
return create_deep_agent(
    model="anthropic:claude-sonnet-5",
    tools=[run_tests_tool(repo)],   # orchestrator runs tests, cannot edit them
    subagents=subagents_for(contract, loop),
)
```

Judge tools = `["read_file"]`. Code-implementer write tool refuses `tests/**` with a sentence, not an exception.

`create_deep_agent` does **not** count retries. Python still owns `gates.decide`.


---

# Commands

```bash
cd solutions/sol2_implementer_deep_agents
python3 -m pytest tests -q
python3 harness.py --table-only
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer none
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer deep
```

`--doer deep` needs `deepagents` and `ANTHROPIC_API_KEY`. Tests do not.


---

# Recap

Same role table as Saturday. Enforcement is a missing tool on the subagent, plus a path check inside the write tool, plus Python on the outside.

If a port imports `loops`, the design leaked. `test_standalone.py` greps for that import and fails the build.
