# Extra credit prompt

Claude Code is not required. Headless:

```bash
claude -p "$(cat labs/extra-credit/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
opencode run --dir . "$(cat labs/extra-credit/prompts/claude-code.md)"
codex exec "$(cat labs/extra-credit/prompts/claude-code.md)"
grok -p "$(cat labs/extra-credit/prompts/claude-code.md)" --no-auto-update
```

This is extra credit. Not Saturday.

Fill `labs/extra-credit/scripts/groom_ticket.py` and `labs/extra-credit/scripts/fix_pr.py`.

Requirements:

- Trigger is GitHub Actions, not a polling loop.
- Reuse the same criteria, ready label, retry budget, and hidden grader as the PRD loops.
- Set and clear `agent-in-progress`. Increment `agent-attempts-N`. Stop at `AGENT_MAX_ATTEMPTS`.
- Log JSON. Comment when you give up.
- Copy YAML from `labs/extra-credit/workflows/` onto a fork. Do not enable it on the instructor repo.
- Do not edit graders. Do not skip Module 2.

Working example: `solutions/extra_credit/`.
