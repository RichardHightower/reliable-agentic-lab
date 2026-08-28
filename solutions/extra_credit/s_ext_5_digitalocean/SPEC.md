# Spec. Extra credit 5. Run the receiver on a DigitalOcean Droplet

No Python. You put assignment 1 on a box with a permanent HTTPS address.

The virtual private server (VPS) is a DigitalOcean Droplet.
Cheapest Basic plan. One virtual CPU. One gigabyte of RAM. About six dollars a month.
Ubuntu 24.04 LTS. SSH key on create. Note the public IP.

Answer: the procedure below, plus `deploy/nginx.conf` and
`deploy/agent-webhook.service` in this folder.
The lab copies live under `labs/extra-credit/ext_5_digitalocean/deploy/`.
Keep them the same.

This is takehome. It is not on the Saturday clock.

Finish extra credit 1 first. Fill
`labs/extra-credit/ext_1_webhook/webhook_server.py` so it serves
`GET /health` and `POST /github-webhook`.
The Droplet runs that file. It does not import
`solutions.extra_credit.s_ext_1_webhook`. That package is gone.
Groom, fulfill, and fix answers live in the Saturday lab folders.

## Build it step by step

1. Create the smallest Ubuntu Droplet. Point a subdomain at its IP.

2. Clone the fork onto the box and install.

   ```bash
   ssh root@YOUR_DROPLET_IP
   apt update && apt upgrade -y
   apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git
   git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
   python3 -m venv /opt/agent-env
   source /opt/agent-env/bin/activate
   pip install -r /opt/agents/requirements.txt
   ```

3. Write `/opt/agents/.env`. Never commit it.

   ```
   GITHUB_TOKEN=ghp_...
   GITHUB_REPO=your-user/reliable-agentic-lab
   GITHUB_WEBHOOK_SECRET=your_random_secret
   AGENT_BACKEND=python
   AGENT_MAX_ATTEMPTS=3
   ```

4. Install the unit file from `deploy/agent-webhook.service`.
   It runs the filled assignment 1 script on `127.0.0.1:8000`, so
   nothing but nginx can reach it.

   ```bash
   cp solutions/extra_credit/s_ext_5_digitalocean/deploy/agent-webhook.service /etc/systemd/system/agent-webhook.service
   systemctl daemon-reload
   systemctl enable --now agent-webhook
   ```

5. Put nginx in front and terminate Transport Layer Security (TLS) with certbot.
   `deploy/nginx.conf` is the server block.

   ```bash
   cp solutions/extra_credit/s_ext_5_digitalocean/deploy/nginx.conf /etc/nginx/sites-available/agent-webhook
   ln -s /etc/nginx/sites-available/agent-webhook /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   certbot --nginx -d your-domain.com
   ```

6. Point the fork's webhook at `https://<your-domain>/github-webhook`.
   Content type `application/json`.
   Use the same secret you put in `GITHUB_WEBHOOK_SECRET`.
   Subscribe to Issues, Pull requests, and Check suites.

7. Open an issue and read the journal.

   ```bash
   journalctl -u agent-webhook -f
   ```

## Verify

A 200 in the GitHub webhook log, and a record in
`labs/extra-credit/ext_1_webhook/work/last-webhook.json` on the Droplet.

## Why bind to localhost

The agent holds a token. Nothing outside nginx should be able to reach it, and a
default bind of `0.0.0.0` puts it on the public internet.

## What this assignment does not change

The trigger moved out of the loop. The exits stay in it.
`AGENT_BACKEND=python` is the working default.
Change the backend only after the Python path is green.
