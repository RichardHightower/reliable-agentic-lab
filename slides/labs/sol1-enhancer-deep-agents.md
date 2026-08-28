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

# Scope. Three ways, all used

1. Per-subagent tool list. Judge is never handed write.
2. Path check **inside** the doer's write tool. Refusal is a sentence, not an exception (exceptions start retry loops).
3. Harness fence:
   - `FilesystemBackend(root_dir=crm, virtual_mode=True)` so `..` cannot walk off
   - `permissions=` deny writes on orchestrator, allow `tickets/**` on doer, deny on judge
   - Hide `write_file, edit_file, delete, execute` from the orchestrator
   - **Turn off the default `general-purpose` subagent.** It ships harness FS tools. Leaving it on is how a "scoped" agent writes `app/`.


---

# `check_stop.py` is a different contract

```python
def check(*, done, turns, max_turns, spent_usd=0.0, max_usd=2.0) -> dict:
    if done: return {stop: True, reason: "done"}
    if spent_usd >= max_usd: return {stop: True, reason: "cost"}
    if turns + 1 >= max_turns: return {stop: True, reason: "max turns"}
    return {stop: False, reason: None}
```

Repeated signature is **not** an exit here. That is a real behavioral fork vs the plugin. `MAX_USD = 2.0`. Done waits for human `LGTM`.


---

# Marker is implemented

`MARKER = "<!-- enhancer-loop -->"`. Fetch `per_page=100` because the default 30 plus a marker filter wedges long threads.

`already_acted_on` compares GitHub ids as **ints**. `"1000000001" <= "999999999"` is True as text and would skip a real new comment.


---

# Commands

```bash
cd solutions/sol1_enhancer_deep_agents
python3 loop.py --table-only     # judge writes column must be no
task test && task table && task checks
task clone && task create-test-tickets
task run                         # python3 loop.py --once --repo TARGET
```

Taskfile `dotenv: ['../../.env', '.env']`. First file that defines a var wins.

GitHub Actions: `ENHANCER_BACKEND=deep-agents`. Secret `ANTHROPIC_API_KEY`. Same copy-me workflow as the other sol1 ports.


---

# Recap

Deep Agents is a harness. The subagent `tools` list replaces the parent. Python still owns the outer budget.

If a port imports a shared engine, the design leaked. This folder copies `roleplan.py` and `write_scope.py` on purpose.
