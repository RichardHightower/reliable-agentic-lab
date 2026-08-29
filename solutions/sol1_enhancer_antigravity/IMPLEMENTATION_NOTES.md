# Implementation notes: how this plugin loads

Read this the first time `/enhancer-loop` does not appear in Antigravity.

## Antigravity finds this plugin by workspace root, not by plugin.json alone

Two load paths exist. They are easy to mix up.

| Path | What it loads | When it fires |
|---|---|---|
| `.agents/skills/` and `.agents/agents/` | workspace skills and custom subagents | opening this folder, or starting `agy` here |
| `.agents/plugins/ticket-enhancer/` | the Antigravity plugin pack | `agy plugin install` |

A plugin directory sitting in the tree does **not** auto-register. Antigravity
already discovers `.agents/skills/<folder>/SKILL.md` and
`.agents/agents/<name>.md` as workspace customizations. It still understands
the older `.agent/skills/` path; this port uses `.agents/`.

This folder ships three symlinks that point into the plugin:

```
.agents/skills/enhancer-loop
    -> ../plugins/ticket-enhancer/skills/enhancer-loop
.agents/agents/enhancer-judge.md
    -> ../plugins/ticket-enhancer/agents/enhancer-judge.md
.agents/agents/enhancer-doer.md
    -> ../plugins/ticket-enhancer/agents/enhancer-doer.md
```

Nothing is copied. The plugin stays the artifact and the single source of
truth. Editing a file under `.agents/plugins/` changes what runs on the next
poll.

Recreate them from this folder with:

```bash
mkdir -p .agents/skills .agents/agents
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop .agents/skills/enhancer-loop
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-judge.md .agents/agents/enhancer-judge.md
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-doer.md .agents/agents/enhancer-doer.md
```

`task inspect` / `bin/fence_check.py` confirms the three paths resolve.

## Open this folder, not the lab repo root

Antigravity discovers `.agents/skills/` from the **workspace root**. Open
`solutions/sol1_enhancer_antigravity/` as the folder. Open the lab repo instead
and Antigravity looks at the repo's own `.agents/`, which does not have this
skill.

`task run` pins `dir:` to this folder for the same reason. `agy` started at
the repo root cannot see `/enhancer-loop`.

## Tool names are Antigravity's

| Tool | Purpose |
|---|---|
| `view_file` | read a file |
| `grep_search` | search the tree |
| `replace_file_content` | write a file |
| `run_command` | shell |
| `invoke_subagent` | spawn a custom subagent |

The judge and the doer are allowlisted to `view_file` and `grep_search` only.
They also set `subagent: true`, `mainAgent: false`, and
`commandExecutionPolicy: off`. `task inspect` fails if write, shell, or spawn
appear, or if those three flags drift.

`--dangerously-skip-permissions` on `agy` is the orchestrator's yolo flag. It
does not give the judge a write tool. The judge's tool list still governs the
subagent.

A misspelled tool name in the allowlist can hang the subagent. Use the names
above, exactly.

## The subagent tool is `invoke_subagent`

`SKILL.md` tells the orchestrator to spawn the judge and the doer with
`invoke_subagent`, passing the custom agent's name. Claude Code calls this
`Task` / `Agent`. Copilot CLI calls it `agent`. Grok 1.0.5 calls it
`spawn_subagent`. Antigravity calls it `invoke_subagent`.

`mainAgent: false` keeps the two roles out of the primary agent picker. The
parent still spawns them. A subagent starts with a clean context: only the
final result returns to the parent.

## `agy -p` is headless

```bash
agy --dangerously-skip-permissions -p "/enhancer-loop --repo ../../work/northwind-field-crm"
```

`-p` is also `--print` and `--prompt`. Without `--dangerously-skip-permissions`
a headless poll stops on the first `gh` call. The `run` task is ordered that
way.

## The lockdown is deliberately uneven

The judge and the doer are read-only. The orchestrator holds the shell,
writes the ticket file, and runs `gh`. That asymmetry is the design, not an
oversight. The roles that could grade or draft their own work cannot act,
and the role that acts does not grade.
