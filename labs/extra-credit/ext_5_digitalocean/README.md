# Extra credit. DigitalOcean Droplet plus webhooks

Not Saturday. A cheap permanent public endpoint.

The virtual private server is a DigitalOcean Droplet. Cheapest Basic plan.
Ubuntu 24.04 LTS. One virtual CPU. One gigabyte of RAM. About six dollars a month.

The receiver is `solutions/extra_credit/s_ext_1_webhook`. An `issues` opened
delivery shells out to [`solutions/sol1_enhancer`](../../../solutions/sol1_enhancer):

```bash
cd solutions/sol1_enhancer
task run -- --ticket T001
```

## One command on the box

```bash
ssh root@YOUR_DROPLET_IP
git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
bash /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/bootstrap.sh
```

Then edit `/opt/agents/.env` from `.env.example`. Point a subdomain at the
Droplet. Run `certbot --nginx -d your-domain`. Point the CRM fork's webhook at
`https://your-domain/github-webhook`.

## What bootstrap installs

| Piece | Path |
|---|---|
| `.env.example` | `labs/extra-credit/ext_5_digitalocean/.env.example` |
| systemd unit | `deploy/agent-webhook.service` |
| nginx | `deploy/nginx.conf` (loopback only to uvicorn) |
| sol1 config | `deploy/write-sol1-config.sh` writes `solutions/sol1_enhancer/config.json` |
| handoff | `deploy/call-sol1-enhancer.sh T001` |
| smoke | `deploy/smoke.sh` |

The unit binds `127.0.0.1:8000`. Nothing but nginx should reach the agent. The
agent holds a token.

## GitHub webhook

On the **CRM fork** (`GITHUB_REPO`), not the lab repo:

- Payload URL: `https://your-domain/github-webhook`
- Content type: `application/json`
- Secret: same as `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Issue comments, Check suites

Issue titles must include `[T001]` so the receiver can pick a ticket.

## Call sol1 without GitHub

```bash
sudo -u agent bash -lc 'source /opt/agents/.env && /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001 --print'
sudo -u agent bash -lc 'source /opt/agents/.env && /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001'
```

`AGENT_BACKEND=claude` is the default. That is the Claude Code plugin in
`solutions/sol1_enhancer`.
