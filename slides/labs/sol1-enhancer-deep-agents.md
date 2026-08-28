---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_deep_agents

Take-home. LangChain Deep Agents >= 0.7.

Python owns the loop. The doer **holds a write tool**, scoped to `tickets/**`. The judge still has none.

Model: `anthropic:claude-sonnet-5`.


---

# What you will build

| File | Job |
|---|---|
| `enhancer.py` | poll-and-act in Python |
| `roles.py` | `create_deep_agent`, scoped write tool |
| `skills/doer/SKILL.md` | doer prompt |
| `skills/judge/SKILL.md` | judge prompt |
| `check_stop.py` | done, cost, max turns. Signature is not an exit |
| `tests/` | pytest, no SDK |

Turn off the default `general-purpose` subagent. It ships harness FS tools. Leaving it on is how a "scoped" agent writes `app/`.


---

# Learning objectives

- Hand each subagent its own tool list
- Put the path check **inside** the write tool
- Refuse with a sentence, not an exception
- Hide orchestrator write tools
- Compare `check_stop.py` to the plugin (signature is not an exit here)


---

# Starting architecture

```
python3 loop.py --once --repo TARGET
  └── create_deep_agent
         orchestrator: no write_file, edit_file, delete, execute
         doer: write tool, tickets/** only
         judge: read_file only
  FilesystemBackend(root_dir=crm, virtual_mode=True)
```


---

# Scope. Three ways, all used

1. Per-subagent tool list. Judge is never handed write.
2. Path check inside the doer's write tool.
3. Harness fence: virtual FS root, permissions deny on orchestrator, allow `tickets/**` on doer, deny on judge.

```python
ORCHESTRATOR_EXCLUDED_TOOLS = {write_file, edit_file, delete, execute}
```


---

# Refusal is a sentence

```python
@tool(f"write_{role.name}")
def write(path: str, content: str) -> str:
    try:
        scope.check(path)
    except ScopeViolation:
        return f"REFUSED. {role.name} may write {allowed}. {path} is outside that scope."
    (repo / path).write_text(content, encoding="utf-8")
    return f"wrote {path}"
```

An unformatted exception in an agent's context tends to start a retry loop. A short sentence tends to change the next action.


---

# `check_stop.py` is a different contract

```python
def check(*, done, turns, max_turns, spent_usd=0.0, max_usd=2.0) -> dict:
    if done: return {stop: True, reason: "done"}
    if spent_usd >= max_usd: return {stop: True, reason: "cost"}
    if turns + 1 >= max_turns: return {stop: True, reason: "max turns"}
    return {stop: False, reason: None}
```

Repeated signature is **not** an exit. Stuck work burns turns or dollars until cost or max-turns fires. `MAX_USD = 2.0`. Done waits for human `LGTM`.


---

# Marker is implemented

`MARKER = "<!-- enhancer-loop -->"`. Fetch `per_page=100` because the default 30 plus a marker filter wedges long threads.

`already_acted_on` compares GitHub ids as **ints**. `"1000000001" <= "999999999"` is True as text and would skip a real new comment.


---

# Commands

```bash
cd solutions/sol1_enhancer_deep_agents
python3 loop.py --table-only
task test && task table && task checks
task clone && task create-test-tickets
task run
```

Taskfile `dotenv: ['../../.env', '.env']`. First file that defines a var wins.


---

# Expected table

```
role           writes  scope
orchestrator   no      nothing
doer           yes     tickets/**
judge          no      nothing
```

If judge prints `yes`, stop.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Writes `app/` | default general-purpose still on | turn it off |
| Retry storm | write tool raises | return a sentence |
| Skipped a new comment | id compared as text | compare as ints |
| Stopped on same gaps | copied plugin check_stop | signature is not an exit here |


---

# Validation

- [ ] table: judge `no`
- [ ] pytest green without a key
- [ ] doer write to `tickets/T900.md` works
- [ ] doer write to `app/main.py` returns REFUSED
- [ ] marker on posted comments


---

# GitHub Actions

`ENHANCER_BACKEND=deep-agents`. Secret `ANTHROPIC_API_KEY`.

```bash
python3 loop.py --once --repo "$GITHUB_WORKSPACE" --ticket "$TICKET"
```

Same copy-me workflow as the other sol1 ports.


---

# Recap

Deep Agents is a harness. The subagent tools list replaces the parent. Python still owns the outer budget.

Three belts: missing tool, in-tool path check, harness profile. All three.
