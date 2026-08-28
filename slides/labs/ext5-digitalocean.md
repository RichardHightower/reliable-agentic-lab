---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# Extra credit 5. DigitalOcean Droplet

<!-- _class: lead -->

Not Saturday. A cheap permanent public endpoint.

Cheapest Basic plan. Ubuntu 24.04 LTS. One vCPU. 1 GB RAM. About six dollars a month.

No new Python. You put extra credit 1 on a box.


---

# What you will build

The receiver is `solutions/extra_credit/s_ext_1_webhook`. nginx is the only public door. systemd runs uvicorn on loopback.

| Piece | Path |
|---|---|
| `.env.example` | `labs/extra-credit/ext_5_digitalocean/.env.example` |
| systemd unit | `deploy/agent-webhook.service` |
| nginx | `deploy/nginx.conf` |
| sol1 config | `deploy/write-sol1-config.sh` |
| handoff | `deploy/call-sol1-enhancer.sh T001` |
| smoke | `deploy/smoke.sh` |


---

# Why bind to localhost

The agent holds a token. A default bind of `0.0.0.0` puts it on the public internet.

```
Internet ──TLS──► nginx :443 ──proxy──► 127.0.0.1:8000 uvicorn
```

`ProtectSystem=strict`. `NoNewPrivileges=yes`. User `agent`.


---

# Learning objectives

- Bootstrap Ubuntu 24.04 with one script
- Fill `/opt/agents/.env` from the example
- Terminate TLS with certbot
- Point the **CRM fork** webhook at `https://your-domain/github-webhook`
- Smoke-test HMAC locally before GitHub
- Swap `AGENT_BACKEND` without rewriting the unit


---

# Starting architecture

```
GitHub CRM fork
   POST https://agents.example.com/github-webhook
            │
            ▼
        nginx (TLS)
            │  proxy_read_timeout 120s
            ▼
     127.0.0.1:8000  s_ext_1_webhook
            │  subprocess
            ▼
     solutions/sol1_enhancer   (or grok / opencode / ...)
```


---

# One command on the box

```bash
ssh root@YOUR_DROPLET_IP
git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
bash /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/bootstrap.sh
```

Then edit `/opt/agents/.env`. Point DNS. `certbot --nginx -d your-domain`.


---

# What bootstrap installs

- python3, venv, nginx, certbot, git, jq, `task`
- system user `agent`
- clone or pull `/opt/agents`
- venv at `/opt/agent-env` with `requirements.txt`
- `.env` from the example if missing (`chmod 0600`)
- optional clone of the CRM fork into `work/northwind-field-crm`
- `write-sol1-config.sh` then `install.sh`


---

# `.env` that matters

```
GITHUB_TOKEN=
GITHUB_REPO=your-github-username/northwind-field-crm
GITHUB_WEBHOOK_SECRET=
AGENT_BACKEND=claude
AGENT_MAX_ATTEMPTS=3
AGENT_TIMEOUT=900
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8000
ANTHROPIC_API_KEY=
WEBHOOK_DOMAIN=agents.example.com
```

`GITHUB_REPO` is the CRM fork, **not** the lab repo.


---

# `AGENT_BACKEND` picks the folder

```
claude      -> solutions/sol1_enhancer
grok        -> solutions/sol1_enhancer_grok_build
opencode    -> solutions/sol1_enhancer_opencode
codex       -> solutions/sol1_enhancer_codex
agent-sdk   -> solutions/sol1_enhancer_agent_sdk
deep-agents -> solutions/sol1_enhancer_deep_agents
```

Grok is a good fit on a Droplet (you can `task trust` once). It is a poor fit on hosted Actions.


---

# systemd unit. Loopback only.

```
ExecStart=/opt/agent-env/bin/python -m uvicorn \
  solutions.extra_credit.s_ext_1_webhook.webhook:app \
  --host 127.0.0.1 --port 8000
User=agent
EnvironmentFile=/opt/agents/.env
ReadWritePaths=/opt/agents
```

Working directory `/opt/agents`. `PYTHONPATH=/opt/agents`.


---

# nginx. Two locations. Everything else 404.

```
location /health         { proxy_pass http://127.0.0.1:8000/health; }
location /github-webhook {
    proxy_pass http://127.0.0.1:8000/github-webhook;
    proxy_read_timeout 120s;
}
location / { return 404; }
```

`client_max_body_size 1m`. Replace `YOUR_DOMAIN` before certbot.


---

# GitHub webhook

On the CRM fork (`GITHUB_REPO`):

- Payload URL: `https://your-domain/github-webhook`
- Content type: `application/json`
- Secret: same as `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Issue comments, Check suites

Issue titles must include `[T001]`.


---

# Smoke without GitHub

```bash
source /opt/agents/.env
bash labs/extra-credit/ext_5_digitalocean/deploy/smoke.sh
sudo -u agent bash -lc 'source /opt/agents/.env && \
  /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001 --print'
```

`smoke.sh` GETs `/health`, then POSTs a signed `issues.opened` body at loopback.


---

# Expected live result

A 202 in the GitHub webhook log. A record in:

```
/opt/agents/solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json
```

A `task run` in `solutions/sol1_enhancer` for that ticket.

```bash
journalctl -u agent-webhook -f
```


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Droplet 502 | uvicorn down, or proxy_pass wrong | `systemctl status agent-webhook` |
| 401 | secret mismatch | same string in GitHub and `.env` |
| 503 | secret empty | fill `.env`, restart unit |
| Clone failed | `CRM_OWNER` still the placeholder | edit `.env`, run `write-sol1-config.sh` |
| Grok skill not found | untrusted git root | `task trust` as the `agent` user |


---

# Recap

Permanent HTTPS. Same receiver as extra credit 1. Same exits as Lab 1.

The lid can close. The box keeps listening.

Next scale step: Fargate plus a queue. Same HMAC. Same 202. Worker is a second service.
