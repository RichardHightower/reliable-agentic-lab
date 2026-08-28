# Prompt for Claude Code. Take-home: the implementer in Claude Agent SDK

Run it from this folder:

```bash
cd labs/takehome/agent-sdk
claude -p "$(cat prompts/claude-code.md)"
```

---

Fill `loop.py` in this folder. Fill only that file.

Rebuild the Module 2 implementer loop on top of Claude Agent SDK.

## What to implement

- `build(contract)`. Return the runtime configuration for the five roles, read
  from `solutions/roleplan.py`. Do not restate the scopes here. There is one
  table and it lives in `.loop.yml`.
- `run(contract, ticket_id, budget)`. Run the loop: plan, write tests, check the
  red gate, write code, score with the local `rubric`, then decide with
  the local `gates`.

## Rules

- The judge gets no tool that can write. Not a rule in its prompt. No tool.
- The code implementer must not be able to write `tests/**`.
- Python holds the loop. The model does not count its own retries.
- Wrap the run in this folder's own trace helper so there is a record either
  way.

## Exit when

1. The rubric is green and the final judge agrees.
2. The budget is spent.
3. The same rubric rows fail twice.

## Verify

```bash
task test
python loop.py --repo ../../../work/northwind-field-crm --dry-run
```

The first command needs no API key. Run it first.

## Reading

- `solutions/sol2_implementer_agent_sdk/`, the answer for this runtime
- `solutions/sol2_implementer_agent_sdk/`, the Saturday Module 2 loop on this runtime
- `import claude_agent_sdk` is how you know the install worked
