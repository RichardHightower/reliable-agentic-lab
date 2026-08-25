# CRM instructions

## Boot it

```bash
cd solutions/crm
docker compose up --build
```

Open the home page. You should see customers and sales tasks.
New task form has a `due_date` field.
Task list can filter `due_before` and `overdue`.

## Prove the contract

From the repo root, with `.venv` on:

```bash
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/m2-harness/graders/test_due_date_contract.py -q
```

Seven tests. All pass on this package. They fail on `starter_crm`.

## Talking points

- This is not a ticketing app. TicketCloser runs *on* this CRM.
- Seed rows keep null due dates. That is part of the contract.
- Do not hardcode customer names in filters or tests.
- Field type, timezone, and filters were underspecified until the enhancer
  produced the ready ticket. This tree is the ready contract made real.

## Do not

- Do not rebuild the CRM during Module 1.
- Do not turn it into a SPA.
- Do not add auth.
