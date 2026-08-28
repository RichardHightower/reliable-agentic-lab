# Extra credit. ngrok adapter for the Lab 1 enhancer plugin

Not Saturday. Run the Lab 1 ticket enhancer on your laptop. GitHub still sends
real events.

Answer: `solutions/extra_credit/s_ext_2_ngrok/`.

## What you build

1. Copy the Lab 1 plugin into the extra-credit 2 folder.
2. Configure `config.json` and clone your CRM fork.
3. Run the small Python adapter in `bin/webhook_trigger.py`.
4. Give GitHub a public URL for it with ngrok.
5. Open an issue titled `[T900] ...` and watch one `task run` start.

The adapter is not the loop. It verifies the webhook, replies `202`, and
spawns `task run -- --ticket Txxx`. The copied `enhancer-loop` skill still
decides when to stop.

## What ngrok does

ngrok gives you a public HTTPS URL that tunnels to a local server. GitHub
posts issue and comment events to that URL. You do not open a firewall port.

## Free tier (August 2026)

- Up to 3 online endpoints
- 1 GB data transfer per month
- 20,000 HTTP requests per month
- Interstitial page on free endpoints
- Good enough for class demos and light testing

Paid plans start at about $8 per month if you need a reserved domain.
Free URLs change every time you restart ngrok unless you pay for a domain.

## Setup

Follow `solutions/extra_credit/s_ext_2_ngrok/SPEC.md`. Short version:

```bash
cd solutions/extra_credit/s_ext_2_ngrok
task copy-plugin
cp config.json.example config.json   # set fork_owner
task clone
export GITHUB_WEBHOOK_SECRET=pick-a-long-random-string
task listen
```

In another terminal: `ngrok http 8765`.

Webhook on the CRM fork, not this lab repo. Payload URL:

```
https://YOUR-SUBDOMAIN.ngrok-free.app/github-webhook
```

Content type: `application/json`. Secret: the same `GITHUB_WEBHOOK_SECRET`.
Events: Issues, Issue comments. Nothing else.

Issue titles must contain `[Txxx]`. That is the ticket id the adapter passes
to the plugin.

If GitHub deliveries show an HTML interstitial, the free warning page is in
the way. GitHub-Hookshot usually skips the browser page. A paid reserved
domain always does.

Port 8765 avoids the CRM on 8000.
