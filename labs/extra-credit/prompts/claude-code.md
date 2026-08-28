# Extra credit prompt

Claude Code is not required. Headless:

```bash
claude -p "$(cat labs/extra-credit/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
opencode run --dir . "$(cat labs/extra-credit/prompts/claude-code.md)"
codex exec "$(cat labs/extra-credit/prompts/claude-code.md)"
grok -p "$(cat labs/extra-credit/prompts/claude-code.md)" --no-auto-update
```

This is extra credit. Not Saturday.

Two assignments remain. Do one at a time.

| Assignment | You fill | Answer |
|---|---|---|
| `ext_2_ngrok` | nothing to code. Expose a local receiver and take a delivery. | its `README.md` |
| `ext_5_digitalocean` | nothing to code. Deploy a receiver behind nginx. | its `README.md` |

Requirements:

- Trigger may be ngrok or a DigitalOcean Droplet. Not a polling loop.
- The receiver must verify `X-Hub-Signature-256`.
- Log JSON. Comment when you give up.
- Do not enable extra-credit workflows on the instructor repo.
- Do not edit the target repo's tests. Do not skip Module 2.

Working example: `solutions/extra_credit/`.
