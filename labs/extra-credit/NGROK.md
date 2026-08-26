# Extra credit. ngrok for local webhook triggers

Not Saturday. Run the agents on your laptop. GitHub still sends real events.

## What ngrok does

ngrok gives you a public HTTPS URL that tunnels to a local server.
GitHub posts issue and pull request events to that URL. The local agent handles them immediately.

## Free tier (August 2026)

- Up to 3 online endpoints
- 1 GB data transfer per month
- 20,000 HTTP requests per month
- Interstitial page on free endpoints
- Good enough for class demos and light testing

Paid plans start at about $8 per month if you need a reserved domain.
Free URLs change every time you restart ngrok unless you pay for a domain.

## Setup

1. Install ngrok and authenticate. A free account is fine.
2. Set `GITHUB_WEBHOOK_SECRET` in `.env`.
3. Run the extra-credit server from the repo root:

```bash
export PYTHONPATH="$PWD"
export GITHUB_WEBHOOK_SECRET=pick-a-long-random-string
python solutions/extra_credit/webhook.py --port 8765
```

Port 8765 avoids the CRM on 8000.

4. In another terminal: `ngrok http 8765`
5. Copy the public HTTPS URL.
6. GitHub repo, Settings, Webhooks. Payload URL:

```
https://YOUR-SUBDOMAIN.ngrok-free.app/github-webhook
```

Content type: `application/json`. Secret: the same `GITHUB_WEBHOOK_SECRET`.
Events: Issues, Check suites, Pull requests.

7. The server must verify the GitHub signature, then call the same agent logic as the polling labs.

If GitHub deliveries show an HTML interstitial, the free warning page is in the way. Use a GitHub-Hookshot delivery (it usually skips the browser page) or a paid reserved domain.

Working receiver: `solutions/extra_credit/webhook.py`
Stub: `labs/extra-credit/scripts/webhook_server.py`
