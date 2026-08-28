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

# What you will build

A Codex skill pack that grooms draft tickets the same way Saturday's Claude plugin does.

| Piece | Path |
|---|---|
| Orchestrator | `.agents/skills/enhancer-loop/SKILL.md` |
| Judge skill | `.agents/skills/enhancer-judge/SKILL.md` |
| Doer skill | `.agents/skills/enhancer-doer/SKILL.md` |
| Field check | `.agents/skills/enhancer-loop/scripts/check_fields.py` |
| Stop check | `.agents/skills/enhancer-loop/scripts/check_stop.py` |
| Jail | `bin/role.sh` |
| Fence probe | `bin/fence_check.sh` |

`check_fields.py` and `check_stop.py` are byte-identical to the lab.


---

# Why Codex is a different lesson

Claude isolates by omitting Write from YAML. Codex cannot. Every in-session skill inherits the parent's sandbox.

If the orchestrator runs under `workspace-write`, an in-session `$enhancer-judge` can edit the ticket it grades.

The product is still: vague issue in, ready contract out. The new knob is a child process.


---

# Learning objectives

- Configure Codex skills under `.agents/skills/`
- Implement `bin/role.sh` so judge and doer cannot write
- Troubleshoot the four Codex traps
- Validate with `task fence-check` then `task run`
- Deploy the same loop on issue events (`ENHANCER_BACKEND=codex`)


---

# Starting architecture

```
task run
  └── codex exec -s workspace-write   (orchestrator)
         ├── bin/role.sh enhancer-judge
         │      └── codex exec -s read-only
         └── bin/role.sh enhancer-doer
                └── codex exec -s read-only
```

Trigger still lives outside. One poll, then exit. Labels, marker, and three exits are unchanged.


---

# Prerequisites

```bash
cd solutions/sol1_enhancer_codex
codex --version
cp config.json.example config.json   # fork_owner
task clone
task fence-check
```

`task fence-check` fails if `~/.codex/config.toml` has `trust_level = "trusted"`. That setting silently turns the orchestrator fence off. Judge and doer stay read-only either way.


---

# The fence. Flags live in the script

```bash
# bin/role.sh. The flags are not in SKILL.md on purpose.
codex exec -s read-only --cd "$DIR" -o "$OUT" "\$$SKILL $*" \
  </dev/null >/dev/null 2>&1
cat "$OUT"
```

`< /dev/null` is load-bearing. `codex exec` appends open stdin and waits for EOF. `task` pipes stdin. Without the redirect the child hangs with no error.

`--cd` lands in this folder so Codex finds `.agents/skills`. Ticket paths are passed absolute. A read-only process may still read outside its workspace.


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

- Judge and doer ignore orchestrator instructions
- Orchestrator never invokes `$enhancer-judge` as an in-session skill
- It shells out through `bin/role.sh`

Read `IMPLEMENTATION_NOTES.md` before you "simplify" this.


---

# Three model processes per round

1. Judge scores the current ticket
2. Doer drafts a replacement body
3. Judge scores the candidate

Budget five minutes per poll. `timeout 420 task run --` while developing.

No self-reinvoke. `codex exec` exits when the turn ends. `task poll-forever` is still the seminar scheduler.


---

# Commands and expected result

```bash
python3 .agents/skills/enhancer-loop/scripts/check_fields.py --demo
python3 .agents/skills/enhancer-loop/scripts/check_stop.py --demo
task create-test-tickets
timeout 420 task run --
```

Expected: T900/T901/T902 grooms, `enhanced` label after a real rewrite, comment with `<!-- enhancer-loop -->`, state file under `.harness/`.

Second poll with no new human comment: no-op. Must not post again.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Silent hang | open stdin | `< /dev/null` on every `codex exec` |
| Nested judges | AGENTS.md recursion | split instructions by role |
| Orchestrator can write as judge | `trust_level = trusted` | `task fence-check` |
| Child cannot start | missing `--add-dir ~/.codex` | add it on `task run` |
| `$enhancer` empty | unescaped `$` in Taskfile | `\$enhancer-loop` |


---

# Validation checklist

- [ ] `task fence-check` is green
- [ ] `--demo` scripts pass
- [ ] Judge process is `-s read-only`
- [ ] One poll rewrites a stub and labels `enhanced`
- [ ] Marker is on the posted comment
- [ ] `LGTM` plus green rubric sets `ready`


---

# GitHub Actions

Set `ENHANCER_BACKEND=codex` in the copy-me workflow:

`labs/lab1_enhancer/workflows/enhance-on-issue.yml`

Hosted runners must have `codex` installed. If they do not, use Agent SDK or Claude Code on Actions. Keep Codex on a laptop.

The trigger starts one poll. This folder still owns the exits. Skip `<!-- enhancer-loop -->`.


---

# Recap

Isolation in Codex is a process sandbox, not a role flag.

The loop did not change. Ready is still `check_fields.py`. The judge still has no write path.

**Takeaways**

1. Flags live in `bin/role.sh`, not in the skill.
2. Close stdin.
3. Split AGENTS.md by role or you recurse.
4. Same three exits as Saturday.
