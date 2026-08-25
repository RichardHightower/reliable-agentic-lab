# Module 2 instructions

Known-good CRM is already green. First run should pass with maker `none`.

```bash
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker none
```

To watch fail then pass, point the CRM at a broken tree and use `--maker reference`.
Module 1 already shows that path on a starter copy.

## Talking points

- Why Maker needs a Checker with fewer tools.
- Spec-driven development as a testable contract.
- Graph nodes: orchestrator, grader, rubric, gate.
- Read `traces/last-loop.json`. Know when to stop.

## Stop rules

- Pass: hidden grader green.
- Retry: new failure signature, budget remains.
- Escalate: repeated failure signature, or budget spent.

Default budget is 3.

## Do not

- Do not make Langfuse the lab. It is a pane on the output.
- Do not teach Deep Agents as a product tour. Show sub-agent tool scope.
