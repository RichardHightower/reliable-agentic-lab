# Spec. Lab 4. Unattended PR fixer on Claude Agent SDK

A failing branch in, a green one out, or an honest explanation.

Use `query()`, not `ClaudeSDKClient`. Nobody is chatting. `permission_mode` is
`acceptEdits`. `max_turns` is the budget. Merge is never a tool.

## Cast

orchestrator, code_implementer, judge.

Write scope is a PreToolUse hook. The judge holds no Edit and no Write.
`tests/**` is denied. The fixer cannot weaken a test to reach green.

## What Python still owns

`summarize_failure` from junit. Three exits: suite green; same failing ids
twice; budget spent with a comment. Giving up silently is the bug.

## Run

```bash
cd solutions/sol4_fixer_agent_sdk
python3 -m pytest tests -q
python3 loop.py --table-only
# live, after stashing Module 2 work:
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer reference
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer sdk
```

`--doer sdk` needs `claude-agent-sdk`. The tests stub it.
