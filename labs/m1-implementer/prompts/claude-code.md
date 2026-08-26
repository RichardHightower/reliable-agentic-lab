# Prompt for Claude Code

Claude Code is not required. See [labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Headless (no TUI):

```bash
claude -p "$(cat labs/m1-implementer/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Interactive: run `claude` at the repo root and paste everything below this line.

You are implementing Module 1 of Engineering Reliable Agentic AI Systems.

Fill `labs/m1-implementer/loop.py` function `apply_change`.
Read `solutions/tickets/T001-due-dates.ready.md`. That is the contract.
Copy files from `solutions/m2-harness/fixtures/t001-pass/` onto the work CRM if you need a known-good shape, or write the due date field yourself.

Rules:

- Do not edit `solutions/m2-harness/graders/`.
- Do not rebuild the CRM.
- Do not start Module 2 yet.
- Keep the loop tiny: copy starter, change code, run hidden pytest, write PR.md.
- Exit when pytest is green. If you cannot get green, stop and report failure.

When done, run:

python labs/m1-implementer/loop.py
