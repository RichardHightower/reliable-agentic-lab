# Implementation notes: how this plugin loads, and why your run did nothing

Read this the first time `task run` prints nothing useful. Every note here is
something that cost time on a real machine, not something from a doc.

## Grok finds this plugin by its own working directory

Grok loads a project plugin from `.grok/plugins/` relative to the directory it
starts in. `task run` sets `dir:` to this folder for exactly that reason. Run
`grok` from the repository root instead and `ticket-enhancer` does not exist,
because the root has no `.grok/plugins/`.

Check what Grok actually sees:

```bash
cd solutions/sol1_enhancer_grok_build
grok inspect
```

You want three things in that output:

- `ticket-enhancer` under **Plugins**
- `enhancer-loop` under **Skills**
- `enhancer-judge` and `enhancer-doer` under **Agents**

If the plugin is missing entirely, `plugin.json` or a folder name is wrong.
Run `grok plugin validate .grok/plugins/ticket-enhancer` to find out which.

## A project plugin needs trust, and trust attaches to the clone

The first time you look, `grok inspect` most likely says this:

```
Plugins (44)
└ ticket-enhancer (project, disabled)      1 skills, 2 agents
```

`disabled` means Grok found the plugin and refuses to load it, because your
checkout is not trusted. Headless `grok -p` never prompts, so `task run`
quietly does nothing.

Grok records trust against the **git root**, not this folder. Trust the clone
once and every solution folder inside it is covered.

Grok 1.0.5 has no command-line way to grant trust. A coding agent cannot do it
for you either, because it needs a human click. Do it yourself, in a real
terminal:

1. Change to this folder.

   ```bash
   cd solutions/sol1_enhancer_grok_build
   ```

2. Start Grok with no arguments.

   ```bash
   grok
   ```

3. Accept the trust prompt for the folder.
4. If `grok inspect` still says `disabled`, type `/plugins trust` in that same
   session.
5. Quit Grok.
6. Confirm it took.

   ```bash
   grok inspect
   ```

   You want `Project trusted: yes` and `ticket-enhancer (project, enabled)`.

Do not hand-edit `~/.grok/trusted_folders.toml`. Let Grok write it.

The same trust switches on the debug hooks in
`.grok/plugins/ticket-enhancer/hooks/hooks.json`.

## Trust alone is not enough on 1.0.5, so this folder ships a shim

A trusted project plugin still contributes **only its hooks** on grok 1.0.5.
Its skill and its agents never register.

`grok inspect` shows the trap plainly. The **Plugins** section counts the
components. The **Skills** and **Agents** sections do not list them:

```
Plugins (44)
└ ticket-enhancer (project, enabled)       1 skills, 1 agents, hooks
```

`(project, enabled)` means "not disabled". It does not mean loaded. Only a
plugin installed through `grok plugin install`, and named in `[plugins]
enabled` in `~/.grok/config.toml`, gets its skills and agents registered. That
key is user-global. **Grok 1.0.5 has no project-level equivalent**, so there is
nothing this repository can commit to switch registration on.

`grok plugin enable ticket-enhancer` does not help either. It only knows
installed plugins:

```
Error: Plugin "ticket-enhancer" not found.
```

Four load paths were tested on 1.0.5. Every one loaded the hooks. None loaded
the skill or the agents:

| Load path | Skill and agents register? |
|---|---|
| `.grok/plugins/ticket-enhancer/` in this folder | no |
| the same plugin at the git root | no |
| a symlink into `~/.grok/plugins/` | no |
| a duplicate manifest in `.claude-plugin/plugin.json` | no |

### The shim

Project-scoped `.grok/skills/` and `.grok/agents/` do register. This folder
ships three symlinks that point into the plugin:

```
.grok/skills/enhancer-loop      -> ../plugins/ticket-enhancer/skills/enhancer-loop
.grok/agents/enhancer-judge.md  -> ../plugins/ticket-enhancer/agents/enhancer-judge.md
.grok/agents/enhancer-doer.md   -> ../plugins/ticket-enhancer/agents/enhancer-doer.md
```

Recreate them from this folder with:

```bash
mkdir -p .grok/skills .grok/agents
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop .grok/skills/enhancer-loop
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-judge.md .grok/agents/enhancer-judge.md
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-doer.md .grok/agents/enhancer-doer.md
```

