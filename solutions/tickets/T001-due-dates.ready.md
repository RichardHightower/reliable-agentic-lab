---
id: T001
title: Customers need to know when tasks are due
state: ready
loop: implementer
---

# Customers need to know when tasks are due

Sales people keep missing follow-ups. Add due dates to tasks.

## Success criteria

- `sales_tasks.due_date` is a date field, optional, ISO 8601, stored UTC.
- Existing tasks stay valid with a null due date. Do not require a backfill.
- The new-task form shows a `due_date` field named `due_date`.
- `GET /api/tasks` and `GET /tasks` accept `due_before=<ISO date>`.
- `GET /api/tasks` and `GET /tasks` accept `overdue=true`.
- Overdue means status is `open` and `due_date` is before today's UTC date.
- Accept `YYYY-MM-DD` or a full ISO 8601 timestamp on write.
- Return the stored date as ISO 8601 on the API.
- Hidden grader tests cover model, API, and filters.
- Do not hardcode seed customer names in filters or tests.

## Out of scope

- Time-of-day reminders.
- Recurring tasks.
- Calendar integrations.
