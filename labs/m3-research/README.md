# Lab 3. Research Assistant over MCP

A question in, a cited brief out. Same graph, different object.

**25 minutes. Artifact: A working research assistant that cites what it retrieved.**

## Work from this folder

```bash
cd labs/m3-research
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
task loop:research -- --question "sqlalchemy nullable datetime column" --backend fixture
```

## When it stops

- the brief is grounded and clean
- the search budget is spent
- no source could be found, which escalates rather than shipping an uncited brief

## The gate

The boundary is the lesson. This loop can search and write into its own output folder. It cannot merge, deploy, or touch the repo.

## If you fall behind

Stop typing and watch. Then:

```bash
git checkout done-m3
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
