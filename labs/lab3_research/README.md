# Lab 3. Research Assistant over MCP

A question in, a cited brief out. Same graph, different object.

**25 minutes. Artifact: A working research assistant that cites what it retrieved.**

## Work from this folder

```bash
cd labs/lab3_research
```

Your coding agent runs here, not at the repo root. This folder has its own
`.claude/`, so the tool scope and the skills for this lab apply and nothing
else does.

## Fill one file

`loop.py`. Nothing else.

## Start

Pick one tool and paste its prompt.

| Tool | Command |
|---|---|
| Claude Code | `claude -p "$(cat prompts/claude-code.md)"` |
| Codex | `codex exec "$(cat prompts/codex.md)"` |
| Grok Build | `grok -p "$(cat prompts/grok-build.md)"` |
| OpenCode | `opencode run "$(cat prompts/opencode.md)"` |

## Take-home

Same loop, different runtime. Not Saturday. Do not copy those fences into
this folder.

| Runtime | Prompt | Answer |
|---|---|---|
| Claude Agent SDK | [prompts/agent-sdk.md](prompts/agent-sdk.md) | `solutions/sol3_research_agent_sdk/` |
| LangChain Deep Agents | [prompts/deep-agents.md](prompts/deep-agents.md) | `solutions/sol3_research_deep_agents/` |

## Verify

Saturday self-check, from this folder:

```bash
task test
```

Instructor demo of a cited brief, from the Deep Agents port:

```bash
cd ../../solutions/sol3_research_deep_agents
python3 loop.py --question "sqlalchemy nullable datetime column" --backend fixture
```

## When it stops

- the brief is grounded and clean
- the search budget is spent
- no source could be found, which escalates rather than shipping an uncited brief

## The gate

The boundary is the lesson. This loop can search and write into its own output folder. It cannot merge, deploy, or touch the repo.

## If you fall behind

Stop typing and watch. Fill `loop.py` from what Rick types.
See `FALL-BEHIND.md`.
