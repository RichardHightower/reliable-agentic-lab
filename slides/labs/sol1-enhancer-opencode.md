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

# What you will build

| Piece | Path |
|---|---|
| Judge | `.opencode/agents/enhancer-judge.md` |
| Doer | `.opencode/agents/enhancer-doer.md` |
| Skill | `.opencode/skills/enhancer-loop/SKILL.md` |
| Scripts | `.opencode/skills/enhancer-loop/scripts/check_{fields,stop}.py` |
| Command | `.opencode/command/enhancer-loop.md` |
| Permissions | `opencode.json` |

Saturday FALL-BEHIND.md still says "No OpenCode answer exists yet." That paragraph is stale. This folder is the answer.


---

# Why OpenCode is a different lesson

Claude omits Write from a YAML tool list. Codex starts a second process. OpenCode puts `permission: edit: deny` on the subagent.

`--auto` does not override explicit deny. That is the claim to prove.


---

# Learning objectives

- Configure OpenCode agents with `mode: subagent`
- Deny edit, bash, and task on the judge
- Invoke headless via `--command enhancer-loop`
- Probe the jail with `cksum` before a live poll
- Point Actions at `ENHANCER_BACKEND=opencode`


---

# Starting architecture

```
opencode run --auto --command enhancer-loop
  └── agent: build  (orchestrator, default)
         Task tool
            ├── enhancer-judge   permission.edit: deny
            └── enhancer-doer    permission.edit: deny
```

`--agent enhancer-judge` fails: "is a subagent, not a primary agent." That is correct. The orchestrator is `build`.


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

The body then says: if asked to write or edit, refuse and still return the JSON grade of the file as it currently is.


---

# `opencode.json` and the command file

```json
{ "permission": { "external_directory": "allow" } }
```

Without that, writes to `../../work/northwind-field-crm` become asks. Headless `--auto` would then stall.

`.opencode/command/enhancer-loop.md` pins `agent: build` and substitutes `$ARGUMENTS`.


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

No built-in loop skill. No self-reinvoke. First poll is about six minutes. Cap it:

```bash
timeout 360 task run --
```


---

# Jail probe before a live poll

Spawn the judge. Ask it to edit a file. `cksum` of that file must be identical.

If the file changed, `--auto` overrode deny and the port is wrong. Stop. Do not run `task create-test-tickets` yet.


---

# Commands

```bash
cd solutions/sol1_enhancer_opencode
cp config.json.example config.json
task clone
python3 .opencode/skills/enhancer-loop/scripts/check_fields.py --demo
python3 .opencode/skills/enhancer-loop/scripts/check_stop.py --demo
task create-test-tickets
timeout 360 task run --
```


---

# Expected result

Same as Saturday: stubs become real fields, `enhanced` after a rewrite, marked comment, state file.

`check_fields.py` still computes ready. The permission block did not have to change the rubric.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "is a subagent, not a primary" | `--agent enhancer-judge` | orchestrator is `build` |
| Ask-loop on CRM writes | missing `external_directory` | set allow in `opencode.json` |
| Judge edited the ticket | deny not applied | probe with `cksum` |
| Six-minute hang | first poll is slow | `timeout 360` |
| FALL-BEHIND says no answer | stale doc | this folder is the answer |


---

# Validation

- [ ] Judge YAML has `edit: deny`
- [ ] Jail probe: file checksum unchanged
- [ ] `--demo` scripts pass
- [ ] One poll labels `enhanced` after a rewrite
- [ ] Marker on the comment


---

# GitHub Actions

`ENHANCER_BACKEND=opencode`. The job needs `opencode` on the runner.

Copy `labs/lab1_enhancer/workflows/enhance-on-issue.yml` onto **your** CRM fork. Do not enable it on the instructor repo.

Skip comments that contain `<!-- enhancer-loop -->`.


---

# Recap

OpenCode isolation is a permission block on the subagent.

Same rubric. Same marker. Same exits. The loop did not have to change to make it run.
