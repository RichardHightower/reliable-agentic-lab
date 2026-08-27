# Spec. Lab 2. Ticket Implementer and the harness, with Grok Build

A ready ticket in, a green rubric out. This is the centre of the workshop.

**Artifact: A reusable evaluation harness that plans, executes, verifies, and iterates. About 25 minutes.**

This folder holds the finished answer. `harness.py` here runs as it stands.
The stub you start from is `labs/lab2_implementer/harness.py`, and the prompt that
drives Grok Build is `labs/lab2_implementer/prompts/grok-build.md`.

## Build it step by step

1. Work from the lab folder, not from this one.

   ```bash
   cd labs/lab2_implementer
   ```

2. Drive Grok Build with the lab's prompt, or fill `harness.py` by hand.

   ```bash
   grok -p "$(cat prompts/grok-build.md)" --no-auto-update
   ```

   Interactive: run `grok` in the lab folder and paste everything below the
   line in the prompt file.

3. Fill `red_gate(before, after)`. The docstring in the stub says what it must decide.
4. Fill `score_attempt(...)`. The docstring in the stub says what it must decide.
5. Fill `run_loop(...)`. The docstring in the stub says what it must decide.
6. Stop at one of three exits. Do not add a fourth.

   - every rubric row passes
   - the same rows fail twice
   - the iteration or money budget is spent

7. Verify.

   ```bash
   task loop:implementer -- --ticket T001 --doer reference
   task loop:implementer -- --ticket T001 --doer none
   ```

8. Compare your answer against this folder.

   ```bash
   diff harness.py ../../solutions/sol2_implementer_grok_build/harness.py
   ```

## The roles

In this loop, an orchestrator writes nothing, a test implementer owns tests/ only, a code implementer owns app/ and is denied tests/, and a judge holds no write path at all.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## The gate

You will hit the push gate in this lab. Your agent will try to push and be refused until `task test` is green. Read the refusal. It is the lesson.

## The reference

loops/implementer.py, loops/rubric.py, and loops/gates.py

## Worth reading

- `loops/rubric.py`
- `loops/gates.py`
- `loops/roles.py`
- `loops/steps.py`

## Run the finished answer

```bash
cd solutions/sol2_implementer_grok_build
task test
```
