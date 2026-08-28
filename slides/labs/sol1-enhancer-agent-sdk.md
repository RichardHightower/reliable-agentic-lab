---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_agent_sdk

Take-home. Python owns the loop. The model only drafts and grades.

Stop conditions cannot be talked past.

Needs `claude-agent-sdk` and an API key for a live poll. `task test` does not.


---

# What you will build

| File | Job |
|---|---|
| `enhancer.py` | one poll-and-act step in Python |
| `loop.py` | CLI `--once`, `--table-only` |
| `roles.py` | `ClaudeAgentOptions` plus `scope_hook` |
| `plugin/` | same agents as Saturday, loaded with `plugins=` |
| `check_fields.py` | ready is arithmetic |
| `check_stop.py` | done, cost, max turns |
| `tests/` | pytest, stubs the SDK |

The point is not that it runs. The point is that the rubric, the write scope, and the exits did not have to change.


---

# Why Python holds the loop

A skill is a model following steps. A model can skip a step.

Here the parent session may only use the `Agent` tool. Python writes the candidate from the doer's text. Python calls `check_fields.py`. Python calls `check_stop.py`.


---

# Learning objectives

- Configure `tools=[...]` so judge and doer hold no Write
- Implement `scope_hook` with the full deny envelope
- Validate `--table-only` prints judge writes = `no`
- Troubleshoot a hook that fails **open** because of a typo
- Name the marker gap vs Deep Agents
- Deploy `loop.py --once` on issue events


---

# Starting architecture

```
python loop.py --once --repo TARGET --ticket T900
  └── enhancer.py
         Agent tool
            ├── enhancer-judge  Read, Grep, Glob   output_format JSON
            └── enhancer-doer   Read, Grep, Glob   text draft
         Python writes tickets/<id>.enhancer-candidate.md
         check_fields.py / check_stop.py
         gh labels + .harness/last-enhancer-<id>.json
```


---

# Scope. Two places, both required

1. `tools=[...]`. `NO_WRITE` strips Edit, Write, Bash.
2. `PreToolUse` hook `roles.scope_hook`.

Empty `{}` = allow. Deny must be:

```python
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "...",
  }
}
```

A typo fails **open**. Tests assert this shape key by key.


---

# Parent session

```
allowed_tools=["Agent"]
disallowed_tools=NO_WRITE
CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1
maxTurns=12
background=False
```

System prompt: "Python already owns the loop. Do not invoke the enhancer-loop skill."

Judge uses structured `output_format` (`JUDGE_SCHEMA`). The hook still fires if a Write leaks.


---

# Cast. `roleplan.py`

```
enhancer: orchestrator, doer, judge
orchestrator  tools: Task                              writes: no
doer          tools: Read,Glob,Grep,Edit,Write,Bash    allow: tickets/**
judge         tools: Read,Glob,Grep,Bash               writes: no
```

Doer tools include Write in the table. Python still writes the candidate. The hook is the fail-closed belt.


---

# Extra exits. Marker gap

`check_stop.py` also fires on `usd >= max_usd` and `turns >= max_turns`.

Known gap vs the plugin and Deep Agents: `Gh.latest_comment` does not filter `<!-- enhancer-loop -->`, and `comment()` does not append it. Do not copy that gap into a new port.


---

# Commands

```bash
cd solutions/sol1_enhancer_agent_sdk
pip install -r ../../requirements-takehome.txt
cp config.json.example config.json
task table          # python loop.py --table-only
task test           # pytest, no key, no clone
task checks
task clone && task create-test-tickets
task run            # python loop.py --once --repo TARGET
```

Outcome line: `T900    waiting     round 1, still missing value, criteria`


---

# Expected `--table-only`

```
role           writes  scope
orchestrator   no      nothing
doer           yes     tickets/**
judge          no      nothing
```

If judge prints `yes`, stop. The port is wrong.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Judge writes `yes` | tools list leaked Write | strip with `NO_WRITE` |
| Writes to `app/` | deny envelope typo | tests assert `hookSpecificOutput` |
| Duplicate comments | marker gap | copy Deep Agents filter |
| SDK import error in pytest | imported at module top | lazy import, tests stub |


---

# Validation

- [ ] `task test` green without a key
- [ ] table: judge writes `no`
- [ ] deny shape matches tests key by key
- [ ] live poll grooms T900
- [ ] you know the marker gap exists


---

# GitHub Actions

`ENHANCER_BACKEND=agent-sdk`

```bash
python3 loop.py --once --repo "$GITHUB_WORKSPACE" --ticket "$TICKET"
```

Secret `ANTHROPIC_API_KEY`. Copy `labs/lab1_enhancer/workflows/enhance-on-issue.yml` onto your CRM fork.


---

# Recap

The harness is the product. The framework is not.

If a port imports a shared engine, the design leaked. This folder copies `roleplan.py` and `write_scope.py` on purpose.
