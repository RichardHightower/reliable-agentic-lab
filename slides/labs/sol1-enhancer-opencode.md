---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_opencode

Same loop. Jail is **permission deny**, not a child process.

Native `.opencode/` discovery. Not a copy of `.claude/`. Not an OpenCode JS plugin. No `plugin.json`.


---

# What you create (already in the answer folder)

```
.opencode/agents/enhancer-judge.md
.opencode/agents/enhancer-doer.md
.opencode/skills/enhancer-loop/SKILL.md
.opencode/skills/enhancer-loop/scripts/check_fields.py
.opencode/skills/enhancer-loop/scripts/check_stop.py
.opencode/command/enhancer-loop.md
opencode.json
```

`opencode.json` sets `"permission": { "external_directory": "allow" }` so writes to `../../work/northwind-field-crm` are not asks.


---

# Judge frontmatter. This is the type system

```yaml
---
description: Grade one enhancer ticket. Return JSON only.
mode: subagent
permission:
  edit: deny
  bash: deny
  task: deny
---
```

`--agent enhancer-judge` fails: "is a subagent, not a primary agent." Orchestrator is default `build`. It loads the skill and spawns via the **Task tool**.

`--auto` does not override explicit deny. Jail probe: spawn the judge, ask it to edit a file, `cksum` stays identical.


---

# Headless argv

```
opencode run
  --dir {{.TASKFILE_DIR}}
  --auto
  --command enhancer-loop
  --
  --repo {{.TARGET}} {{.CLI_ARGS}}
  < /dev/null
```

`.opencode/command/enhancer-loop.md` pins `agent: build` and substitutes `$ARGUMENTS`.

No built-in loop skill. No self-reinvoke. First poll ~6 minutes. `timeout 360 task run --`.


---

# Commands

```bash
cd solutions/sol1_enhancer_opencode
cp config.json.example config.json
task clone
python3 .opencode/skills/enhancer-loop/scripts/check_fields.py --demo
task create-test-tickets
timeout 360 task run --
```

FALL-BEHIND.md in the Saturday lab still says "No OpenCode answer exists yet." That paragraph is stale. This folder is the answer.

GitHub Actions: `ENHANCER_BACKEND=opencode`. See `labs/lab1_enhancer/GITHUB-ACTIONS.md`.


---

# Recap

OpenCode isolation is a permission block on the subagent. Same rubric, same marker, same exits. The loop did not have to change to make it run.
