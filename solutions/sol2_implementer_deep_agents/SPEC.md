# Spec. Lab 2. Ticket Implementer on LangChain Deep Agents

The same eight steps as `sol2_implementer/implementer.py`. A different runtime
for the makers. Python still owns the red gate and the three exits.

## Cast

orchestrator, planner, test_implementer, code_implementer, judge.

`create_deep_agent` is the harness. The orchestrator holds `run_tests` and
`task`. It holds no write tool. Each subagent gets its own `tools` list, which
**replaces** the parent. The judge's list is `read_file` only.

## What Python still owns

1. Ready ticket in.
2. Plan schema in `steps.jsonl`.
3. Red gate over `reports/junit.xml`.
4. Ten-row rubric. No model.
5. `gates.decide`. Pass, retry, escalate. Same signature twice means stop.

## Run

```bash
cd solutions/sol2_implementer_deep_agents
python3 -m pytest tests -q
python3 harness.py --table-only
# live, after task setup:
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer deep
```

`--doer deep` needs `deepagents` installed. The tests do not.

## What this folder is not

Not a second loop engine. Not Saturday's lab. Saturday fills `harness.py` under
`labs/lab2_implementer` with Claude Code.
