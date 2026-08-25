# Module 2 setup

Same venv as the CRM.

```bash
pip install -r solutions/crm/requirements.txt
```

Run unit tests (no CRM boot):

```bash
PYTHONPATH=solutions/m2-harness pytest solutions/m2-harness/tests -q
```

Run the hidden grader against the known-good CRM:

```bash
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/m2-harness/graders -q
```