Nothing is copied. The plugin stays the artifact and the single source of
truth, so editing a file under `.grok/plugins/` changes what runs on the next
poll. Delete the symlinks the day project plugins register their own
components.

### Check the names, not the counts

The counts in the **Plugins** line come from counting directories, so
`1 agents` shows even when two agent files are present and none loaded. Never
read them as proof. Confirm registration by name before you trust a poll:

```bash
grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
```

You want exactly three lines:

```
└ enhancer-loop      project
└ enhancer-judge     project
└ enhancer-doer      project
```

If any is missing, `spawn_subagent` cannot reach that role and the poll fails
partway through.

## Three things that look like the answer and are not

**`--plugin-dir` does not exist here.** The Grok README that ships in
`~/.grok/README.md` lists it as a session-scoped plugin location. Grok 1.0.5
rejects it:

```
$ grok --plugin-dir /tmp --help
error: unexpected argument '--plugin-dir' found
```

The flag is real on Grok agent stdio, not on this CLI. Do not put it in the
Taskfile.

**Do not run `grok plugin install`.** It copies the plugin into your Grok home
directory. The copy becomes the plugin Grok runs, so your edits in this folder
stop taking effect until you uninstall and reinstall. The whole point of a
project plugin is that the repository is the source of truth.

**Do not add `[plugins] paths` to `~/.grok/config.toml`.** It works, and it
hardcodes an absolute path into a global file. Move the checkout, or open a
second lab folder, and it breaks or fights the other one.

## `-p` takes the prompt as its own value

`-p` is short for `--single <PROMPT>`, so the prompt has to follow it
immediately. Put another flag in between and you get this:

```
$ grok -p --always-approve "/enhancer-loop ..."
error: a value is required for '--single <PROMPT>' but none was supplied
```

Every other flag goes before `-p`. The `run` task in `Taskfile.yml` is ordered
that way.

## The subagent tool is `spawn_subagent`

`SKILL.md` tells the orchestrator to spawn the judge and the doer with
`spawn_subagent`, passing the agent name as `subagent_type`. The README's tool
table calls it `task`. The README is wrong on this build, the same way it is
wrong about `--plugin-dir`. A probe run on 1.0.5 named `spawn_subagent`, and
that string is in the binary.

## Plugin hooks never fire, so this plugin ships none

The Claude Code answer logs one line per tool call to `debug.log`, driven by
`PreToolUse` and `PostToolUse` hooks. That would be useful here, because
`grok -p` prints nothing until the whole run finishes and a working run looks
hung.

It does not work on 1.0.5. A plugin `hooks/hooks.json` is the one component
that *does* register from an untrusted-then-trusted project plugin, and
`grok inspect` lists it under **Hooks**:

```
└ file                plugin: ticket-enhancer
```

It still never runs. A probe hook that wrote unconditionally to
`/tmp/grok-hook-probe.log` produced no file across a run that called
`list_dir`. An empty `debug.log` next to a working loop is worse than no
`debug.log` at all, because it reads as "the skill never started".

This plugin therefore ships no `hooks/` directory. For live progress, run the
poll yourself with streaming output instead:

```bash
grok --always-approve --output-format streaming-json \
  -p "/enhancer-loop --repo ../../work/northwind-field-crm --ticket T001"
```

`config.json` keeps its `debug` key so the shape matches the Claude Code
answer. Nothing reads it here.

## Grok adds MCP tools to an agent allowlist

Both agent files carry a read-only allowlist:

```yaml
tools:
  - read_file
  - grep
  - list_dir
```

A probe run confirmed that blocks writing and blocks spawning. It does not
block everything. Grok also handed the probe agent `search_tool` and
`use_tool`, which reach every connected MCP server. With a GitHub MCP server
connected, a judge that cannot write a file can still write an issue.

Both agents therefore also carry:

```yaml
disallowedTools:
  - search_tool
  - use_tool
```

An allowlist alone is not the whole fence here. Check what an agent really
holds by asking it to list its own tools.

## The lockdown is deliberately uneven

The judge and the doer are read-only. The orchestrator holds the shell, writes
the ticket file, and runs `gh`. That asymmetry is the design, not an
oversight. The roles that could grade or draft their own work cannot act, and
the role that acts does not grade.
