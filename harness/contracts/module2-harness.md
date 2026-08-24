# Module 2 harness contract

Paper contract for Monday. Do not turn this into a product tour.

## Inputs

- Path to a ready ticket markdown file.
- Path to the CRM checkout the Maker may edit.
- Budget: max iterations, max tool calls, max tokens if known.
- Grader command: `pytest harness/graders/test_due_date_contract.py -q`.

## Orchestrator

Runs the loop. Holds the budget. Sees summaries and scores only.
Does not receive raw repo dumps or full file bodies.

## Maker sub-agent

Edits code to satisfy the ready ticket.

Allowed tools:

- Read files under `crm/`.
- Write files under `crm/`.
- Run CRM smoke tests and the hidden grader.

Forbidden tools:

- Change ticket state.
- Edit `harness/graders/`.
- Merge a pull request.
- Talk to production.

## Checker sub-agent

Reads the diff and the grader output.

Allowed tools:

- Read the diff.
- Read pytest output.
- Read the ready ticket and rubric.

Forbidden tools:

- Write files.
- Change tickets.

## Stop rules

1. Pass: hidden grader exits 0.
2. Retry: grader fails and iteration is under budget and the failure signature is new.
3. Escalate to human: same failure signature twice, or budget exhausted, or Maker wants to edit graders.
4. Stop: escalate or pass.

## Score schema

```json
{
  "ticket_id": "T001",
  "iteration": 1,
  "passed": false,
  "failed_node_ids": ["test_model_has_optional_due_date"],
  "repeat_failure": false,
  "gate": "retry",
  "trace_id": "local-or-langfuse"
}
```

## Trace schema (Langfuse or local JSON)

Each loop write one object under `harness/traces/`:

- `trace_id`
- `ticket_id`
- `iteration`
- `maker_summary`
- `checker_summary`
- `tool_calls`
- `pytest_output`
- `score`

Cloud Langfuse is optional. Local files keep the same keys.
