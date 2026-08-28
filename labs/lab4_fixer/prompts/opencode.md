# Prompt for OpenCode

You do not need OpenCode. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/lab4_fixer
opencode run "$(cat prompts/opencode.md)"
```

Interactive: run `opencode` here and paste everything below the line.

---

Fill `loop.py` in this folder. Fill only that file.

A failing branch in, a green one out, or an honest explanation of why not.

## What to implement

- `summarize_failure(run_result)`
- `repair_until_green(contract, budget)`

## The roles

In this loop, an orchestrator owns the budget, a code implementer repairs inside its scope, and a judge reads the suite.

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

- Fill only `loop.py`. Do not edit anything under `solutions/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, watch Rick. Fill the two functions in `loop.py`.

## Worth reading

- `contract.py`
