# Spec. Lab 1. Ticket Enhancer, with Codex

A vague ticket in, a ready contract out.

**Artifact: A working autonomous loop, running on your machine. About 25 minutes.**

This folder holds the finished answer. `loop.py` here runs as it stands.
The stub you start from is `labs/lab1_enhancer/loop.py`, and the prompt that
drives Codex is `labs/lab1_enhancer/prompts/codex.md`.

## Build it step by step

1. Work from the lab folder, not from this one.

   ```bash
   cd labs/lab1_enhancer
   ```

2. Drive Codex with the lab's prompt, or fill `loop.py` by hand.

   ```bash
   codex exec "$(cat prompts/codex.md)"
   ```

   Interactive: run `codex` in the lab folder and paste everything below the
   line in the prompt file.

3. Fill `judge_ticket(ticket)`. The docstring in the stub says what it must decide.
4. Fill `decide_next(verdict, iteration, previous)`. The docstring in the stub says what it must decide.
5. Stop at one of three exits. Do not add a fourth.

   - the ticket is ready
   - the budget is spent
   - two rounds in a row find exactly the same gaps, which means the human has not acted and another round will not help

6. Verify.

   ```bash
   task loop:enhancer -- --ticket T001
   ```

7. Compare your answer against this folder.

   ```bash
   diff loop.py ../../solutions/sol1_enhancer_codex/loop.py
   ```

## The roles

In this loop, an orchestrator owns the budget and the exits, a doer edits the ticket body and nothing else, and a judge scores the ticket against criteria for its kind.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## The gate

This lab writes no code, so the push gate does not fire. You meet it in Module 2.

## The reference

loops/enhancer.py and loops/criteria.py

## Worth reading

- `loops/criteria.py`
- `loops/gates.py`
- `loops/ticket.py`

## Run the finished answer

```bash
cd solutions/sol1_enhancer_codex
task test
```
