# Extra credit prompt

Claude Code is not required. Headless:

```bash
claude -p "$(cat labs/extra-credit/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
opencode run --dir . "$(cat labs/extra-credit/prompts/claude-code.md)"
codex exec "$(cat labs/extra-credit/prompts/claude-code.md)"
grok -p "$(cat labs/extra-credit/prompts/claude-code.md)" --no-auto-update
```

This is extra credit. Not Saturday.

Fill `labs/extra-credit/scripts/groom_ticket.py`, `labs/extra-credit/scripts/fix_pr.py`, and `labs/extra-credit/scripts/webhook_server.py`.

Requirements:

- Trigger may be GitHub Actions, ngrok, or a DigitalOcean Droplet. Not a polling loop.
- One FastAPI `POST /github-webhook`. Verify `X-Hub-Signature-256`.
- Route `issues` opened to the groomer, `ready` labeled to the fulfiller, failed `check_suite` to the fixer.
- Set and clear `agent-in-progress`. Increment `agent-attempts-N`. Stop at `AGENT_MAX_ATTEMPTS`.
- Log JSON. Comment when you give up.
- Copy YAML from `labs/extra-credit/workflows/` onto a fork. Do not enable it on the instructor repo.
- Do not edit graders. Do not skip Module 2.

Working example: `solutions/extra_credit/`.
