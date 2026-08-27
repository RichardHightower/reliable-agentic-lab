# Extra credit 1. The webhook receiver

One FastAPI server that GitHub can post to. Every later assignment needs it.

## Fill

`webhook_server.py` in this folder.

## What it must do

1. Serve `POST /github-webhook` and `GET /health`.
2. Verify `X-Hub-Signature-256` against `GITHUB_WEBHOOK_SECRET`. Reject a bad
   signature with 401. Never trust an unverified body.
3. Route `issues` opened to the groomer, a `ready` label to the fulfiller, and a
   failed `check_suite` to the fixer.
4. Set `agent-in-progress` before the work and clear it after, so two deliveries
   for one issue do not run at once.
5. Stop at `AGENT_MAX_ATTEMPTS`. Comment when you give up.
6. Write one JSON record per delivery.

## Verify

```bash
python solutions/extra_credit/s_ext_1_webhook/webhook.py --port 8765
curl -s localhost:8765/health
```

## Answer

`solutions/extra_credit/s_ext_1_webhook/`. Read it when you stall. It is the
answer, not a hint.
