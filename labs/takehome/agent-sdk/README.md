# Take-home. The implementer in Claude Agent SDK

Rebuild the Module 2 loop in Claude Agent SDK. Same graph, same rubric, same gate.

**Optional. Nobody is expected to finish this inside the workshop.**

## Work from this folder

```bash
cd labs/takehome/agent-sdk
pip install -r ../../../requirements-takehome.txt
```

## Fill one file

`loop.py`. Two functions.

## Start

```bash
claude -p "$(cat prompts/claude-code.md)"
```

## Verify

```bash
task test     # no key needed
python loop.py --repo ../../../work/northwind-field-crm --dry-run
python loop.py --repo ../../../work/northwind-field-crm --ticket T001
```

`--dry-run` prints the role table and the configuration it built, and calls no
model. Read that before you spend anything.

## The answer

`solutions/sol2_implementer_agent_sdk/`.

## What you are actually building

Not a second product. One translation, of one table, into one runtime's idea of
tool scope. If your judge ends up holding a write tool, the translation is wrong,
and the test above says so.
