# Spec. Extra credit 5. Run the receiver on a Droplet

No Python. You put assignment 1 on a box with a permanent HTTPS address.

Answer: the procedure below, plus `deploy/nginx.conf` and
`deploy/agent-webhook.service` under
`labs/extra-credit/ext_5_digitalocean/deploy/`.

## Build it step by step

1. Create the smallest Ubuntu Droplet. Point a subdomain at its IP.

2. Clone the repo on the Droplet and run `task setup`.

3. Install the unit file. It runs uvicorn against
   `solutions.extra_credit.s_ext_1_webhook.webhook:app` on `127.0.0.1:8000`, so
   nothing but nginx can reach it.

   ```bash
   systemctl enable --now agent-webhook
   ```

4. Put nginx in front and terminate TLS with certbot. `deploy/nginx.conf` is the
   server block.

5. Point the fork's webhook at `https://<your-domain>/github-webhook`. Use the
   same secret you put in `GITHUB_WEBHOOK_SECRET`.

6. Open an issue and read the journal.

   ```bash
   journalctl -u agent-webhook -f
   ```

## Verify

A 200 in the GitHub webhook log, and a record in
`solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json` on the Droplet.

## Why bind to localhost

The agent holds a token. Nothing outside nginx should be able to reach it, and a
default bind of `0.0.0.0` puts it on the public internet.
