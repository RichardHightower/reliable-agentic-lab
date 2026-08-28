# Spec. Extra credit 5. Run the receiver on a DigitalOcean Droplet

No new Python. You put extra credit 1 on a box with a permanent HTTPS address.

The virtual private server is a DigitalOcean Droplet. Cheapest Basic plan.
One virtual CPU. One gigabyte of RAM. About six dollars a month. Ubuntu 24.04 LTS.

Answer: the scripts in `deploy/`, plus the same copies under
`labs/extra-credit/ext_5_digitalocean/deploy/`. Keep them the same.

The receiver is `solutions/extra_credit/s_ext_1_webhook`. It calls
`solutions/sol1_enhancer` with `task run -- --ticket T001`. It does not import
that folder.

This is takehome. It is not on the Saturday clock.

## Build it step by step

1. Create the smallest Ubuntu Droplet. Add your SSH key. Point a subdomain at
   its IP.

2. Clone the fork and run bootstrap.

   ```bash
   ssh root@YOUR_DROPLET_IP
   git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
   bash /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/bootstrap.sh
   ```

3. Fill `/opt/agents/.env` from
   `labs/extra-credit/ext_5_digitalocean/.env.example`.
   `GITHUB_REPO` is the CRM fork, not the lab repo.
   `AGENT_BACKEND=claude` selects `solutions/sol1_enhancer`.

4. Confirm the unit is loopback only.

   ```bash
   systemctl status agent-webhook
   curl -sS http://127.0.0.1:8000/health
   ```

5. Terminate TLS.

   ```bash
   certbot --nginx -d your-domain
   ```

6. Point the CRM fork webhook at `https://<your-domain>/github-webhook`.
   Content type `application/json`. Same secret as `GITHUB_WEBHOOK_SECRET`.
   Subscribe to Issues, Issue comments, and Check suites.

7. Open an issue titled `[T001] ...` and read the journal.

   ```bash
   journalctl -u agent-webhook -f
   cat /opt/agents/solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json
   ```

## Verify

A 202 in the GitHub webhook log, a record in `last-webhook.json`, and a
`task run` in `solutions/sol1_enhancer` for that ticket.

Call the solution by hand:

```bash
labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001 --print
labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001
```

## Why bind to localhost

The agent holds a token. Nothing outside nginx should be able to reach it, and a
default bind of `0.0.0.0` puts it on the public internet.

## What this assignment does not change

The trigger moved out of the loop. The exits stay in `solutions/sol1_enhancer`.
