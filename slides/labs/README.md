# Lab walkthrough decks

Marp. Same Spillwave theme as the four session decks. These are guided
implementation walkthroughs, not summaries of the READMEs.

Commands on these decks match folder-local `HOW_TO_RUN.md`, `SPEC.md`,
`DESIGN_DOC.md`, `TEST_PLAN.md`, `E2E_PLAN.md`, and `Taskfile.yml`.
Architecture diagrams live next to each solution at
`docs/diagrams/architecture.svg`. Walkthrough decks also use Spillwave Navy
Imagine rasters in `slides/labs/images/`, with prompt sidecars in
`slides/diagrams/imagen/`.

Saturday labs first. Then every `solutions/sol*_` variant. Then extra
credit and production triggers.

```bash
npx @marp-team/marp-cli slides/labs/lab1-enhancer.md \
  --theme-set slides/themes/spillwave.css \
  --allow-local-files --pdf
```

| Deck | What it teaches | Folder |
|---|---|---|
| `lab1-enhancer.md` | Saturday Claude Code plugin | `labs/lab1_enhancer` |
| `sol1-enhancer.md` | Finished Claude Code answer | `solutions/sol1_enhancer` |
| `sol1-enhancer-codex.md` | Process sandbox via `bin/role.sh` | `solutions/sol1_enhancer_codex` |
| `sol1-enhancer-opencode.md` | Permission deny on subagents | `solutions/sol1_enhancer_opencode` |
| `sol1-enhancer-grok-build.md` | Project plugin plus registration shims | `solutions/sol1_enhancer_grok_build` |
| `sol1-enhancer-agent-sdk.md` | Python loop, PreToolUse hook | `solutions/sol1_enhancer_agent_sdk` |
| `sol1-enhancer-deep-agents.md` | Deep Agents, scoped write tool | `solutions/sol1_enhancer_deep_agents` |
| `lab2-implementer.md` | Fill `harness.py` | `labs/lab2_implementer` |
| `sol2-implementer-deep-agents.md` | Working eight-step loop. Driver of T001. | `solutions/sol2_implementer_deep_agents` |
| `sol2-implementer-agent-sdk.md` | Role-table config port. Cast, not driver. | `solutions/sol2_implementer_agent_sdk` |
| `lab3-research.md` | Fill `plan_questions` and `check_brief` | `labs/lab3_research` |
| `sol3-research-deep-agents.md` | White paper pipeline, nine stages, three fences | `solutions/sol3_research_deep_agents` |
| `sol3-research-agent-sdk.md` | White paper pipeline, ten phases, one PreToolUse hook | `solutions/sol3_research_agent_sdk` |
| `lab4-fixer.md` | Fill `summarize_failure` and `repair_until_green` | `labs/lab4_fixer` |
| `sol4-fixer-agent-sdk.md` | Working unattended fixer. `dontAsk`. | `solutions/sol4_fixer_agent_sdk` |
| `sol4-fixer-deep-agents.md` | Role-table config port. Graph only. | `solutions/sol4_fixer_deep_agents` |
| `ext1-webhook.md` | FastAPI HMAC receiver, 202, subprocess | `labs/extra-credit/ext_1_webhook` |
| `ext2-ngrok.md` | ngrok adapter for the copied Lab 1 plugin | `labs/extra-credit/ext_2_ngrok` |
| `ext5-digitalocean.md` | Droplet, nginx, systemd, loopback uvicorn | `labs/extra-credit/ext_5_digitalocean` |
| `deploy-github-actions.md` | Actions on issue events, backend matrix | `labs/lab1_enhancer/workflows` |
| `deploy-aws-fargate.md` | ALB + SQS + Fargate worker (pattern, not a lab) | extra credit 1 mapped to AWS |

Lab 1 deploy notes (GitHub Actions on ticket change events):
`labs/lab1_enhancer/GITHUB-ACTIONS.md`. Copy-me workflow:
`labs/lab1_enhancer/workflows/enhance-on-issue.yml`.

`deploy-aws-fargate.md` is a production mapping of extra credit 1. The repo
does not ship Terraform. HMAC, 202, marker skip, and the three exits stay
exactly as `s_ext_1_webhook`.

The two Lab 3 solution decks cover the grown report generators, not the old
config-only ports. Saturday still fills two functions in `labs/lab3_research`.
`sol3_research_deep_agents` has no `HOW_TO_RUN.md`. Use `SPEC.md` and the
Taskfile (`task brief`, `task paper`, `task live`).

Driver vs cast: `sol2_implementer_deep_agents` and `sol4_fixer_agent_sdk` are
the live loops. `sol2_implementer_agent_sdk` and `sol4_fixer_deep_agents` are
configuration ports. Do not demo T001 or `broken-pr` from the cast folders.

Testing skills, after class:

- `.agents/skills/test-sol1-ticket-enhancer/`
- `.agents/skills/test-ticket-implementer/`
- `.agents/skills/e2e-test-research-report/`

Every solution walkthrough starts with that folder's `task setup` /
`task table` / `task test`. Do not `pip install` into Homebrew Python.

Do not project these during the four-hour clock unless a lab is running
long and the room needs the code on screen. Module 2 still does not get
cut.
