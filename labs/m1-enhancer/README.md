# Lab 1. Ticket Enhancer

A vague ticket in, a ready contract out.

**25 minutes. Artifact: A working autonomous loop, running on your machine.**

## Work from this folder

```bash
cd labs/m1-enhancer
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

## Verify

```bash
task loop:enhancer -- --ticket T001
```

## When it stops

- the ticket is ready
- the budget is spent
- two rounds in a row find exactly the same gaps, which means the human has not acted and another round will not help

## The gate

This lab writes no code, so the push gate does not fire. You meet it in Module 2.

## If you fall behind

Stop typing and watch. Then:

```bash
git checkout done-m1
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
