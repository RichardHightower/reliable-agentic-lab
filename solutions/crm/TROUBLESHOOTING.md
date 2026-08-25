# CRM troubleshooting

## Hidden tests fail with table does not exist

The test client booted a different engine than `reset_engine`.
Use `get_engine()` everywhere. Do not cache a module-level engine in routes.

## HTML overdue filter always passes

The assertion was too weak. It must show the overdue task title and hide
the not-yet-due title.

## Docker boots, browser is empty

Seed runs on container start. If the volume already has a DB from an older
image, wipe the volume or delete `data/crm.db`.

## `ModuleNotFoundError: app`

Set `PYTHONPATH` to `solutions/crm`. Uvicorn needs `--app-dir solutions/crm`
when you launch from the repo root.
