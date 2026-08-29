# Lab 2. Ticket Implementer and the harness

A ready ticket in, a green rubric out. This is the centre of the workshop.

**25 minutes. Artifact: A reusable evaluation harness that plans, executes, verifies, and iterates.**

## Work from this folder

```bash
cd labs/lab2_implementer
```

Your coding agent runs here, not at the repo root. This folder has its own
`.claude/`, so the tool scope and the skills for this lab apply and nothing
else does.

## Fill one file

`harness.py`. Nothing else.

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
| Claude Agent SDK | [prompts/agent-sdk.md](prompts/agent-sdk.md) | `solutions/sol2_implementer_agent_sdk/` |
| LangChain Deep Agents | [prompts/deep-agents.md](prompts/deep-agents.md) | `solutions/sol2_implementer_deep_agents/` |

Fill-one-file stubs: `labs/takehome/agent-sdk/` and `labs/takehome/deep-agents/`.

## Verify

Saturday self-check, from this folder:

```bash
task test
```

Instructor demo of the eight-step loop, from the Deep Agents port:

```bash
cd ../../solutions/sol2_implementer_deep_agents
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer none
```

## When it stops

- every rubric row passes
- the same rows fail twice
- the iteration or money budget is spent

## The gate

You will hit the push gate in this lab. Your agent will try to push and be refused until `task test` is green. Read the refusal. It is the lesson.

## If you fall behind

Stop typing and watch. Fill `harness.py` from what Rick types.
See `FALL-BEHIND.md`.
