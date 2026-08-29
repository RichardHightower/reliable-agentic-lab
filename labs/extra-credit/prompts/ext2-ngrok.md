# Prompt. Extra credit 2. ngrok adapter

Not Saturday. Do not skip Module 2.

Copy the Lab 1 ticket-enhancer plugin. Run a small adapter. Give GitHub a
public HTTPS URL with ngrok. The finished answer is
`solutions/extra_credit/s_ext_2_ngrok/`. Read its
[SPEC.md](../../../solutions/extra_credit/s_ext_2_ngrok/SPEC.md).

The adapter is not the loop. It verifies the webhook, replies 202, and
spawns `task run -- --ticket Txxx`. The copied enhancer-loop skill still
decides when to stop.

```bash
cd solutions/extra_credit/s_ext_2_ngrok
claude
```

---

## Prompt 0: the things that will waste your hour

1. GitHub waits about 10 seconds, then treats the delivery as failed. Claude
   takes minutes. Reply 202 before Claude starts.
2. Put the webhook on your CRM fork, not this lab repo. That is where the
   enhancer's issues live.
3. Do not import `solutions/sol1_enhancer` at runtime. `task copy-plugin`
   copies `.claude/` into this folder. The copy is gitignored. Copy it on
   each machine.
4. Skip comments that contain `<!-- enhancer-loop -->`. That marker is the
   plugin's own reply. Drop it or you pay for a Claude run the skill would
   no-op anyway.
5. Port 8765. The CRM uses 8000.

---

## Prompt 1: copy the plugin and prove one poll

```
cd solutions/extra_credit/s_ext_2_ngrok
task copy-plugin
cp config.json.example config.json   # set fork_owner
task clone
task run -- --ticket T001
```

That is the exact command the adapter will spawn.

---

## Prompt 2: the adapter

```
Write bin/webhook_trigger.py. Stdlib only. No FastAPI.

GET /health reports whether the copied plugin is present.
POST /github-webhook reads the raw body first.
HMAC SHA-256 over that raw body, compared to X-Hub-Signature-256 with
hmac.compare_digest. Missing secret is 503. Bad signature is 401.
ping is pong.
Issue titles must contain [Txxx].
issues opened, edited, or reopened starts one poll.
issue_comment created starts one poll, unless the body contains the
enhancer-loop marker.
Reply 202 before Claude starts.
One lock file per ticket under work/locks/.
One file per X-GitHub-Delivery under work/deliveries/, so retries do not
double-start the same event.
```

---

## Prompt 3: ngrok and the webhook

```
export GITHUB_WEBHOOK_SECRET=pick-a-long-random-string
task listen
```

In another terminal: `ngrok http 8765`.

Webhook on the CRM fork:

- Payload URL: `https://YOUR-SUBDOMAIN.ngrok-free.app/github-webhook`
- Content type: `application/json`
- Secret: the same `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Issue comments. Nothing else.

Open an issue titled `[T900] ...` and watch one `task run` start.

Free ngrok URLs change every restart. Update the webhook when that happens.

---

## Verify

```bash
curl -s http://127.0.0.1:8765/health
task test
```

Health wants `"ok": true` and `"plugin_ready": true`. GitHub ping wants 200.
The adapter tests need no ngrok and no Claude.

## Prompt 4: compare against the answer

```
Diff what I built against solutions/extra_credit/s_ext_2_ngrok/, behavior
first, wording second. I will decide what to change.
```
