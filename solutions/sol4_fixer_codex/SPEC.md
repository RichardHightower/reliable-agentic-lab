# Spec. Lab 4. Broken PR Fixer, unattended, with Codex

A failing branch in, a green one out, or an honest explanation of why not.

**Artifact: A production-ready architecture you can hand to your engineering org. About 18 minutes.**

This folder holds the finished answer. `loop.py` here runs as it stands.
The stub you start from is `labs/lab4_fixer/loop.py`, and the prompt that
drives Codex is `labs/lab4_fixer/prompts/codex.md`.

## Build it step by step

1. Work from the lab folder, not from this one.

   ```bash
   cd labs/lab4_fixer
   ```

2. Drive Codex with the lab's prompt, or fill `loop.py` by hand.

   ```bash
   codex exec "$(cat prompts/codex.md)"
   ```

   Interactive: run `codex` in the lab folder and paste everything below the
   line in the prompt file.

3. Fill `summarize_failure(run_result)`. The docstring in the stub says what it must decide.
4. Fill `repair_until_green(contract, budget)`. The docstring in the stub says what it must decide.
5. Stop at one of three exits. Do not add a fourth.

   - the suite is green
   - the same tests fail twice
   - the budget is spent, and it leaves a comment saying why

6. Verify.

   ```bash
   # Module 2 left its work in the target repo. Put it away first.
   git -C ../../work/northwind-field-crm stash --include-untracked
   
   task loop:fixer -- --branch broken-pr --doer reference
   ```

7. Compare your answer against this folder.

   ```bash
   diff loop.py ../../solutions/sol4_fixer_codex/loop.py
   ```

## The roles

In this loop, an orchestrator owns the budget, a code implementer repairs inside its scope, and a judge reads the suite.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## The gate

Nobody is watching this one. Its exits matter more than its successes, and the same gate that blocks your push blocks its push.

## The reference

loops/fixer.py

## Worth reading

- `loops/fixer.py`
- `loops/gates.py`

## Run the finished answer

```bash
cd solutions/sol4_fixer_codex
task test
```
