# Extra credit instructions

Pass:

- `task copy-plugin` puts the Lab 1 enhancer into `s_ext_2_ngrok/`.
- `bin/webhook_trigger.py` verifies HMAC, replies 202, and spawns
  `task run -- --ticket Txxx`.
- `ngrok` exposes a public URL GitHub can POST to.
- Unsigned webhook posts return 401. Missing secret returns 503.
- A Droplet runs a receiver behind Nginx.
- GitHub mode comments or labels, never loops past `AGENT_MAX_ATTEMPTS`.
- `agent-in-progress` is removed even when the run fails.

Do not force-push student branches from Actions in this lab.
