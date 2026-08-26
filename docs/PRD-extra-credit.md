# Extra Credit: Event-driven agents via GitHub Actions

Not on the Saturday clock. Polling stays the class default.
Webhooks and Actions are this optional path.

Students who choose extra credit still implement the same core logic:
criteria checks, plan then implement then test, retry budget.
The only difference is the trigger. GitHub Actions instead of a polling loop.

Copy the YAML onto **your fork**. Do not enable these workflows on the shared instructor repo.
They can spend model tokens and comment on every issue.

Working examples: `solutions/extra_credit/`
Stubs and copy-me workflows: `labs/extra-credit/`

## 1. Ticket groomer on new issue

Trigger: `issues` event, types `opened` or `labeled`.

Copy `labs/extra-credit/workflows/groom-ticket.yml` to `.github/workflows/groom-ticket.yml` on the fork.

The job checks out the repo, sets up Python 3.11, installs dependencies, then runs:

```bash
python labs/extra-credit/scripts/groom_ticket.py --issue "$ISSUE_NUMBER"
```

Working command (no GitHub event required):

```bash
python solutions/extra_credit/groom_ticket.py --issue T001
```

The script evaluates the ticket against bug, feature, or user-interface criteria.
It either adds the `ready` label or posts a comment with suggested edits.

## 2. PR fixer on failed checks

Trigger: `check_suite` completed with failure.

Copy `labs/extra-credit/workflows/fix-broken-pr.yml` to `.github/workflows/fix-broken-pr.yml` on the fork.

```bash
python labs/extra-credit/scripts/fix_pr.py --pr "$PR_NUMBER"
```

Working command:

```bash
python solutions/extra_credit/fix_pr.py --pr T001 --maker reference
```

The script reads the failing check, proposes a fix, re-runs tests, and either comments a plan or, with `--apply`, restores the known-good due-date files.
It respects the retry budget. After the budget it leaves a comment and stops.

## 3. Safety guardrails

- Always set a max-attempts counter (label `agent-attempts-N` plus env `AGENT_MAX_ATTEMPTS`). The action cannot loop forever.
- Store API keys in repository secrets. Never hard-code them.
- Prefer fine-grained tokens with the minimum required scopes.
- Add `agent-in-progress` so two runs cannot chew the same ticket or PR at once.
- Log every decision to `last-groom.json` or `last-fix.json` so students can inspect the agent.

Required Actions secrets on the fork:

- `ANTHROPIC_API_KEY` only if the student calls a live model. The reference scripts do not need it.
- `GITHUB_TOKEN` is provided by Actions. Grant `issues: write`, `pull-requests: write`, `checks: read`, `contents: read` (write only if `--apply` will push).

## 4. Lab notes

This is excellent practice for production event-driven agent design.
It is still extra credit. Module 2 stays the center of Saturday.
If you stall on extra credit, stop and return to the polling labs.

## 5. Extra credit. ngrok for local webhook triggers

This path lets students run the agents on their own laptop while still getting real GitHub webhooks.

ngrok creates a public HTTPS URL that tunnels to a local server. GitHub sends issue and PR events to that URL. The local agent handles them immediately.

Free tier as of August 2026: up to 3 online endpoints, 1 GB transfer per month, 20,000 HTTP requests per month, interstitial page on free endpoints. Good enough for class demos. Paid plans start around $8 per month for a reserved domain. Free URLs change on every restart.

How it fits the three agents:

1. Ticket Groomer: webhook on `issues` opened or labeled → ngrok URL → local FastAPI `/github-webhook` → grooming logic → `ready` label or suggested edits.
2. Ticket Fulfiller: webhook on issues labeled `ready` → same endpoint → implementation plan, tests, PR.
3. PR Fixer: webhook on `check_suite` failure or `pull_request` synchronize → same endpoint → fix within budget, comment if it stops.

Minimal setup:

1. Install ngrok and authenticate. A free account is fine.
2. Run `python solutions/extra_credit/webhook.py --port 8765`
3. `ngrok http 8765`
4. Copy the public HTTPS URL.
5. GitHub, Settings, Webhooks. Payload URL `https://…/github-webhook`. Events: issues, check_suite, pull_request.
6. Verify the GitHub webhook secret, then call the same agent logic as polling.

Student notes: [labs/extra-credit/NGROK.md](../labs/extra-credit/NGROK.md)

## 6. Extra credit. DigitalOcean VPS plus webhooks

A permanent public endpoint on a cheap Droplet. Same FastAPI receiver as ngrok.

Goal: Ubuntu 24.04 Droplet, about $6 per month, Nginx plus Let's Encrypt, systemd, GitHub events routed to Groomer, Fulfiller, or Fixer.

`AGENT_BACKEND` selects the implementation behind the same entry point:

- `python` working extra-credit loops
- `claude` headless `claude -p`
- `opencode` / `codex` / `grok`
- `agent-sdk` / `langgraph` lab stubs

Student notes: [labs/extra-credit/deploy/DIGITALOCEAN.md](../labs/extra-credit/deploy/DIGITALOCEAN.md)
Nginx sample: [labs/extra-credit/deploy/nginx.conf](../labs/extra-credit/deploy/nginx.conf)
systemd sample: [labs/extra-credit/deploy/agent-webhook.service](../labs/extra-credit/deploy/agent-webhook.service)

Do not run this on the shared instructor Droplet during class unless Rick says so. Students use their own account.

## 7. Shared webhook safety

These rules apply to Actions, ngrok, and the Droplet:

- Always verify `X-Hub-Signature-256`.
- Use `agent-in-progress` or a lock file so the same ticket is not processed twice.
- Enforce the same max-iteration budget as polling.
- Log every decision (`last-groom.json`, `last-fix.json`, `last-webhook.json`).
- Store secrets in `.env` or systemd `EnvironmentFile`. Never commit them.

This is still extra credit. Students implement the core loop once. Only the trigger changes: poll, Actions, ngrok, or a VPS.

