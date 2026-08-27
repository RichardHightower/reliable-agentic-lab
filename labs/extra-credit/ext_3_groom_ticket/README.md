# Extra credit 3. Groom a ticket from GitHub Actions

The Module 1 enhancer, started by an issue event instead of by you.

## Fill

`groom_ticket.py` in this folder.

## What it must do

1. Read one issue by number through the GitHub API.
2. Judge it with `loops.criteria`. The judge does not change, only the trigger.
3. Label it `ready` when it passes. Comment the missing parts when it does not.
4. Count attempts with an `agent-attempts-N` label. Stop at the budget and say so
   in a comment.
5. Skip the run when `agent-in-progress` is already set.
6. Write `work/last-groom.json`.

## Copy the workflow onto your fork

```bash
cp labs/extra-credit/ext_3_groom_ticket/workflows/groom-ticket.yml \
   .github/workflows/groom-ticket.yml
```

Do not enable it on the instructor repo.

## Verify

```bash
python solutions/extra_credit/s_ext_3_groom_ticket/groom_ticket.py --issue T001 --incorporate
```

## Answer

`solutions/extra_credit/s_ext_3_groom_ticket/`.
