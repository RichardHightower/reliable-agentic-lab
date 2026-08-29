# Deploy Lab 1 on GitHub Actions (ticket change events)

Saturday still polls. `task poll-forever` is a seminar stand-in for a
scheduler. Close the laptop and polling stops.

Production is an event. GitHub already knows when a ticket changed.
A workflow on **your CRM fork** starts one poll, then exits. The loop
does not decide when to stop. The trigger does not grade the ticket.

This is the same enhancer you built. Only the trigger moves.

Copy these notes onto your fork. Do not enable this workflow on the
shared instructor repo. It comments on issues and can spend model tokens.

Working extra-credit cousins: `labs/extra-credit/ext_1_webhook` (FastAPI),
`ext_2_ngrok`, `ext_5_digitalocean`. Those receive a webhook. This path
lets GitHub Actions be the receiver.

## What listens

```yaml
on:
  issues:
    types: [opened, edited, labeled]
  issue_comment:
    types: [created]
```

That is "the ticket changed": a new issue, an edited body, a label, or a
human comment. `LGTM` arrives as `issue_comment`. The next poll can pass.

Skip any comment that contains `<!-- enhancer-loop -->`. That marker is
how the loop recognizes its own posts. Filtering by author is wrong: the
workflow runs as `github-actions[bot]`, and a human `LGTM` must still
count.

## Copy-me workflow

File in this folder: `workflows/enhance-on-issue.yml`.

On the CRM fork:

```bash
mkdir -p .github/workflows
cp path/to/reliable-agentic-lab/labs/lab1_enhancer/workflows/enhance-on-issue.yml \
  .github/workflows/enhance-on-issue.yml
```

Then vendor or check out the enhancer you actually run:

| Backend | Folder to run from | How the job starts it |
|---|---|---|
| Claude Code (Saturday) | `solutions/sol1_enhancer` | `task run -- --ticket "$TICKET"` |
| Codex | `solutions/sol1_enhancer_codex` | same, after `task` sees that Taskfile |
| OpenCode | `solutions/sol1_enhancer_opencode` | same |
| Grok Build | `solutions/sol1_enhancer_grok_build` | same, plus `task trust` is a local step that does not exist on Actions. Prefer Claude/SDK on GHA. |
| VS Code | `solutions/sol1_enhancer_vscode` | same, plus Copilot CLI. Needs a Copilot token. Prefer Claude/SDK on GHA. |
| Copilot CLI | `solutions/sol1_enhancer_copilot_cli` | same, plus Copilot CLI. Needs a Copilot token. Prefer Claude/SDK on GHA. |
| Antigravity | `solutions/sol1_enhancer_antigravity` | same, plus `agy`. Needs an authenticated CLI. Prefer Claude/SDK on GHA. |
| Agent SDK | `solutions/sol1_enhancer_agent_sdk` | `python3 loop.py --once --repo "$GITHUB_WORKSPACE" --ticket "$TICKET"` |
| Deep Agents | `solutions/sol1_enhancer_deep_agents` | `python3 loop.py --once --repo "$GITHUB_WORKSPACE" --ticket "$TICKET"` |

Set repository variable `ENHANCER_BACKEND` to one of:
`claude`, `codex`, `opencode`, `vscode`, `copilot-cli`, `antigravity`, `agent-sdk`, `deep-agents`.

Grok, VS Code, Copilot CLI, and Antigravity on hosted runners are a poor fit
(trust prompt, local plugin shims, Copilot token, authenticated `agy`). Use
Claude Code, Agent SDK, or Deep Agents in Actions. Keep Grok, VS Code, Copilot
CLI, and Antigravity for a laptop or a Droplet (`ext_5`).

## Ticket id from the issue title

Seed titles look like `[T900] Search crashes on an empty query`.
The workflow parses `\[(T[0-9]+)\]`. If the title has no id, it uses
`T{issue_number}`. That matches HOW_TO_RUN for issues opened in the UI.

## Guardrails (same as extra credit)

- `concurrency.group: enhancer-${{ github.event.issue.number }}` so two
  events on the same ticket do not chew it twice.
- Label `agent-in-progress` while the job runs. Remove it in `if: always()`.
- Stop at `AGENT_MAX_ATTEMPTS` (default 3). The loop already has a round
  budget. This is a second belt, at the trigger.
- Permissions: `issues: write`, `contents: read`. Grant `contents: write`
  only if a later job will push. The enhancer edits issue bodies and
  labels, not app code.
- Secrets: `ANTHROPIC_API_KEY` for Agent SDK and Deep Agents. Claude Code
  on Actions needs that key too if you call `claude -p`. `GITHUB_TOKEN` is
  provided. Fine-grained PAT if you must reach a private CRM from a
  different repo.
- Log the poll. Plugin ports already write
  `.harness/last-enhancer-<id>.json` in the target. Upload it as an
  artifact so you can read the last score at 2 a.m.

## What does not change

Three exits, no fourth: `LGTM` plus a green rubric, same gaps twice,
budget spent. Labels `enhanced`, `ready`, `needs-human`. Judge still has
no write tool. `check_fields.py` still computes ready.

A workflow that merges, deploys, or closes the issue has left the lab.

## Verify

1. Push the workflow to **your** fork.
2. Open or edit an issue titled `[T900] Search crashes on an empty query`.
3. The Actions tab shows `enhance`. The issue gets `enhanced` or a marked
   comment.
4. Comment `LGTM` as yourself. The next event should set `ready` only if
   `check_fields.py` already said the body is ready.
5. A second event with no new human comment must be a no-op on a green
   ticket. If it posts again, the marker filter is missing.

## If you stall

Stop and return to polling. `task run --` from `labs/lab1_enhancer` is
the Saturday path. Extra credit webhook is the other event-driven path
if Actions is the wrong tool for your laptop.
