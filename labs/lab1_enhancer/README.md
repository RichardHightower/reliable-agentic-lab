# Lab 1. Ticket enhancer

A vague ticket in, a ready contract out. No human sits in an interactive
session driving this loop: it polls the ticket's GitHub issue for comments
and acts on what it finds.

**25 minutes for the four build prompts. Artifact: a Claude Code plugin
that grooms every open ticket in your fork, one poll at a time.** You do
fork setup and `task clone` once, from `SETUP.md`, before this lab; the
25 minutes covers the four build prompts only.

`task poll-forever` never stops on its own, not even once every ticket
reaches `ready`. That is by design, a seminar stand-in for a real
scheduler, not a bug. `Ctrl-C` it when you are done.

## Work from this folder

```bash
cd labs/lab1_enhancer
```

Your coding agent runs here, not at the repo root. This folder has its own
`.claude/`, so the agents and the skill you build here apply, and nothing
else does.

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

Follow [prompts/claude-code.md](prompts/claude-code.md): four prompts,
pasted one at a time into an interactive `claude` session, each building one
piece (the judge agent, the doer agent, the deterministic field check, the
orchestrator skill). A fifth prompt at the end has Claude Code diff your
result against the answer.

## Verify

```bash
task create-test-tickets && task run --
```

This tests the plugin you just built in `.claude/`, not the answer in
`solutions/sol1_enhancer/`. It polls every open draft ticket and exits. See
[SPEC.md](../../solutions/sol1_enhancer/SPEC.md) for the full design.

For the length of the seminar, run it forever in one terminal, `Ctrl-C`
when you are done:

```bash
task poll-forever --
```

This is a seminar stand-in for a real scheduler, see `SPEC.md`'s "How this
should really run." Two other ways to keep polling: type
`/enhancer-loop --repo ...` directly in an interactive `claude` session
(the same one you built the skill in works), and the skill invokes the
built-in `loop` skill itself once a ticket is still waiting on its next
poll; or wrap `task run` in `/loop` by hand:

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
