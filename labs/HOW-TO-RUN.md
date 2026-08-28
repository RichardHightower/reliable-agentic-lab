# How to run a lab

You need one coding agent. You choose which.

## The one rule that changed

**Work from the lab folder, not the repo root.**

```bash
cd labs/lab2_implementer
```

Each lab is its own project. Running there means that lab's `.claude/` applies:
its tool scope, and nothing from the other three.

## The four tools

| Tool | Headless | Interactive |
|---|---|---|
| Claude Code | `claude -p "$(cat prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"` | `claude` |
| Codex | `codex exec "$(cat prompts/codex.md)"` | `codex` |
| Grok Build | `grok -p "$(cat prompts/grok-build.md)" --no-auto-update` | `grok` |
| OpenCode | `opencode run "$(cat prompts/opencode.md)"` | `opencode` |

For interactive mode, start the tool in the lab folder and paste everything
below the line in the prompt file.

## No coding agent at all

You can still do labs 2 through 4 by filling the stub by hand. Watch Rick
if you stall. Labs 2 to 4 have no drop-in solution folder; Lab 1 still does.

Lab 1 is a Claude Code plugin. It needs an LLM:

```bash
cd solutions/sol1_enhancer
task create-test-tickets && task run --
```

## Four rules, whichever tool you picked

1. Fill only the stub named in your lab's README. Do not edit `solutions/`.
2. Never edit a test in the target repo to make something pass. The harness
   catches it, and catching it is the lesson.
3. Stop at the documented exit. Do not invent a fourth one.
4. When you stall, read the solution named in your prompt. It is the answer, not
   a hint, and reading it costs you nothing.

## The gate

In Module 2 your agent will try to push and be refused:

```
BLOCKED by pre-tool hook: git push
Last run: FAILED (3 tests).
  first failure: tests.test_due_date::test_model_has_optional_due_date
Run `task test` first.
```

That is working as designed. Run `task test`, make it green, push again.
