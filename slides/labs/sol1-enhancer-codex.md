---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_codex

Same loop as Lab 1. Isolation is a **process sandbox**, not a role flag.

Codex has no per-agent tool list. `$enhancer-judge` inside the orchestrator session inherits `workspace-write`. The jail is `bin/role.sh` starting a child `codex exec -s read-only`.

Work from `solutions/sol1_enhancer_codex`.


---

# What changes vs Saturday Claude Code

| Knob | Claude plugin | Codex |
|---|---|---|
| Discovery | `.claude/agents`, `.claude/skills` | `.agents/skills/{enhancer-loop,enhancer-judge,enhancer-doer}` |
| Isolation | YAML `tools:` omit Write | child process `-s read-only` |
| How judge runs | Claude subagent | `bin/role.sh enhancer-judge` |
| Headless | `claude -p "/enhancer-loop ..."` | `codex exec -s workspace-write ... "\$enhancer-loop ..." < /dev/null` |
| Self-reinvoke | interactive `/loop` | no. `codex exec` exits. |

`check_fields.py` and `check_stop.py` are byte-identical to the lab.


---

# Learning objectives

- Implement Codex skills under `.agents/skills/`
- Configure `bin/role.sh` so the judge cannot write
- Troubleshoot the four Codex traps: stdin hang, AGENTS.md recursion, trusted project, missing `--add-dir ~/.codex`
- Validate with `task fence-check` and `task run`


---

# The fence. `bin/role.sh`

```bash
codex exec -s read-only --cd "$DIR" -o "$OUT" "\$$SKILL $*" </dev/null >/dev/null 2>&1
cat "$OUT"
```

`< /dev/null` is load-bearing. `codex exec` appends open stdin and waits for EOF. `task` pipes stdin. Without the redirect, the child hangs silently.

Flags live here, not in SKILL.md. If the skill could pass `-s workspace-write`, the jail would be a suggestion.


---

# `task run`

```
codex exec
  -s workspace-write
  -c sandbox_workspace_write.network_access=true
  --add-dir {{.TARGET}}
  --add-dir {{.CODEX_HOME_DIR}}
  "\$enhancer-loop --repo {{.TARGET}} {{.CLI_ARGS}}"
  < /dev/null
```

Escape `\$enhancer-loop` or the shell eats `$enhancer`.

`--add-dir $HOME/.codex` is required. A child `codex exec` cannot start without it.


---

# AGENTS.md split by role

A first draft said "run judge through `bin/role.sh`". The judge read it, obeyed, started another judge. Infinite recursion.

Now:

- Judge and doer skills ignore orchestrator instructions.
- Orchestrator never invokes `$enhancer-judge` as an in-session skill. It shells out.

Read `IMPLEMENTATION_NOTES.md` before you "simplify" this.


---

# Four traps

| Trap | Symptom | Fix |
|---|---|---|
| Open stdin | silent hang | `< /dev/null` on every `codex exec` |
| AGENTS.md recursion | nested judges | split instructions by role |
| `trust_level = "trusted"` | orchestrator fence off | `task fence-check`. Judge/doer stay read-only either way. |
| Missing `--add-dir ~/.codex` | child cannot start | add it on `task run` |

Budget five minutes per poll. Three model processes per round (judge, doer, judge). `timeout 420 task run --` while developing.


---

# Commands and expected result

```bash
cd solutions/sol1_enhancer_codex
cp config.json.example config.json   # fork_owner
task clone
task fence-check
python3 .agents/skills/enhancer-loop/scripts/check_fields.py --demo
task create-test-tickets
timeout 420 task run --
```

Expected: same labels and state files as Lab 1. Same marker on comments. Same three exits.

GitHub Actions: set `ENHANCER_BACKEND=codex` in `labs/lab1_enhancer/GITHUB-ACTIONS.md`. Hosted runners must have `codex` installed. Prefer Agent SDK on Actions if Codex is not in the image.


---

# Recap

Isolation in Codex is a process sandbox, not a role flag.

The loop did not change. Ready is still `check_fields.py`. The judge still has no write path. The trigger can still move to Actions.
