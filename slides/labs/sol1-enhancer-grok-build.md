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

# What you will build

```
.grok/plugins/ticket-enhancer/plugin.json
.grok/plugins/ticket-enhancer/agents/{enhancer-judge,enhancer-doer}.md
.grok/plugins/ticket-enhancer/skills/enhancer-loop/...

.grok/skills/enhancer-loop      -> ../plugins/ticket-enhancer/skills/enhancer-loop
.grok/agents/enhancer-judge.md  -> ../plugins/ticket-enhancer/agents/enhancer-judge.md
.grok/agents/enhancer-doer.md   -> ../plugins/ticket-enhancer/agents/enhancer-doer.md
```

Do not `grok plugin install`. That copies into `~/.grok`. Edits here then stop taking effect.


---

# Why Grok is a different lesson

Claude discovers `.claude/` in the folder you launched from. Grok 1.0.5 discovers project plugins only after trust, and only through the shim paths.

Until trusted, `task run` finds no skill and does nothing. Headless `grok -p` never prompts. Trust is step zero.


---

# Learning objectives

- Build a Grok project plugin (`plugin.json` name `ticket-enhancer`)
- Register it with three `ln -sfn` shims
- Trust the **git root**, not this folder
- Deny MCP writes on a read-only judge
- Keep Grok off hosted Actions


---

# Starting architecture

```
grok -p "/enhancer-loop --repo ..."
  └── skill via .grok/skills/enhancer-loop  (symlink)
         spawn_subagent
            ├── enhancer-judge  allowlist + disallowedTools
            └── enhancer-doer   allowlist + disallowedTools
```

Subagent tool on 1.0.5 is `spawn_subagent`. A README that says `task` is wrong on this CLI.


---

# plugin.json

```json
{
  "name": "ticket-enhancer",
  "description": "One poll-and-act step that grooms draft tickets.",
  "version": "0.1.0"
}
```

`--plugin-dir` does not exist on this CLI. The shims are the install.


---

# Trust is step zero

Trust attaches to the **git root**, not `solutions/sol1_enhancer_grok_build`.

```bash
task trust
grok                 # accept the prompt, maybe /plugins trust
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


---

# `task run`

```
grok --always-approve
  --deny "Edit({{.LAB_ROOT}}/scripts/**)"
  --deny "Edit({{.LAB_ROOT}}/work/**/tests/**)"
  -p "/enhancer-loop --repo {{.TARGET}} {{.CLI_ARGS}}"
```

`-p` must come last.

Hooks register but never fire on 1.0.5. An empty `debug.log` does not mean the skill failed to start.

Live progress: `grok --always-approve --output-format streaming-json -p "..."`.


---

# Commands

```bash
cd solutions/sol1_enhancer_grok_build
cp config.json.example config.json
task clone
task trust
python3 .grok/plugins/ticket-enhancer/skills/enhancer-loop/scripts/check_fields.py --demo
task create-test-tickets
task run --
```


---

# Expected result

Same labels and state files as Lab 1. Same marker. Same three exits.

No Grok loop skill. Polling is always external: `task poll-forever` or Actions (poor fit, see next slide).


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Skill not found | untrusted git root | `task trust`, then inspect **names** |
| Judge wrote an issue | MCP tools injected | `disallowedTools: search_tool, use_tool` |
| Edits have no effect | `grok plugin install` copied away | use the shims, never install |
| Empty debug.log | hooks never fire on 1.0.5 | stream JSON instead |


---

# GitHub Actions

Hosted Actions is a poor fit (trust prompt, local shims). Set `ENHANCER_BACKEND` to `claude`, `agent-sdk`, or `deep-agents` on the runner.

Keep Grok on a laptop or a Droplet (`labs/extra-credit/ext_5_digitalocean`).

The exits do not change if you do run it under Actions. See `labs/lab1_enhancer/GITHUB-ACTIONS.md`.


---

# Recap

Plugin on disk. Shims to register. Trust the git root. Deny MCP writes.

Same `check_fields.py`. Same three exits. The loop is the product. The runtime is not.
