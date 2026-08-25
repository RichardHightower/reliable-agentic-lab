# Rubric: T001 due dates

Source of truth: `harness/tickets/T001-due-dates.ready.md`.

| Check | How | Weight |
| --- | --- | --- |
| Model has optional `due_date` | SQLAlchemy inspect | required |
| Null due dates stay valid | API create without field | required |
| ISO 8601 write and read | API create `2026-09-15` | required |
| `due_before` filter | API query | required |
| `overdue` filter | API query, open + past UTC date | required |
| Form field `due_date` | HTML `name="due_date"` | required |
| HTML list filters | `/tasks?overdue=true` and `due_before` | required |

Score schema:

```json
{
  "ticket_id": "T001",
  "passed": false,
  "failed_checks": [],
  "pytest_exit_code": 1,
  "iterations": 0,
  "gate": "retry"
}
```

Gate: pass if every required check is green. Retry if pytest fails and budget
remains. Escalate if the same failure repeats twice or the budget is gone.
