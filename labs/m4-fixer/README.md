# Lab 4. Broken PR Fixer, unattended

A failing branch in, a green one out, or an honest explanation of why not.

**18 minutes. Artifact: A production-ready architecture you can hand to your engineering org.**

## Work from this folder

```bash
cd labs/m4-fixer
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
task loop:fixer -- --doer reference
```

## When it stops

- the suite is green
- the same tests fail twice
- the budget is spent, and it leaves a comment saying why

## The gate

Nobody is watching this one. Its exits matter more than its successes, and the same gate that blocks your push blocks its push.

## If you fall behind

Stop typing and watch. Then:

```bash
git checkout done-m4
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
