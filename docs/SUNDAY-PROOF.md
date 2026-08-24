# Sunday proof

Done when hidden tests fail on the starter and pass on a known-good branch.

## Fail on starter

`sales_tasks` has no `due_date`.
The new-task form has no `due_date` field.
`GET /api/tasks` ignores `due_before` and `overdue`.

## Pass on known-good

Instructor implementation of T001 ready contract.

- Optional `due_date` on `SalesTask`.
- ISO 8601 write and read.
- Null due dates stay valid.
- Filters: `due_before`, `overdue`.
- Form field `name="due_date"`.
