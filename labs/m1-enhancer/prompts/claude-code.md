# Prompt for Claude Code

You do not need Claude Code. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/m1-enhancer
claude -p "$(cat prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Interactive: run `claude` here and paste everything below the line.

---

Fill `loop.py` in this folder. Fill only that file.

A vague ticket in, a ready contract out.

## What to implement

- `judge_ticket(ticket)`
- `decide_next(verdict, iteration, previous)`

## The roles

This loop has orchestrator owns the budget and the exits, a doer edits the ticket body and nothing else, and a judge scores the ticket against criteria for its kind.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## When the loop stops

There are three exits and no fourth: pass, retry, escalate.

1. the ticket is ready
2. the budget is spent
3. two rounds in a row find exactly the same gaps, which means the human has not acted and another round will not help

## Verify

```bash
task loop:enhancer -- --repo ../../work/northwind-field-crm --ticket T001
```

## The gate

This lab writes no code, so the push gate does not fire. You meet it in Module 2.

## Rules

- Fill only `loop.py`. Do not edit anything under `loops/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read loops/enhancer.py and loops/criteria.py. It is the answer, not a hint.

## Worth reading

- `loops/criteria.py`
- `loops/gates.py`
- `loops/ticket.py`
