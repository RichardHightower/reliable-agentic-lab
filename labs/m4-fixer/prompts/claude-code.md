# Prompt for Claude Code

You do not need Claude Code. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/m4-fixer
claude -p "$(cat prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Interactive: run `claude` here and paste everything below the line.

---

Fill `loop.py` in this folder. Fill only that file.

A failing branch in, a green one out, or an honest explanation of why not.

## What to implement

- `summarize_failure(run_result)`
- `repair_until_green(contract, budget)`

## The roles

This loop has orchestrator owns the budget, a code implementer repairs inside its scope, and a judge reads the suite.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## When the loop stops

There are three exits and no fourth: pass, retry, escalate.

1. the suite is green
2. the same tests fail twice
3. the budget is spent, and it leaves a comment saying why

## Verify

```bash
# Module 2 left its work in the target repo. Put it away first.
git -C ../../work/northwind-field-crm stash --include-untracked

task loop:fixer -- --branch broken-pr --doer reference
```

## The gate

Nobody is watching this one. Its exits matter more than its successes, and the same gate that blocks your push blocks its push.

## Rules

- Fill only `loop.py`. Do not edit anything under `loops/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read loops/fixer.py. It is the answer, not a hint.

## Worth reading

- `loops/fixer.py`
- `loops/gates.py`
