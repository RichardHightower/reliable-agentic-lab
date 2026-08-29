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

Lab 1 also ships take-home prompts for two other runtimes. They are not
Saturday. They rebuild the same loop as a Python harness:

| Runtime | Prompt | Answer |
|---|---|---|
| Claude Agent SDK | `prompts/agent-sdk.md` | `solutions/sol1_enhancer_agent_sdk/` |
| LangChain Deep Agents | `prompts/deep-agents.md` | `solutions/sol1_enhancer_deep_agents/` |

Labs 2 to 4 ship the same two filenames, pointed at that module's solution
folder. Saturday still fills the stub with one of the four tools above.

For interactive mode, start the tool in the lab folder and paste everything
below the line in the prompt file.

## No coding agent at all

You can still do labs 2 through 4 by filling the stub by hand. Watch Rick
if you stall. Labs 2 to 4 have no drop-in solution folder; Lab 1 still does.

Lab 1 is a plugin in `labs/lab1_enhancer`. It needs an LLM, but it does
not need Claude Code if you built with Grok, Codex, or OpenCode. Work from
the lab folder. `task run` looks at the skill tree you built and calls
that CLI:

```bash
cd labs/lab1_enhancer
task detect
task create-test-tickets && task run --
```

The Claude Code answer still lives at `solutions/sol1_enhancer/` if you
want to run that copy instead. That folder always calls `claude`. Do not
use it as the verification path for Grok, Codex, or OpenCode.

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
