# Lab 2. Ticket Implementer and the harness

A ready ticket in, a green rubric out. This is the centre of the workshop.

**25 minutes. Artifact: A reusable evaluation harness that plans, executes, verifies, and iterates.**

## Work from this folder

```bash
cd labs/m2-implementer
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

## Verify

```bash
task loop:implementer -- --repo ../../work/northwind-field-crm --ticket T001 --doer reference
task loop:implementer -- --repo ../../work/northwind-field-crm --ticket T001 --doer none
```

## When it stops

- every rubric row passes
- the same rows fail twice
- the iteration or money budget is spent

## The gate

You will hit the push gate in this lab. Your agent will try to push and be refused until `task test` is green. Read the refusal. It is the lesson.

## If you fall behind

Stop typing and watch. Then:

```bash
git checkout done-m2
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
