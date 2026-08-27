# Spec. Extra credit 1. The webhook receiver

One FastAPI server GitHub can post to. Assignments 2 through 5 all need it.

Stub: `labs/extra-credit/ext_1_webhook/webhook_server.py`.
Answer: `webhook.py` in this folder.

## Build it step by step

1. Serve two routes.

   `GET /health` returns the backend name. `POST /github-webhook` takes the
   delivery.

2. Verify the signature before you read the body.

   Compute HMAC SHA-256 over the raw body with `GITHUB_WEBHOOK_SECRET` and
   compare it to `X-Hub-Signature-256` using `hmac.compare_digest`. Reject a
   mismatch with 401. An unverified body is an attacker's body.

3. Route on the event type.

   `issues` opened goes to the groomer. A `ready` label goes to the fulfiller. A
   failed `check_suite` goes to the fixer.

4. Take one lock per issue.

   Two deliveries for one issue must not run at once. `LOCK_DIR` holds a file
   per issue number.

5. Stop at `AGENT_MAX_ATTEMPTS`, and comment when you give up.

6. Write `work/last-webhook.json` on every delivery. A run nobody can read is a
   run that did not happen.

## Verify

```bash
python solutions/extra_credit/s_ext_1_webhook/webhook.py --port 8765
curl -s localhost:8765/health
task test
```

## Where the exits live

In `loops/`, not in this file. This file decides who runs. The loop decides when
to stop.
