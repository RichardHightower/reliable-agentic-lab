# Prompt for LangChain Deep Agents

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`loop.py` in this folder.

Rebuild the broken-PR fixer as a Python loop on LangChain Deep Agents. This
is a config port of the graph, not the live driver. Demo `broken-pr` from
`solutions/sol4_fixer_agent_sdk`. The finished answer is
`solutions/sol4_fixer_deep_agents/`. Read its
[SPEC.md](../../../solutions/sol4_fixer_deep_agents/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol4_fixer_deep_agents/HOW_TO_RUN.md), and
[DESIGN_DOC.md](../../../solutions/sol4_fixer_deep_agents/DESIGN_DOC.md).

Do not copy these harness fences into this lab folder.

Python owns the role table and the write scope. The model is the
code-implementer. It does not edit `tests/**`. Deny stays the unattended
rule. There is no interrupt on this path.

Needs `deepagents>=0.7`.

```bash
cd solutions/sol4_fixer_deep_agents
claude
```

---

## Prompt 0: the things that will waste your hour

1. Three fences, all required. Turn the default `general-purpose` subagent
   off. Leaving it on is how a scoped agent writes `tests/**`.
2. Skills are mounted, not pasted: `skills/code_implementer/SKILL.md` and
   `skills/judge/SKILL.md`.
3. This port is the graph. The live unattended run is the Agent SDK folder.
   `task reset` still checks out `broken-pr` and refuses a dirty clone.
4. `task setup` creates `.venv`. Homebrew Python will refuse system pip.

---

## Prompt 1: the role table

```
Create roleplan.py. Cast: orchestrator, code_implementer, judge.

code_implementer owns app/**, denied tests/**.

task table. The judge must print no. If it prints yes, stop.
```

---

## Prompt 2: the three fences

```
Create roles.py. Tool list per subagent. Path check inside the write tool.
Harness profile hides write_file / edit_file / delete / execute on the
orchestrator and turns general-purpose off.

FilesystemBackend(virtual_mode=True). Resolve paths before a custom tool
touches disk.
```

---

## Prompt 3: the loop

```
Same four stops as the Agent SDK driver: tests green; same failures twice;
budget spent; human merge. The loop never gets a merge tool.

Python holds the loop. The model edits app/** only.
```

---

## Verify

```bash
cd solutions/sol4_fixer_deep_agents
task setup
task table
task test
task clone
task reset
task run
```

`task test` and `task table` need no key.

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol4_fixer_deep_agents/, behavior first,
wording second. I will decide what to change.
```
