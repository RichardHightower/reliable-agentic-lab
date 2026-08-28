# Lab walkthrough decks

Marp. Same Spillwave theme as the four session decks. These are guided
implementation walkthroughs, not summaries of the READMEs.

Saturday labs first. Then every `solutions/sol*_` variant.

```bash
npx @marp-team/marp-cli slides/labs/lab1-enhancer.md \
  --theme-set slides/themes/spillwave.css \
  --allow-local-files --pdf
```

| Deck | What it teaches | Folder |
|---|---|---|
| `lab1-enhancer.md` | Saturday Claude Code plugin | `labs/lab1_enhancer` |
| `sol1-enhancer-codex.md` | Process sandbox via `bin/role.sh` | `solutions/sol1_enhancer_codex` |
| `sol1-enhancer-opencode.md` | Permission deny on subagents | `solutions/sol1_enhancer_opencode` |
| `sol1-enhancer-grok-build.md` | Project plugin plus registration shims | `solutions/sol1_enhancer_grok_build` |
| `sol1-enhancer-agent-sdk.md` | Python loop, PreToolUse hook | `solutions/sol1_enhancer_agent_sdk` |
| `sol1-enhancer-deep-agents.md` | Deep Agents, scoped write tool | `solutions/sol1_enhancer_deep_agents` |
| `lab2-implementer.md` | Fill `harness.py` | `labs/lab2_implementer` |
| `sol2-implementer-deep-agents.md` | Working eight-step loop | `solutions/sol2_implementer_deep_agents` |
| `sol2-implementer-agent-sdk.md` | Role-table config port | `solutions/sol2_implementer_agent_sdk` |
| `lab3-research.md` | Fill `plan_questions` and `check_brief` | `labs/lab3_research` |
| `sol3-research-deep-agents.md` | Working research loop | `solutions/sol3_research_deep_agents` |
| `sol3-research-agent-sdk.md` | Role-table config port | `solutions/sol3_research_agent_sdk` |
| `lab4-fixer.md` | Fill `summarize_failure` and `repair_until_green` | `labs/lab4_fixer` |
| `sol4-fixer-agent-sdk.md` | Working unattended fixer | `solutions/sol4_fixer_agent_sdk` |
| `sol4-fixer-deep-agents.md` | Role-table config port | `solutions/sol4_fixer_deep_agents` |

Lab 1 deploy notes (GitHub Actions on ticket change events):
`labs/lab1_enhancer/GITHUB-ACTIONS.md`. Copy-me workflow:
`labs/lab1_enhancer/workflows/enhance-on-issue.yml`.

Do not project these during the four-hour clock unless a lab is running
long and the room needs the code on screen. Module 2 still does not get
cut.
