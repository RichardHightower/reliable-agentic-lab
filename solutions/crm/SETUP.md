# CRM setup

From the repo root.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r solutions/crm/requirements.txt
export PYTHONPATH="$PWD/solutions/crm"
```

Python 3.11+. Dependencies are pinned in `requirements.txt`.

## Without Docker

```bash
export PYTHONPATH="$PWD/solutions/crm"
python -m app.seed
uvicorn app.main:app --reload --app-dir solutions/crm --host 0.0.0.0 --port 8000
```

## With Docker

```bash
cd solutions/crm
docker compose up --build
```

App listens on port 8000.

## Tests

```bash
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/crm/tests -q
pytest solutions/m2-harness/graders -q
```

The hidden due-date contract lives next to the harness on purpose.
Do not copy those tests into `solutions/crm/tests`.
