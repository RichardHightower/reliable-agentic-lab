# Extra credit. Pick a tool

Claude Code is not required. Headless:

```bash
claude -p "$(cat labs/extra-credit/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
opencode run --dir . "$(cat labs/extra-credit/prompts/claude-code.md)"
codex exec "$(cat labs/extra-credit/prompts/claude-code.md)"
grok -p "$(cat labs/extra-credit/prompts/claude-code.md)" --no-auto-update
```

This is extra credit. Not Saturday. Do one assignment at a time. Each has
its own prompt, one per solution folder.

| Assignment | Prompt | Answer |
|---|---|---|
| `ext_1_webhook` | [ext1-webhook.md](ext1-webhook.md) | `solutions/extra_credit/s_ext_1_webhook/` |
| `ext_2_ngrok` | [ext2-ngrok.md](ext2-ngrok.md) | `solutions/extra_credit/s_ext_2_ngrok/` |
| `ext_5_digitalocean` | [ext5-digitalocean.md](ext5-digitalocean.md) | `solutions/extra_credit/s_ext_5_digitalocean/` |

Paste the assignment prompt, not this file, into the tool.

Requirements that do not change:

- Trigger may be ngrok or a DigitalOcean Droplet. Not a polling loop.
- The receiver must verify `X-Hub-Signature-256`.
- Log JSON. Comment when you give up.
- Do not enable extra-credit workflows on the instructor repo.
- Do not edit the target repo's tests. Do not skip Module 2.
