# Spec. Lab 3. Research Assistant over MCP, with Claude Code

A question in, a cited brief out. Same graph, different object.

**Artifact: A working research assistant that cites what it retrieved. About 25 minutes.**

This folder holds the finished answer. `loop.py` here runs as it stands.
The stub you start from is `labs/lab3_research/loop.py`, and the prompt that
drives Claude Code is `labs/lab3_research/prompts/claude-code.md`.

## Build it step by step

1. Work from the lab folder, not from this one.

   ```bash
   cd labs/lab3_research
   ```

2. Drive Claude Code with the lab's prompt, or fill `loop.py` by hand.

   ```bash
   claude -p "$(cat prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
   ```

   Interactive: run `claude` in the lab folder and paste everything below the
   line in the prompt file.

3. Fill `plan_questions(question)`. The docstring in the stub says what it must decide.
4. Fill `check_brief(body, sources)`. The docstring in the stub says what it must decide.
5. Stop at one of three exits. Do not add a fourth.

   - the brief is grounded and clean
   - the search budget is spent
   - no source could be found, which escalates rather than shipping an uncited brief

6. Verify.

   ```bash
   task loop:research -- --question "sqlalchemy nullable datetime column" --backend fixture
   ```

7. Compare your answer against this folder.

   ```bash
   diff loop.py ../../solutions/sol3_research/loop.py
   ```

## The roles

In this loop, an orchestrator owns the budget, a researcher calls the tool boundary, a writer assembles the brief, and a judge checks grounding and style without a model.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## The gate

The boundary is the lesson. This loop can search and write into its own output folder. It cannot merge, deploy, or touch the repo.

## The reference

loops/researcher.py, loops/research.py, and loops/brief.py

## Worth reading

- `loops/brief.py`
- `loops/research.py`
- `MCP.md`

## Run the finished answer

```bash
cd solutions/sol3_research
task test
```
