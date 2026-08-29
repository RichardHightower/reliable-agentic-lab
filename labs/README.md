# Labs

Four labs, one per module. You fill one function or two in each. Everything
around them is written.

| Lab | Module | You build | You fill | Artifact |
|---|---|---|---|---|
| `lab1_enhancer` | 1 | Ticket Enhancer | a Claude Code plugin (`.claude/agents`, `.claude/skills`) | A working autonomous loop |
| `lab2_implementer` | 2 | The harness | `harness.py` | A reusable evaluation harness |
| `lab3_research` | 3 | Research assistant | `loop.py` | A cited research brief |
| `lab4_fixer` | 4 | Broken PR Fixer | `loop.py` | A production architecture |

Module 2 is the centre. If time runs short anywhere, it is not there.

## Work from the lab folder

```bash
cd labs/lab2_implementer
```

Your agent runs here, not at the repo root. Each lab folder is its own Claude
Code project: it has a `.claude/` with the tool scope for that lab, and a
`Taskfile.yml` that reaches the root spine, so `task test` works.

## Pick one tool

Claude Code, Codex, Grok Build, or OpenCode. You choose, and the lab does not
care. Every lab ships the same four Saturday prompts in `prompts/`. Lab 1 also
ships take-home prompts for Claude Agent SDK and LangChain Deep Agents. Labs
2 to 4 ship those two as well, pointed at the standalone solution folders,
not at the Saturday stub.

See [HOW-TO-RUN.md](HOW-TO-RUN.md).

## One prompt per solution variant

Every folder under [`solutions/`](../solutions/) has one prompt in the matching
lab. That is the map. If you add a solution folder, add the prompt. If you add
a variant prompt, add the folder.

| Solution | Prompt |
|---|---|
| `sol1_enhancer` | [lab1_enhancer/prompts/claude-code.md](lab1_enhancer/prompts/claude-code.md) |
| `sol1_enhancer_agent_sdk` | [lab1_enhancer/prompts/agent-sdk.md](lab1_enhancer/prompts/agent-sdk.md) |
| `sol1_enhancer_codex` | [lab1_enhancer/prompts/codex.md](lab1_enhancer/prompts/codex.md) |
| `sol1_enhancer_deep_agents` | [lab1_enhancer/prompts/deep-agents.md](lab1_enhancer/prompts/deep-agents.md) |
| `sol1_enhancer_grok_build` | [lab1_enhancer/prompts/grok-build.md](lab1_enhancer/prompts/grok-build.md) |
| `sol1_enhancer_opencode` | [lab1_enhancer/prompts/opencode.md](lab1_enhancer/prompts/opencode.md) |
| `sol2_implementer_agent_sdk` | [lab2_implementer/prompts/agent-sdk.md](lab2_implementer/prompts/agent-sdk.md) |
| `sol2_implementer_deep_agents` | [lab2_implementer/prompts/deep-agents.md](lab2_implementer/prompts/deep-agents.md) |
| `sol3_research_agent_sdk` | [lab3_research/prompts/agent-sdk.md](lab3_research/prompts/agent-sdk.md) |
| `sol3_research_deep_agents` | [lab3_research/prompts/deep-agents.md](lab3_research/prompts/deep-agents.md) |
| `sol4_fixer_agent_sdk` | [lab4_fixer/prompts/agent-sdk.md](lab4_fixer/prompts/agent-sdk.md) |
| `sol4_fixer_deep_agents` | [lab4_fixer/prompts/deep-agents.md](lab4_fixer/prompts/deep-agents.md) |
| `extra_credit/s_ext_1_webhook` | [extra-credit/prompts/ext1-webhook.md](extra-credit/prompts/ext1-webhook.md) |
| `extra_credit/s_ext_2_ngrok` | [extra-credit/prompts/ext2-ngrok.md](extra-credit/prompts/ext2-ngrok.md) |
| `extra_credit/s_ext_5_digitalocean` | [extra-credit/prompts/ext5-digitalocean.md](extra-credit/prompts/ext5-digitalocean.md) |

Labs 2 to 4 also keep four Saturday prompts (`claude-code`, `codex`,
`grok-build`, `opencode`). Those fill `harness.py` or `loop.py`. There is no
`sol2_implementer` folder. The filled stub is the Saturday answer.

`scripts/tests/test_prompt_solution_map.py` fails if this table and the
`solutions/` tree drift.

## Take-home

`takehome/` holds a fill-`loop.py` stub of the Module 2 implementer in the
Claude Agent SDK and in LangChain Deep Agents, both with Langfuse. Nobody is
expected to finish these in five hours. Some will try.

Each lab also ships `prompts/agent-sdk.md` and `prompts/deep-agents.md` for
the full standalone port of that module. Those prompts point at
`solutions/sol*_agent_sdk/` and `solutions/sol*_deep_agents/`.

## If you fall behind

Stop typing and watch Rick. Save your attempt. Labs 2 to 4 have no drop-in
answer. Copy only Lab 1's `.claude/` tree. See each lab's `FALL-BEHIND.md`.
