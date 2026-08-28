---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_grok_build

Same loop. Artifact is a **project plugin** plus three registration shims.

Grok 1.0.5 does not register skills and agents from a project plugin on its own. Symlinks are the runnable surface.


---

# Plugin layout

```
.grok/plugins/ticket-enhancer/plugin.json     # name ticket-enhancer, 0.1.0
.grok/plugins/ticket-enhancer/agents/*.md
.grok/plugins/ticket-enhancer/skills/enhancer-loop/...

.grok/skills/enhancer-loop      -> ../plugins/ticket-enhancer/skills/enhancer-loop
.grok/agents/enhancer-judge.md  -> ../plugins/ticket-enhancer/agents/enhancer-judge.md
.grok/agents/enhancer-doer.md   -> ../plugins/ticket-enhancer/agents/enhancer-doer.md
```

Do not `grok plugin install`. That copies into `~/.grok`. Edits here then stop taking effect. `--plugin-dir` does not exist on this CLI.


---

# Trust is step zero

Trust attaches to the **git root**, not this folder. Headless `grok -p` never prompts. Until trusted, `task run` finds no skill and does nothing.

```bash
task trust
grok          # accept the prompt, maybe /plugins trust
grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
```

Check **names, never counts**. The Plugins line counts directories (`1 agents` even with two files, none loaded).


---

# Allowlist plus MCP deny

```yaml
tools:
  - read_file
  - grep
  - list_dir
disallowedTools:
  - search_tool
  - use_tool
```

Allowlist blocks write and spawn. Grok still injects MCP tools. Without the deny, a "read-only" judge can write an issue via GitHub MCP.

Subagent tool on 1.0.5 is `spawn_subagent`. README that says `task` is wrong on this CLI.


---

# `task run`

```
grok --always-approve
  --deny "Edit({{.LAB_ROOT}}/scripts/**)"
  --deny "Edit({{.LAB_ROOT}}/work/**/tests/**)"
  -p "/enhancer-loop --repo {{.TARGET}} {{.CLI_ARGS}}"
```

`-p` must come last. Hooks register but never fire on 1.0.5. An empty `debug.log` does not mean the skill failed to start.

Live progress:

```
grok --always-approve --output-format streaming-json -p "..."
```

No Grok loop skill. Polling is always external.


---

# Actions note

Hosted GitHub Actions is a poor fit for Grok (trust prompt, local shims). Prefer Claude Code, Agent SDK, or Deep Agents in `ENHANCER_BACKEND`. Keep Grok on a laptop or a Droplet (`labs/extra-credit/ext_5_digitalocean`).

The exits do not change if you do run it under Actions. See `labs/lab1_enhancer/GITHUB-ACTIONS.md`.


---

# Recap

Plugin on disk, shims to register, trust the git root, deny MCP writes. Same `check_fields.py`. Same three exits.
