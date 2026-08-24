# reliable-agentic-lab

Private lab repo for **Engineering Reliable Agentic AI Systems**.

Workshop: Saturday 29 August 2026. Teach 10:00 to 15:00 Central.
Instructor: Rick Hightower.

Do not invent a new outline. This repo maps onto the locked four modules.

## What this is

TicketCloser on a sample customer relationship management (CRM) app.
Not a ticketing app.

Attendees clone the CRM. They do not build it.

Three loops sit on that app. Attendees do not build all three live.

1. Ticket Enhancer. Vague ticket to a testable contract.
2. Ticket Implementer. Ready ticket to a pull request.
3. Broken PR Fixer. Failing pull request to a mergeable pull request.

First graded ticket: add a due date on sales tasks.

## Layout

```
crm/                 sample app. Docker. SQLite. Customers and sales tasks.
harness/tickets/     markdown tickets with states
harness/loops/       implementer, enhancer, fixer
harness/graders/     hidden contract tests
harness/rubrics/
harness/contracts/   Module 2 paper contract
harness/runbooks/    25-minute paths, added per module
```

## Sunday proof (23 August)

Hidden due-date tests fail on `main`.
The same tests pass on `known-good`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r crm/requirements.txt
export PYTHONPATH="$PWD/crm"
pytest crm/tests -q
pytest harness/graders/test_due_date_contract.py -q   # expected fail on main
python harness/loops/implementer/run.py              # stub: one Claude call if keyed, then pytest
```

Boot the CRM:

```bash
cd crm
docker compose up --build
```

Or without Docker:

```bash
export PYTHONPATH="$PWD/crm"
python -m app.seed
uvicorn app.main:app --reload --app-dir crm
```

## Branches

See `docs/BRANCHES.md`.

Module start and done branches land through the week.
`main` today is the failing starter plus docs.
`known-good` is the instructor proof that the due-date contract is reachable.

## Fall-behind path

Stop typing. Watch Rick finish. Clone the done branch. Continue.
