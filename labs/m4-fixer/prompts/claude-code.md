# Prompt for Claude Code

Claude Code is not required. See [labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Headless (no TUI):

```bash
claude -p "$(cat labs/m4-fixer/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Interactive: run `claude` at the repo root and paste everything below this line.

Fill `labs/m4-fixer/loop.py`.

Seed a broken PR from `solutions/m1-implementer/starter_crm`.
Run the hidden due-date grader. It should fail.
If `--maker reference`, copy the known-good due-date files from `solutions/m2-harness/fixtures/t001-pass/`.
Re-run the grader. Repeat until green or budget is spent.
If you give up, leave a comment that a human can read.

Then optionally call `solutions/m4-production/run_unattended.py` as the deploy of the same stack.
Do not invent a second product.

Working example: `python -m solutions.loops fixer --maker reference`
