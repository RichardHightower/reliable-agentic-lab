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

# What changes

| Knob | Saturday plugin | Agent SDK |
|---|---|---|
| Orchestrator | skill the model follows | `enhancer.py` in Python |
| Isolation | YAML tools omit Write | `tools=[...]` plus PreToolUse hook |
| Candidate file | orchestrator writes from doer text | Python writes from `turns.draft` |
| Cost / turns | none | `max_usd` and `max_turns=12` |
| Marker filter | yes | **no** (known gap vs Deep Agents) |

Same agents live under `plugin/` and load with `plugins=` because `cwd` is the CRM.


---

# Learning objectives

- Configure `ClaudeAgentOptions` so the parent may only use the `Agent` tool
- Implement `scope_hook` with the full `hookSpecificOutput` deny envelope
- Validate `--table-only` prints judge writes = `no`
- Troubleshoot a hook that fails **open** because of a typo
- Deploy the same `loop.py --once` on issue events (see GITHUB-ACTIONS.md)


---

# Scope. Two places, both required

1. `tools=[...]`. Judge and doer get `Read, Grep, Glob`. `NO_WRITE` strips Edit, Write, Bash.
2. `PreToolUse` hook `roles.scope_hook`. Deny writes outside the allow list.

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

Judge uses structured `output_format` (`JUDGE_SCHEMA`). Python writes the candidate. The hook still fires if a Write leaks.


---

# Cast. `roleplan.py`

```
enhancer: orchestrator, doer, judge
orchestrator  tools: Task                         writes: no
doer          tools: Read,Glob,Grep,Edit,Write,Bash   allow: tickets/**
judge         tools: Read,Glob,Grep,Bash          writes: no
```

```bash
python loop.py --table-only
```

If judge prints `yes`, stop. The port is wrong.


---

# Extra exits

`check_stop.py` also fires on `usd >= max_usd` and `turns >= max_turns`.

The SDK query itself stops via `max_budget_usd` / `max_turns`. `adapter.AgentSdkBackend` maps `error_max_turns*` and `error_max_budget*` to `stop_reason`.

Known gap: `Gh.latest_comment` does not filter `<!-- enhancer-loop -->`, and `comment()` does not append it. Deep Agents already does. Do not copy that gap into a new port.


---

# Commands

```bash
cd solutions/sol1_enhancer_agent_sdk
pip install -r ../../requirements-takehome.txt
cp config.json.example config.json
task table          # python loop.py --table-only
task test           # pytest, stubs the SDK, no key, no clone
task checks         # check_*.py --demo
task clone && task create-test-tickets
task run            # python loop.py --once --repo TARGET
```

Outcome line: `T900    waiting     round 1, still missing value, criteria`


---

# GitHub Actions

`ENHANCER_BACKEND=agent-sdk`. The job is:

```bash
python3 loop.py --once --repo "$GITHUB_WORKSPACE" --ticket "$TICKET"
```

Secret `ANTHROPIC_API_KEY`. Same issue events, same marker rule once you close the gap, same three exits. Copy `labs/lab1_enhancer/workflows/enhance-on-issue.yml` onto your CRM fork.


---

# Recap

The point is not that it runs. The point is that the rubric, the write scope, and the exits did not have to change to make it run.

The harness is the product. The framework is not.
