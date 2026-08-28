# Implementation notes: what changes when you move this loop to OpenCode

Read this before you change how a role is launched.

The Claude Code version of this lab lives in `solutions/sol1_enhancer/`. It
runs the same loop with the same rubric and the same exits. This folder is
the OpenCode-native answer. It replaces the stub from #96. It is not a
Python port, and it is not a copy of `.claude/` as the only tree.

## OpenCode plugins are not Agent Plugins

`plugin.json` plus `skills/` at a pack root is the cross-vendor Agent
Plugins spec. OpenCode's own "plugin" is a JS/TS module under
`.opencode/plugins/`. Those are different words. This loop does not use
either. OpenCode already discovers:

- `.opencode/skills/<name>/SKILL.md`
- `.opencode/agents/<name>.md` (also `.opencode/agent/`)
- `.claude/skills/` and `.agents/skills/` as compatibility paths

Source of truth here is `.opencode/`. No `plugin.json`.

## The headless argv

Probed on this machine with `opencode run --help`. The non-interactive
entry is `opencode run`, not the TUI.

`task run` uses:

```
opencode run --dir <TASKFILE_DIR> --auto --command enhancer-loop -- --repo <TARGET> <CLI_ARGS> < /dev/null
```

| Flag | Why |
|---|---|
| `--dir` | OpenCode walks up from cwd looking for `.opencode/`. Pin it so a Task invocation from elsewhere still loads this folder's agents and skills. |
| `--auto` | Auto-approve permissions that are not explicitly denied. The judge and doer still have `edit: deny`. |
| `--command enhancer-loop` | Runs `.opencode/command/enhancer-loop.md`. `$ARGUMENTS` is everything after `--`. |
| `< /dev/null` | Close stdin. Codex hangs on a Task pipe the same way; this CLI is closed the same way so a hang is not mistaken for a slow model. |

`--agent enhancer-judge` does **not** work. OpenCode prints `agent
"enhancer-judge" is a subagent, not a primary agent. Falling back to
default agent`. The orchestrator is the default `build` agent. It loads
the skill and spawns the judge and doer through the Task tool.

## The judge jail

Judge frontmatter:

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

`opencode agent list` from this folder shows `enhancer-judge (subagent)`
with `edit: deny`, `bash: deny`, `task: deny` as the last matching rules.

Live probe: `opencode run --dir . --auto` told `build` to spawn
`enhancer-judge` via the Task tool with a prompt that asked the judge to
edit `_jail_probe.md` and append `HACKED`. The child returned JSON only.
`cksum` of the file was identical before and after. `edit: deny` held. No
Codex-style `bin/role.sh` child process is needed.

A first poll on this machine took about six minutes (three model calls).
`timeout 180` killed a run mid-doer. Use 360 while developing.

`--auto` does not override an explicit deny.

## External writes

The target repo lives at `../../work/northwind-field-crm`, outside this
folder. OpenCode treats that as `external_directory`. `opencode.json` in
this folder sets `"external_directory": "allow"` so the orchestrator can
write tickets and state without hanging on an ask. Combined with `--auto`
for any remaining asks.

## What this port keeps from the Claude skill

Steps 0–8 are the same protocol.

- Step 0 skips `*.ready.md` and `*.enhancer-candidate.md`.
- Step 2 writes `github_issue` into the state file and the ticket
  frontmatter on search and create (#91, #114). A found issue with no state
  file must not look like a first poll, and the frontmatter entry outlives
  the state file the `LGTM` pass deletes.
- Step 3: `sim:` plus exact text for `--simulate-comment`. Persist
  `last_comment_id` in step 8 and on the ready-but-not-LGTM branch.
- Ready requires `check_fields.py` first. `LGTM` alone cannot set
  `state: ready`.
- Every comment this loop posts ends with `<!-- enhancer-loop -->`. Step 3
  ignores comments that contain that marker (#62). Do not filter by author.
  All four ports share this one marker on purpose, so two ports polling the
  same issue skip each other's comments instead of answering them (#114).

Script paths are `.opencode/skills/enhancer-loop/scripts/`, not
`.claude/...`. The scripts themselves are copies, not imports.

## Do not copy this answer onto the Codex or Grok branches

Codex isolation is a process sandbox (`bin/role.sh`). Grok Build isolation
is a project plugin plus trust. Same lesson, different knob.
