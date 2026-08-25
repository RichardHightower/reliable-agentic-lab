# Module 1 troubleshooting

## Grader still fails after the loop

You ran it against `solutions/crm` by accident, or fixtures did not copy.
Check `work/crm/app/models.py` for `due_date`.

## Starter already has due dates

Then you copied the known-good tree into `starter_crm`.
Restore `starter_crm` from git. The whole point is fail then pass.

## Want a live model

Set `ANTHROPIC_API_KEY` and use Claude Code on the starter copy.
Keep the same ticket and the same grader. Do not invent new success criteria.
