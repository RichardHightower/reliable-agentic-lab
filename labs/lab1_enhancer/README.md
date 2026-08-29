# Lab 1. Ticket enhancer

A vague ticket in, a ready contract out. No human sits in an interactive
session driving this loop: it polls the ticket's GitHub issue for comments
and acts on what it finds.

**25 minutes for the four build prompts. Artifact: a plugin that grooms
every open ticket in your fork, one poll at a time.** Saturday default is
Claude Code. Codex, Grok, and OpenCode are first-class here too: you build
in this folder, and `task run` calls the CLI that matches the plugin you
built. You do fork setup and `task clone` once, from `SETUP.md`, before
this lab; the 25 minutes covers the four build prompts only.

`task poll-forever` never stops on its own, not even once every ticket
reaches `ready`. That is by design, a seminar stand-in for a real
scheduler, not a bug. `Ctrl-C` it when you are done.

## Work from this folder

```bash
cd labs/lab1_enhancer
```

Your coding agent runs here, not at the repo root. This folder has a
`.claude/settings.json` deny-list stub so a Claude session cannot wander.
That stub is not the plugin. The plugin is the skill tree you build from
the prompt for your tool.

## Set up your fork

1. Fork the target repo into your own GitHub account (never into
   `SpillwaveSolutions`, that is only where the canonical copy moves to
   around Saturday).
2. Copy the config template and fill in your GitHub username:

   ```bash
   cp config.json.example config.json
   ```

3. Clone your fork:

   ```bash
   task clone
   ```

   Every task here runs from this folder, standalone; you never need the
   repo root. `task clone` writes the fork to `../../work/`, a shared,
   gitignored folder outside this lab tree, on purpose, one clone for
   every module, not one per folder.

## Build it

One prompt per solution variant. Paste into the tool named in the prompt.

| Prompt | Answer |
|---|---|
| [prompts/claude-code.md](prompts/claude-code.md) | `solutions/sol1_enhancer/` |
| [prompts/codex.md](prompts/codex.md) | `solutions/sol1_enhancer_codex/` |
| [prompts/grok-build.md](prompts/grok-build.md) | `solutions/sol1_enhancer_grok_build/` |
| [prompts/opencode.md](prompts/opencode.md) | `solutions/sol1_enhancer_opencode/` |
| [prompts/agent-sdk.md](prompts/agent-sdk.md) | `solutions/sol1_enhancer_agent_sdk/` |
| [prompts/deep-agents.md](prompts/deep-agents.md) | `solutions/sol1_enhancer_deep_agents/` |

Saturday default is Claude Code: four prompts, pasted one at a time into an
interactive `claude` session, each building one piece (the judge agent, the
doer agent, the deterministic field check, the orchestrator skill). A fifth
prompt at the end has Claude Code diff your result against the answer.

A Grok, Codex, or OpenCode student builds the matching tree in this same
folder (`.grok/`, `.agents/`, `.opencode/`). Do not copy those into
`.claude/`. `task run` looks at which skill tree is present and calls that
CLI. `task detect` prints the choice without spending a token.

Agent SDK and Deep Agents are take-home. Python owns the loop. Do not copy
those fences into `.claude/`.

## Verify

```bash
task create-test-tickets && task run --
```

This tests the plugin you just built in this folder, not the answer in
`solutions/sol1_enhancer/`. It polls every open draft ticket and exits. See
[SPEC.md](../../solutions/sol1_enhancer/SPEC.md) for the full design.

`task run` does **not** always call `claude`. It dispatches:

| Skill tree present | CLI it calls |
|---|---|
| `.claude/skills/enhancer-loop` | `claude` |
| `.grok/plugins/ticket-enhancer/skills/enhancer-loop` | `grok` |
| `.agents/skills/enhancer-loop` | `codex` |
| `.opencode/skills/enhancer-loop` | `opencode` |

If more than one tree is present, set `AGENT=grok` (or `claude`, `codex`,
`opencode`). If none is present, it tells you to build from `prompts/` or
copy from [FALL-BEHIND.md](FALL-BEHIND.md) instead of dying with
`claude: executable file not found`.

For the length of the seminar, run it forever in one terminal, `Ctrl-C`
when you are done:

```bash
task poll-forever --
```

This is a seminar stand-in for a real scheduler, see `SPEC.md`'s "How this
should really run." Two other ways to keep polling: type
`/enhancer-loop --repo ...` directly in an interactive session of the tool
you built with (the same one you built the skill in works); or wrap
`task run` by hand:

```
/loop 10m task run --
```

Use a short `poll_interval` (`1m`, `30s`) in `config.json` while you are
testing this lab. A `10m` interval like the example above fits production,
not a live session where you want to see the next poll happen.

## When it stops, per ticket

- the newest comment is `LGTM`
- the round budget is spent
- two rounds in a row find exactly the same gaps, which means the human has
  not acted and another round will not help

## The gate

This lab writes no code, so the push gate does not fire. You meet it in
Module 2.

## If you fall behind

Stop typing and watch. Then copy the answer's scaffolding into this folder.
See [FALL-BEHIND.md](FALL-BEHIND.md).

## Deploy on GitHub Actions

`task poll-forever` is a seminar stand-in. Production listens to ticket
change events. Notes and a copy-me workflow:

- [GITHUB-ACTIONS.md](GITHUB-ACTIONS.md)
- [workflows/enhance-on-issue.yml](workflows/enhance-on-issue.yml)

Copy the YAML onto **your** CRM fork. The same notes are appended to every
`solutions/sol1_*` SPEC. The trigger moves. The exits stay.
