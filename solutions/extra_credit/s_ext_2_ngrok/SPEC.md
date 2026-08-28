# Spec. Extra credit 2. ngrok adapter for the Lab 1 enhancer plugin

Not Saturday. Polling stays the class default.

Copy the Lab 1 ticket-enhancer plugin into this folder. Configure it. Then run
the small Python adapter in `bin/`. GitHub posts through ngrok. The adapter
replies in milliseconds and starts one `task run -- --ticket Txxx`. The plugin
still owns the exits.

Stub: `labs/extra-credit/ext_2_ngrok/README.md`.
Answer: this folder.

## What ngrok is

ngrok is a local agent that opens an outbound HTTPS tunnel to ngrok's cloud.
GitHub needs a public HTTPS URL. Your laptop only has `localhost`. ngrok
bridges the two. You do not open a firewall port.

GitHub waits about 10 seconds, then treats the delivery as failed. Claude
takes minutes. The adapter must verify the signature, reply `202`, and start
the plugin in the background. That is the whole adapter. It does not label
`ready`. It does not edit the ticket file.

## Copy the plugin here

Do this from this folder. Do not import `solutions/sol1_enhancer` at runtime.
This folder has to stay standalone after the copy.

```bash
cd solutions/extra_credit/s_ext_2_ngrok
task copy-plugin
# same thing: bin/copy_plugin.sh
```

That copies:

- `.claude/` (agents, `enhancer-loop` skill, `check_fields.py`, `check_stop.py`)
- `config.json.example`
- `bin/setup_test_tickets.sh`

It does not copy `SPEC.md`, `HOW_TO_RUN.md`, or Lab 1's `Taskfile.yml`. This
folder owns those. The copied `.claude/` is gitignored. Copy it on each
machine. Do not commit the plugin twice.

Then configure it:

```bash
cp config.json.example config.json
# set fork_owner to your GitHub username
task clone
task create-test-tickets   # optional T900 T901 T902
```

Prove one poll by hand before you add ngrok:

```bash
task run -- --ticket T001
```

That is the exact command the adapter will spawn.

## Install ngrok

Sign up at https://ngrok.com/signup. Copy the authtoken from
https://dashboard.ngrok.com/get-started/your-authtoken.

```bash
# macOS
brew install ngrok
ngrok config add-authtoken YOUR_TOKEN

# Linux: see https://ngrok.com/download, then
ngrok config add-authtoken YOUR_TOKEN
```

A free account is enough for this lab. Free URLs change every restart. Update
the GitHub webhook when that happens. Paid reserved domains keep the URL
stable.

## Start the adapter, then the tunnel

Three terminals. All commands run from this folder.

Terminal A, the adapter:

```bash
export GITHUB_WEBHOOK_SECRET='pick-a-long-random-string'
task listen
# same thing: python3 bin/webhook_trigger.py
```

It listens on `0.0.0.0:8765`. Override with `WEBHOOK_PORT`.

Terminal B, ngrok:

```bash
ngrok http 8765
```

Copy the HTTPS forwarding URL. It looks like `https://<random>.ngrok-free.app`.
The webhook URL is that host plus `/github-webhook`.

Terminal C, health:

```bash
curl -s http://127.0.0.1:8765/health
```

You want `"ok": true` and `"plugin_ready": true`.

Optional. Verify GitHub at the ngrok edge as well:

```bash
ngrok http 8765 --traffic-policy-file ngrok-github.yml
```

Still verify HMAC in Python. The edge check is extra, not a replacement.

## Register the webhook on the CRM fork

Put the webhook on your **northwind-field-crm fork**, not on this lab repo.
That is where the enhancer's issues live.

GitHub, the fork, **Settings**, **Webhooks**, **Add webhook**.

- Payload URL: `https://YOUR-SUBDOMAIN.ngrok-free.app/github-webhook`
- Content type: `application/json`
- Secret: the same `GITHUB_WEBHOOK_SECRET`
- SSL: enable
- Events: **Let me select individual events**
- Checked: **Issues**, **Issue comments**
- Unchecked: Pushes, Pull requests, Check suites
- Active: yes

Save. GitHub sends `ping`. The adapter returns `{"status":"pong"}`. The
deliveries tab should show `200`.

Do not subscribe to Pull requests or Check suites here. Those belong to the
fixer, not this enhancer.

## What the adapter does

`bin/webhook_trigger.py` is stdlib only. No FastAPI. No extra-credit groomer.

1. `GET /health` reports whether the copied plugin is present.
2. `POST /github-webhook` reads the raw body first.
3. HMAC SHA-256 over that raw body, compared to `X-Hub-Signature-256` with
   `hmac.compare_digest`. Missing secret is `503`. Bad signature is `401`.
