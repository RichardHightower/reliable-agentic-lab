# Prompt for Grok Build

You do not need Grok Build. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/lab2_implementer
grok -p "$(cat prompts/grok-build.md)" --no-auto-update
```

Interactive: run `grok` here and paste everything below the line.

---

Fill `harness.py` in this folder. Fill only that file.

A ready ticket in, a green rubric out. This is the centre of the workshop.

## What to implement

- `red_gate(before, after)`
- `score_attempt(...)`
- `run_loop(...)`

## The roles

In this loop, an orchestrator writes nothing, a test implementer owns tests/ only, a code implementer owns app/ and is denied tests/, and a judge holds no write path at all.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## When the loop stops

There are three exits and no fourth: pass, retry, escalate.

1. every rubric row passes
2. the same rows fail twice
3. the iteration or money budget is spent

## Verify

```bash
task test
```

## The gate

You will hit the push gate in this lab. Your agent will try to push and be refused until `task test` is green. Read the refusal. It is the lesson.

## Rules

- Fill only `harness.py`. Do not edit anything under `solutions/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read `rubric.py` and `gates.py` in this folder, then watch Rick.

## Worth reading

- `rubric.py`
- `gates.py`
