# Prompt. Extra credit 1. The webhook receiver

Not Saturday. Do not skip Module 2.

Build one FastAPI server GitHub can post to. The finished answer is
`solutions/extra_credit/s_ext_1_webhook/`. Read its
[SPEC.md](../../../solutions/extra_credit/s_ext_1_webhook/SPEC.md).

The student stub is `labs/extra-credit/ext_1_webhook/webhook_server.py`.

The receiver does not implement the enhancer. It calls
`solutions/sol1_enhancer` as a subprocess. No import of it. The trigger lives
here. The exits live there.

```bash
cd labs/extra-credit
claude
```

Any of the four Saturday tools works. Same prompt.

---

## Prompt 0: the things that will waste your hour

1. Verify the signature before you parse JSON. HMAC SHA-256 over the raw
   body, compared to `X-Hub-Signature-256` with `hmac.compare_digest`. An
   unverified body is an attacker's body. Missing secret is 503. Bad
   signature is 401.
2. GitHub waits about 10 seconds. Claude takes minutes. Reply first, then
   start the work. Extra credit 2 makes this a 202. Extra credit 1 can do
   the same.
3. Do not invent a ticket id. Title form `[T001] ...` or frontmatter `id:`.
   No id: comment and stop.
4. Do not enable extra-credit workflows on the instructor repo.

---

## Prompt 1: two routes

```
Create GET /health and POST /github-webhook.

Health returns the backend name and the sol1 path.
The POST takes the delivery.
```

---

## Prompt 2: the handoff

```
Route issues opened, and a new issue_comment that is not this loop's own
marker, to the groomer:

cd solutions/sol1_enhancer
task run -- --ticket T001

A ready label is the fulfiller. Not wired in this drop.
A failed check_suite is the fixer. Not wired in this drop.

Take one lock per issue. Two deliveries for one issue must not run at once.
Stop at AGENT_MAX_ATTEMPTS. Comment when you give up.
Set agent-in-progress before the work. Clear it after, even on failure.
Write work/last-webhook.json on every delivery.
```

---

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

Then extra credit 2 tunnels this port. Extra credit 5 puts it on a Droplet.

## Prompt 3: compare against the answer

```
Diff what I built against solutions/extra_credit/s_ext_1_webhook/, behavior
first, wording second. I will decide what to change.
```
