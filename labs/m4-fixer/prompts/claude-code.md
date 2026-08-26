# Prompt for Claude Code

Fill `labs/m4-fixer/loop.py`.

Seed a broken PR from `solutions/m1-implementer/starter_crm`.
Run the hidden due-date grader. It should fail.
If `--maker reference`, copy the known-good due-date files from `solutions/m2-harness/fixtures/t001-pass/`.
Re-run the grader. Repeat until green or budget is spent.
If you give up, leave a comment that a human can read.

Then optionally call `solutions/m4-production/run_unattended.py` as the deploy of the same stack.
Do not invent a second product.

Working example: `python -m solutions.loops fixer --maker reference`
