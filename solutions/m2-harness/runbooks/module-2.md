# Module 2 runbook. 25 minutes.

Harness Engineering. Do not cut this module.

Goal: wrap the Ticket Implementer so a ready ticket is scored, retried, or escalated.

## Minute 0 to 3. Clone.

```bash
git clone git@github.com:RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab
git checkout start-m2
python -m venv .venv
source .venv/bin/activate
pip install -r crm/requirements.txt
export PYTHONPATH="$PWD:$PWD/crm"
```

Fall behind? Stop typing. Watch Rick. Then:

```bash
git fetch origin
git checkout done-m2
```

## Minute 3 to 8. Fail on purpose.

```bash
python -m harness.loops.implementer --maker none --budget 1
```

You should see `passed: false` and a `retry` or `escalate` gate.
Open `harness/traces/last-loop.json`.
That file is the local Langfuse fallback. Same keys either way.

## Minute 8 to 12. Read the contract.

Open these only:

- `harness/tickets/T001-due-dates.ready.md`
- `harness/contracts/module2-harness.md`
- `harness/loops/implementer/gates.py`

Maker may edit `crm/`.
Checker may not write.
Hidden tests stay in `harness/graders/`. Do not edit them.

## Minute 12 to 22. Make it pass.

Use Claude Code or your own editor on the CRM.
Add optional `due_date`. Wire the form. Wire `due_before` and `overdue`.

Then:

```bash
python -m harness.loops.implementer --maker none --budget 1
```

Green means the harness scored your loop. Not that you built a new product.

Instructor path on `done-m2` only:

```bash
python -m harness.loops.implementer --maker reference --budget 3
```

That applies the known-good files, then grades again.

## Minute 22 to 25. Say the graph out loud.

Orchestrator holds the budget.
Maker edits.
Checker reads.
Rubric comes from the ready ticket.
Grader is pytest.
Gate is pass, retry, or escalate.

If you are still red, clone `done-m2` and continue to Module 3 with a working harness.
