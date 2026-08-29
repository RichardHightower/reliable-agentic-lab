# Implementation notes: how this plugin loads, and why Chat has no skill

Read this the first time Copilot Chat does not list `/enhancer-loop`. Every
note here is something that cost time against the VS Code Agent Plugins
docs, not something from a guess.

## VS Code finds this plugin by workspace root, not by plugin.json alone

Two load paths exist. They are easy to mix up.

| Path | What it loads | When it fires |
|---|---|---|
| `.github/skills/` and `.github/agents/` | project skills and custom agents | opening this folder as the workspace, or starting Copilot CLI here |
| `.github/plugins/ticket-enhancer/` | the Agent Plugins 1.0 pack | **Chat: Install Plugin From Source**, or `chat.pluginLocations` |

A plugin directory sitting in the tree does **not** auto-register. That is
the same trap Grok 1.0.5 hit, with a cleaner way out: VS Code already
discovers `.github/skills/` and `.github/agents/` as project customizations.

This folder ships three symlinks that point into the plugin:

```
.github/skills/enhancer-loop
    -> ../plugins/ticket-enhancer/skills/enhancer-loop
.github/agents/enhancer-judge.agent.md
    -> ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-judge.agent.md
.github/agents/enhancer-doer.agent.md
    -> ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-doer.agent.md
```

Nothing is copied. The plugin stays the artifact and the single source of
truth. Editing a file under `.github/plugins/` changes what runs on the next
poll.

Recreate them from this folder with:

```bash
mkdir -p .github/skills .github/agents
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop .github/skills/enhancer-loop
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-judge.agent.md .github/agents/enhancer-judge.agent.md
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-doer.agent.md .github/agents/enhancer-doer.agent.md
```

`task inspect` / `bin/fence_check.py` confirms the three paths resolve.

## Do not also set `chat.pluginLocations`

`.vscode/settings.json` turns on skill-as-tool and custom-agent hooks. It
does **not** point `chat.pluginLocations` at the plugin. Doing both would
load the skill twice: once as `/enhancer-loop` from `.github/skills/`, and
once as `/ticket-enhancer:enhancer-loop` from the plugin prefix.

Install from source only when you want the marketplace shape, on a machine
that is not already opening this folder as the workspace.

## Open this folder, not the lab repo root

VS Code discovers `.github/skills/` from the **workspace root**. Open
`solutions/sol1_enhancer_vscode/` as the folder. Open the lab repo instead
and Copilot looks at the repo's own `.github/skills/`, which does not have
this skill.

`task run` pins `dir:` to this folder for the same reason. Copilot CLI
started at the repo root cannot see `/enhancer-loop`.

Check what Copilot actually sees:

```bash
cd solutions/sol1_enhancer_vscode
copilot skill list
```

You want `enhancer-loop`. Custom agents do not always print from that
command. Confirm them in the VS Code agent picker, or by asking the parent
to spawn `enhancer-judge`.

## The Agent Plugins 1.0 layout is not Claude's

Claude Code plugins put `plugin.json` under `.claude-plugin/` and agents
next to `skills/` at the plugin root. VS Code follows the portable Agent
Plugins standard:

```
.github/plugins/ticket-enhancer/
  plugin.json                         Agent Plugins 1.0 manifest
  skills/enhancer-loop/SKILL.md       portable skill
  com.github.copilot/
    agents/*.agent.md                 VS Code custom agents
    hooks/hooks.json                  VS Code hooks
```

Other clients ignore `com.github.copilot/`. Skills stay portable. Agents
are client-specific because the tool names differ.

`plugin.json` `name` is kebab-case with no slash or colon. The skill
`name` in frontmatter is plain `enhancer-loop`, matching its directory.
A namespaced skill name (`ticket-enhancer/enhancer-loop`) is silently
skipped. That is a documented VS Code failure mode.

Custom agents use the `.agent.md` suffix. VS Code also accepts `.md` under
`.claude/agents/`. This port uses `.agent.md` because that is the VS Code
native format.

## The subagent tool is `agent`

`SKILL.md` tells the orchestrator to spawn the judge and the doer with the
`agent` tool, passing the custom agent's name. Claude Code calls this
`Task` / `Agent`. Grok 1.0.5 calls it `spawn_subagent`. VS Code calls it
`agent`.

The two custom agents set `user-invocable: false` so they do not appear as
primary agents in the Chat dropdown. The parent still spawns them as
subagents. A subagent in VS Code runs in a forked context: only the final
result returns to the parent. That is the point of splitting the judge and
the doer out of the skill.

## An allowlist is the fence

Both agent files carry a read-only allowlist:

```yaml
tools: ['search/codebase', 'search/usages', 'web/fetch']
```

That list has no `edit`, no `runCommands`, and no `agent`. `task inspect`
fails if any of those appear. The parent Copilot agent, running the skill,
keeps write and spawn. That uneven lockdown is the design.

`--allow-all` on Copilot CLI is the orchestrator's yolo flag. It does not
give the judge a write tool. The judge's tool list still governs the
subagent.

## Hooks actually fire

The Grok Build port ships no hooks, because a plugin `hooks.json` registered
on grok 1.0.5 and never ran. VS Code runs `PreToolUse` and `PostToolUse`.
This plugin logs one line per tool call to `debug.log` when
`config.json` has `"debug": true`.

Turn that key on when a poll looks hung. Leave it off for a demo, or the
log becomes the thing people stare at.

## Skill slash-command prefix

Loaded from `.github/skills/`, the skill is `/enhancer-loop`. Loaded from an
installed plugin, VS Code prefixes it with the plugin name:
`/ticket-enhancer:enhancer-loop`. `task run` uses the workspace form.

Do not put that prefix in the `name:` field. The prefix is added by the
host.

## Copilot CLI `-p` is `--prompt`

```bash
copilot --allow-all --prompt "/enhancer-loop --repo ../../work/northwind-field-crm"
```

`--allow-all` (also `--yolo`) skips per-tool confirmation. Without it a
headless poll stops on the first `gh` call. The `run` task is ordered that
way.

There is no `--plugin-dir`. Install-from-source is a Chat command, not a
CLI flag.

## The lockdown is deliberately uneven

The judge and the doer are read-only. The orchestrator holds the shell,
writes the ticket file, and runs `gh`. That asymmetry is the design, not an
oversight. The roles that could grade or draft their own work cannot act,
and the role that acts does not grade.
