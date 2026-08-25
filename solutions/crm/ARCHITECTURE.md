# CRM architecture

Boring on purpose.

```
Browser
  -> FastAPI (Jinja HTML + JSON)
       -> SQLAlchemy
            -> SQLite file, or in-memory for tests
```

## Data

- `customers`: name, email, company
- `sales_tasks`: title, status, notes, optional `due_date`

`due_date` is `DateTime(timezone=True)`, nullable, stored UTC.
API accepts `YYYY-MM-DD` or a full ISO 8601 timestamp.
API returns the date as ISO 8601.

## Filters

- `due_before=<ISO date>` keeps tasks with a due date strictly before that date.
- `overdue=true` keeps `status=open` tasks whose due date is before today UTC.
- Null due dates never match those filters.

## Test isolation

`app.db.reset_engine("sqlite:///:memory:")` plus `StaticPool` so every
TestClient shares one in-memory database. Do not open a second engine
in tests.
