# Prompt for OpenCode

You do not need OpenCode. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/lab3_research
opencode run "$(cat prompts/opencode.md)"
```

Interactive: run `opencode` here and paste everything below the line.

---

Fill `loop.py` in this folder. Fill only that file.

A question in, a cited brief out. Same graph, different object.

## What to implement

- `plan_questions(question)`
- `check_brief(body, sources)`

## The roles

In this loop, an orchestrator owns the budget, a researcher calls the tool boundary, a writer assembles the brief, and a judge checks grounding and style without a model.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## When the loop stops

There are three exits and no fourth: pass, retry, escalate.

1. the brief is grounded and clean
2. the search budget is spent
3. no source could be found, which escalates rather than shipping an uncited brief

## Verify

```bash
task test
```

## The gate

The boundary is the lesson. This loop can search and write into its own output folder. It cannot merge, deploy, or touch the repo.

## Rules

- Fill only `loop.py`. Do not edit anything under `solutions/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read `brief.py` in this folder, then watch Rick.

## Worth reading

- `brief.py`
- `MCP.md`
