# Northwind Field CRM

Sample customer relationship management (CRM) app for the workshop.
Customers. Sales tasks. FastAPI. SQLite. Thin Jinja templates. Docker.

This is the **known-good** app. Due dates already work. Hidden grader tests
in `solutions/m2-harness/graders` pass against this tree.

Attendees do not build this live. They clone it. The starter copy without
due dates lives in `solutions/m1-implementer/starter_crm`.

## Docs

- [SETUP.md](SETUP.md)
- [INSTRUCTIONS.md](INSTRUCTIONS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## What is in here

| Path | Role |
|---|---|
| `app/main.py` | Routes. HTML plus JSON API. |
| `app/models.py` | `Customer` and `SalesTask`. `due_date` is optional UTC. |
| `app/dates.py` | Parse and serialize ISO 8601 due dates. |
| `app/db.py` | SQLite engine. Isolated in-memory engine for tests. |
| `app/seed.py` | Three customers. Five tasks. Null due dates on seed rows. |
| `app/templates/` | Home, customers, task list, new-task form. |
| `tests/test_smoke.py` | Boot and create a customer plus a task. |

## First graded ticket

Add a due date on sales tasks. That ticket is already implemented here.
The vague draft is `solutions/tickets/T001-due-dates.md`.
The ready contract is `solutions/tickets/T001-due-dates.ready.md`.
