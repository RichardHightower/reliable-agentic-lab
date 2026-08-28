# Spec. Extra credit 1. The webhook receiver

One FastAPI server GitHub can post to. Extra credit 2 (ngrok) and extra credit 5
(DigitalOcean Droplet) both need it.

This folder is the filled answer. The student stub is
`labs/extra-credit/ext_1_webhook/webhook_server.py`.

The receiver does **not** implement the enhancer. It calls
[`solutions/sol1_enhancer`](../../sol1_enhancer) as a subprocess:

```bash
cd solutions/sol1_enhancer
task run -- --ticket T001
```

That folder is standalone. No import of it. The trigger lives here. The exits
live there.

## Build it step by step

1. Serve two routes.

   `GET /health` returns the backend name and the sol1 path.
   `POST /github-webhook` takes the delivery.

2. Verify the signature before you read the body.

   Compute HMAC SHA-256 over the raw body with `GITHUB_WEBHOOK_SECRET` and
   compare it to `X-Hub-Signature-256` using `hmac.compare_digest`. Reject a
   mismatch with 401. Missing secret is 503. An unverified body is an
   attacker's body.

3. Route on the event type.

   `issues` opened, and a new `issue_comment` that is not this loop's own
   marker, go to the groomer: `task run` in `solutions/sol1_enhancer`.
   A `ready` label is the fulfiller (not wired in this drop).
   A failed `check_suite` is the fixer (not wired in this drop).

4. Take one lock per issue.

   Two deliveries for one issue must not run at once. `LOCK_DIR` holds a file
   per issue number.

5. Stop at `AGENT_MAX_ATTEMPTS`, and comment when you give up.
   Set `agent-in-progress` before the work. Clear it after, even on failure.

6. Write `work/last-webhook.json` on every delivery. A run nobody can read is a
   run that did not happen.

7. Map the GitHub issue to a ticket id.

   Title form `[T001] ...` is enough. Frontmatter `id: T001` in the body also
   works. No id: comment and stop. Do not invent a ticket.

## Verify

```bash
python -m uvicorn solutions.extra_credit.s_ext_1_webhook.webhook:app --port 8765
curl -s localhost:8765/health
task test
```

Dry-run the handoff without Claude:

```bash
python solutions/extra_credit/s_ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001 --print
```

## Where the exits live

In `solutions/sol1_enhancer`. This file decides who runs. That folder decides
when to stop.
