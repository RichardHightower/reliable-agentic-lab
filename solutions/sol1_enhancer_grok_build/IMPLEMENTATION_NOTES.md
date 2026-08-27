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

Grok 1.0.5 has no command-line way to grant trust. Do it through the
interactive UI:

1. `cd solutions/sol1_enhancer_grok_build`
2. Run `grok` with no arguments.
3. Accept the trust prompt for the folder.
4. Type `/plugins trust` if the prompt did not already cover the plugin, then
   quit.
5. Run `task trust` again. The `disabled` marker is gone.

The same trust switches on the debug hooks in
`.grok/plugins/ticket-enhancer/hooks/hooks.json`.

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
