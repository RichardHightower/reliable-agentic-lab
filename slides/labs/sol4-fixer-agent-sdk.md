---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol4_fixer_agent_sdk

The working Module 4 loop. Issue 120.

`query()`, not `ClaudeSDKClient`. `permission_mode: acceptEdits`. Merge is never a tool.


---

# Layout

```
loop.py       summarize_failure + repair_until_green wrappers
fixer.py      the while loop
doers.py      none / reference / cli / SDK backend
gates.py      identical copy to sol3
contract.py   Taskfile + junit + coverage
roles.py      acceptEdits, PreToolUse deny tests/**
tests/        hook deny/allow, same-signature escalate, table-only
```

No `unattended.py`. Durable `.harness/state.json` and exit codes 0/2/1 lived there and were not copied. This CLI returns `0 if green else 1`. Escalate and crash are the same code. Name that drift. Do not hide it.


---

# Five unattended lines

```
permission_mode: acceptEdits     # nobody to click Allow
PreToolUse deny tests/**         # cannot weaken a test
max_turns=12                     # SDK inner budget; Python owns outer
tests after every turn = pytest  # not a claim
Merge is never a tool
```

Research port uses `dontAsk`. This one uses `acceptEdits` because nobody is in the chair.


---

# Commands

```bash
cd solutions/sol4_fixer_agent_sdk
python3 -m pytest tests -q
python3 loop.py --table-only
# after stash:
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer reference
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer sdk
```

`--doer sdk` needs `claude-agent-sdk`. Tests stub it.


---

# Recap

Same graph, nobody at the keyboard. Reference doer still bound by WriteScope. Human owns merge.

Pair with the Session 4 deck for state.json and cron. Rebuild `unattended.py` in this folder if you need exit 2 for escalate.
