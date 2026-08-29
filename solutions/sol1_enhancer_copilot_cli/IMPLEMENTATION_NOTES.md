# Implementation notes: how this plugin loads

Read this the first time `copilot skill list` does not name `enhancer-loop`.

## Copilot CLI finds this plugin by cwd, not by plugin.json alone

Two load paths exist. They are easy to mix up.

| Path | What it loads | When it fires |
|---|---|---|
| `.github/skills/` and `.github/agents/` | project skills and custom agents | starting Copilot CLI in this folder |
| `.github/plugins/ticket-enhancer/` | the Agent Plugins 1.0 pack | install-from-source / `copilot plugin` |

A plugin directory sitting in the tree does **not** auto-register. Copilot CLI
already discovers `.github/skills/` and `.github/agents/*.agent.md` as project
customizations.

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

## Start Copilot in this folder, not the lab repo root

Copilot CLI discovers `.github/skills/` from its **current working directory**.
`task run` pins `dir:` to this folder for that reason. Copilot started at the
repo root cannot see `/enhancer-loop`.

```bash
cd solutions/sol1_enhancer_copilot_cli
copilot skill list
```

You want `enhancer-loop`. Custom agents do not always print from that
command. Confirm them by asking the parent to spawn `enhancer-judge`.

## Tool names are the CLI aliases

VS Code Copilot uses `search/codebase`, `runCommands`, `web/fetch`. Copilot CLI
uses the shared custom-agent aliases:

| Alias | Purpose |
|---|---|
| `read` | view file contents |
| `search` | grep / glob |
| `edit` | write files |
| `execute` | shell |
| `agent` | spawn a custom agent as a subagent |

The judge and the doer are allowlisted to `read` and `search` only. `task inspect`
fails if `edit`, `execute`/`shell`, or `agent` appear.

`--allow-all` on Copilot CLI is the orchestrator's yolo flag. It does not
give the judge a write tool. The judge's tool list still governs the
subagent.

## The subagent tool is `agent`

`SKILL.md` tells the orchestrator to spawn the judge and the doer with the
`agent` tool, passing the custom agent's name. Claude Code calls this
`Task` / `Agent`. Grok 1.0.5 calls it `spawn_subagent`. Antigravity calls it
`invoke_subagent`. Copilot CLI calls it `agent`.

The two custom agents set `user-invocable: false` so they do not appear as
primary agents under `/agent`. The parent still spawns them as subagents.

## Copilot CLI `--prompt` is headless

```bash
copilot --allow-all --prompt "/enhancer-loop --repo ../../work/northwind-field-crm"
```

`--allow-all` (also `--yolo`) skips per-tool confirmation. Without it a
headless poll stops on the first `gh` call. The `run` task is ordered that
way.

There is no `--plugin-dir`. Workspace discovery is the `.github/skills/`
and `.github/agents/` tree.

## The lockdown is deliberately uneven

The judge and the doer are read-only. The orchestrator holds the shell,
writes the ticket file, and runs `gh`. That asymmetry is the design, not an
oversight. The roles that could grade or draft their own work cannot act,
and the role that acts does not grade.