4. `ping` is `pong`.
5. Issue titles must contain `[Txxx]`. That is how a GitHub issue maps onto
   `task run -- --ticket Txxx`.
6. `issues` opened, edited, or reopened starts one poll.
7. `issue_comment` created starts one poll, unless the body contains
   `<!-- enhancer-loop -->`. That marker is the plugin's own reply. Drop it
   or you pay for a Claude run the skill would no-op anyway.
8. Reply `202` before Claude starts.
9. One lock file per ticket under `work/locks/`.
10. One file per `X-GitHub-Delivery` under `work/deliveries/`, so retries do
    not double-start the same event.
11. Write `work/last-webhook.json` on every accepted run.

The trigger moved out of the loop. The exits did not. `enhancer-loop` still
stops on `LGTM` plus a green rubric, the same gaps twice, or a round budget
of 3 (`needs-human`).

## End-to-end walkthrough

1. `task copy-plugin`, then `config.json`, then `task clone`.
2. `task create-test-tickets` if you want `T900`.
3. Start `task listen` and `ngrok http 8765`. Register the webhook.
4. Open an issue on the fork titled `[T900] login button is grey`.
5. GitHub posts `issues` / `opened`. The adapter replies `202` and runs
   `task run -- --ticket T900`.
6. The skill finds or creates the issue, runs judge then doer, posts a
   comment that ends with `<!-- enhancer-loop -->`.
7. You reply with a real comment, or with `LGTM` after the rubric is green.
8. GitHub posts `issue_comment` / `created`. One more poll. `LGTM` plus a
   green rubric sets `state: ready`, `loop: implementer`, and the `ready`
   label.

Watch:

- GitHub, **Webhooks**, **Recent deliveries**. Look for `202`.
- ngrok inspector at http://127.0.0.1:4040. Replay a delivery from there.
- `work/last-webhook.json` in this folder.
- `work/enhancer-T900.log`.
- `work/northwind-field-crm/.harness/last-enhancer-T900.json` at the repo root.

Local HMAC smoke test, no GitHub:

```bash
BODY='{"action":"opened","issue":{"number":1,"title":"[T900] grey button"}}'
SIG="sha256=$(python3 - <<'PY'
import hashlib, hmac, os
body = b'{"action":"opened","issue":{"number":1,"title":"[T900] grey button"}}'
print(hmac.new(os.environ["GITHUB_WEBHOOK_SECRET"].encode(), body, hashlib.sha256).hexdigest())
PY
)"
curl -s -D- -X POST http://127.0.0.1:8765/github-webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: local-test-1" \
  -H "X-Hub-Signature-256: $SIG" \
  --data "$BODY"
```

Unsigned posts must return `401`.

## When a delivery arrives as HTML

The free ngrok interstitial is in the way. GitHub's User-Agent is not a
browser, so the POST usually reaches you. If the GitHub delivery body is
HTML, use a paid reserved domain. Confirm the request in the inspector.

## Verify

```bash
cd solutions/extra_credit/s_ext_2_ngrok
task copy-plugin
python -m pytest solutions/extra_credit/s_ext_2_ngrok/tests -q
```

From the repo root, `task test` includes these tests.

A live pass is a GitHub delivery with `202` and a matching
`work/last-webhook.json` whose `cmd` is `task run -- --ticket Txxx`.

## Failure table

| Symptom | Cause | Fix |
|---|---|---|
| GitHub delivery is HTML | free interstitial | paid domain, or confirm User-Agent is GitHub-Hookshot |
| Delivery `401` | secret mismatch | same string in GitHub UI and `GITHUB_WEBHOOK_SECRET` |
| Delivery `503` plugin not copied | `.claude/` missing | `task copy-plugin` |
| Delivery `503` secret | secret not in the listener env | export it in terminal A |
| Delivery `202`, no Claude | `task` not on PATH, or cwd wrong | check `work/enhancer-Txxx.log` |
| Second issue for same ticket | closed the issue instead of resetting | Lab 1 `HOW_TO_RUN.md` reset |
| Loop replies to itself forever | missing marker filter | adapter drops `<!-- enhancer-loop -->` |
| ngrok URL 404 after restart | free URL rotated | paste the new URL into the GitHub webhook |

## Where the exits live

In the copied `enhancer-loop` skill, not in this file. This file starts one
poll. The loop decides when to stop.

This is still a laptop demo. Close the lid and the tunnel dies. Production is
a GitHub Actions workflow on `issues` and `issue_comments` that runs the same
`task run -- --ticket …`. Same one-shot skill. Same state file in `.harness/`.
