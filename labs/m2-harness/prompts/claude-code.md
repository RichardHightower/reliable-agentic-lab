# Prompt for Claude Code

Paste this into Claude Code.

Fill `labs/m2-harness/harness.py`.

Implement:

- maker(mode): `none` does nothing. `reference` copies `solutions/m2-harness/fixtures/t001-pass/` onto `solutions/crm` only for the five allowed due-date files.
- checker: read grader output. No writes.
- decide: pass if green. retry if new failure and budget remains. escalate on repeat failure signature or spent budget.
- run_loop: for iteration in 1..budget, grade, check, decide, maybe make.

Use `solutions/m2-harness/loops/implementer/` as the answer key only if you stall.
Do not cut this module. It is the center of the workshop.

Write traces to `labs/m2-harness/traces/last-loop.json`.
