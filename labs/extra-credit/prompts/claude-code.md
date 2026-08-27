# Extra credit prompt

Claude Code is not required. Headless:

```bash
claude -p "$(cat labs/extra-credit/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
opencode run --dir . "$(cat labs/extra-credit/prompts/claude-code.md)"
codex exec "$(cat labs/extra-credit/prompts/claude-code.md)"
grok -p "$(cat labs/extra-credit/prompts/claude-code.md)" --no-auto-update
```

This is extra credit. Not Saturday.

Five assignments, one folder each. Do one at a time.

| Assignment | You fill | Answer |
|---|---|---|
| `ext_1_webhook` | `webhook_server.py` | `solutions/extra_credit/s_ext_1_webhook/` |
| `ext_2_ngrok` | nothing to code. Expose `ext_1` and take a delivery. | its `README.md` |
| `ext_3_groom_ticket` | `groom_ticket.py` | `solutions/extra_credit/s_ext_3_groom_ticket/` |
| `ext_4_fix_pr` | `fix_pr.py` | `solutions/extra_credit/s_ext_4_fix_pr/` |
| `ext_5_digitalocean` | nothing to code. Deploy `ext_1` behind nginx. | its `README.md` |

Requirements:

- Trigger may be GitHub Actions, ngrok, or a DigitalOcean Droplet. Not a polling loop.
- One FastAPI `POST /github-webhook`. Verify `X-Hub-Signature-256`.
- Route `issues` opened to the groomer, `ready` labeled to the fulfiller, failed `check_suite` to the fixer.
- Set and clear `agent-in-progress`. Increment `agent-attempts-N`. Stop at `AGENT_MAX_ATTEMPTS`.
- Log JSON. Comment when you give up.
- Copy each assignment's `workflows/*.yml` onto a fork. Do not enable it on the instructor repo.
- Do not edit the target repo's tests. Do not skip Module 2.

Working example: `solutions/extra_credit/`.
