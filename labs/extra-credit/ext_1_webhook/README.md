# Extra credit 1. The webhook receiver

One FastAPI server that GitHub can post to. Every later assignment needs it.

Filled answer: `solutions/extra_credit/s_ext_1_webhook/`.

That answer calls [`solutions/sol1_enhancer`](../../../solutions/sol1_enhancer)
as a subprocess. It does not import it.

```bash
python -m uvicorn solutions.extra_credit.s_ext_1_webhook.webhook:app --host 127.0.0.1 --port 8000
curl -s localhost:8000/health
```

`webhook_server.py` in this folder launches that module so extra credit 2 and 5
can keep pointing at this path.

## What it must do

1. Serve `POST /github-webhook` and `GET /health`.
2. Verify `X-Hub-Signature-256` against `GITHUB_WEBHOOK_SECRET`. Reject a bad
   signature with 401. Never trust an unverified body.
3. Route `issues` opened (and human comments) to
   `cd solutions/sol1_enhancer && task run -- --ticket T001`.
4. Set `agent-in-progress` before the work and clear it after.
5. Stop at `AGENT_MAX_ATTEMPTS`. Comment when you give up.
6. Write one JSON record per delivery to
   `solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json`.

Issue titles need `[T001]` so the receiver can pick a ticket.

Then extra credit 2 tunnels this port with ngrok.
Extra credit 5 runs the same module on a DigitalOcean Droplet.
