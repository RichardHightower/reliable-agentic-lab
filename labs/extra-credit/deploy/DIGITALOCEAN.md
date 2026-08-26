# Extra credit. DigitalOcean Droplet plus webhooks

Not Saturday. A cheap permanent public endpoint. Same FastAPI receiver as ngrok.

## Goal

A Droplet that:

- Exposes HTTPS `/github-webhook`
- Receives `issues`, `check_suite`, and `pull_request` events
- Routes to Ticket Groomer, Ticket Fulfiller, or PR Fixer
- Works with the Python loops, Claude Code headless, OpenCode, Codex, Grok Build, Agent SDK, or LangGraph

`AGENT_BACKEND=python` is the working default. Change it only after the Python path is green.

## 1. Create the Droplet

1. Sign up at DigitalOcean and create a Droplet.
2. Cheapest Basic plan is enough for demos (about $6 per month, 1 vCPU, 1 GB RAM).
3. Ubuntu 24.04 LTS.
4. Add your SSH key.
5. Create the Droplet and note the public IP.

## 2. Basic server setup

```bash
ssh root@YOUR_DROPLET_IP
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git
git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
python3 -m venv /opt/agent-env
source /opt/agent-env/bin/activate
pip install -r /opt/agents/requirements.txt
```

Optional SDKs:

```bash
pip install -r /opt/agents/requirements-agents.txt
```

## 3. Secrets

`/opt/agents/.env` (never commit this):

```
GITHUB_TOKEN=ghp_...
GITHUB_REPO=your-user/reliable-agentic-lab
GITHUB_WEBHOOK_SECRET=your_random_secret
AGENT_BACKEND=python
AGENT_MAX_ATTEMPTS=3
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
```

## 4. Run the server

```bash
cd /opt/agents
source /opt/agent-env/bin/activate
export PYTHONPATH=/opt/agents
set -a && source /opt/agents/.env && set +a
python -m uvicorn solutions.extra_credit.webhook:app --host 127.0.0.1 --port 8000
```

Copy `agent-webhook.service` into systemd so it survives reboot.

## 5. HTTPS with Nginx and Let's Encrypt

Point a domain at the Droplet. Copy `nginx.conf`. Then:

```bash
certbot --nginx -d your-domain.com
```

## 6. GitHub webhook

Repo, Settings, Webhooks:

- Payload URL: `https://your-domain.com/github-webhook`
- Content type: `application/json`
- Secret: same as `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Check suites, Pull requests

## 7. How the three approaches plug in

Set `AGENT_BACKEND` on the Droplet.

| Value | What the webhook runs |
|---|---|
| `python` | `solutions/extra_credit` loops. Working default. |
| `claude` | `claude -p` headless |
| `opencode` | `opencode run` |
| `codex` | `codex exec` |
| `grok` | `grok -p` |
| `agent-sdk` | lab stub script |
| `langgraph` | lab stub script |

Same entry point. Only the agent implementation changes.

## Safety

- Always verify the GitHub signature.
- File lock plus `agent-in-progress` so two runs cannot overlap.
- Same max-iteration budget as polling.
- Log `solutions/extra_credit/work/last-webhook.json`.
