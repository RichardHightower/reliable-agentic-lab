# Prompt. Extra credit 5. DigitalOcean Droplet

Not Saturday. Do not skip Module 2.

No new Python. Put extra credit 1 on a box with a permanent HTTPS address.
The finished answer is `solutions/extra_credit/s_ext_5_digitalocean/`. Read
its [SPEC.md](../../../solutions/extra_credit/s_ext_5_digitalocean/SPEC.md).

The receiver is `solutions/extra_credit/s_ext_1_webhook`. It calls
`solutions/sol1_enhancer` with `task run -- --ticket T001`. It does not
import that folder.

Cheapest Basic Droplet. Ubuntu 24.04 LTS. One virtual CPU. One gigabyte of
RAM. About six dollars a month.

```bash
cd labs/extra-credit/ext_5_digitalocean
claude
```

---

## Prompt 0: the things that will waste your hour

1. Bind the agent to 127.0.0.1. The agent holds a token. A default bind of
   0.0.0.0 puts it on the public internet. nginx terminates TLS. Nothing
   but nginx should reach uvicorn.
2. `GITHUB_REPO` is the CRM fork, not the lab repo.
3. `AGENT_BACKEND=claude` selects `solutions/sol1_enhancer`.
4. The deploy scripts under `labs/extra-credit/ext_5_digitalocean/deploy/`
   and `solutions/extra_credit/s_ext_5_digitalocean/deploy/` must stay the
   same.

---

## Prompt 1: bootstrap the box

```
Create the smallest Ubuntu Droplet. Add your SSH key. Point a subdomain at
its IP.

ssh root@YOUR_DROPLET_IP
git clone https://github.com/YOUR-FORK/reliable-agentic-lab.git /opt/agents
bash /opt/agents/labs/extra-credit/ext_5_digitalocean/deploy/bootstrap.sh
```

Fill `/opt/agents/.env` from
`labs/extra-credit/ext_5_digitalocean/.env.example`.

---

## Prompt 2: TLS and the webhook

```
Confirm the unit is loopback only:

systemctl status agent-webhook
curl -sS http://127.0.0.1:8000/health

Terminate TLS:

certbot --nginx -d your-domain

Point the CRM fork webhook at https://<your-domain>/github-webhook.
Content type application/json. Same secret as GITHUB_WEBHOOK_SECRET.
Subscribe to Issues, Issue comments, and Check suites.
```

---

## Prompt 3: prove a delivery

```
Open an issue titled [T001] ...
journalctl -u agent-webhook -f
cat /opt/agents/solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json
```

A 202 in the GitHub webhook log, a record in last-webhook.json, and a
`task run` in `solutions/sol1_enhancer` for that ticket.

Call the solution by hand:

```bash
labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001 --print
labs/extra-credit/ext_5_digitalocean/deploy/call-sol1-enhancer.sh T001
```

---

## What this assignment does not change

The trigger moved out of the loop. The exits stay in `solutions/sol1_enhancer`.

## Prompt 4: compare against the answer

```
Diff the deploy scripts against solutions/extra_credit/s_ext_5_digitalocean/,
behavior first, wording second. I will decide what to change.
```
