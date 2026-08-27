# How to run this

Everything runs from `solutions/sol1_enhancer_grok_build/`. This folder is
standalone.

## Step zero: trust the checkout

Grok only loads a project plugin from a trusted checkout, and it records trust
against the git root, so trusting the lab repo covers this folder and every
other solution folder in it.

```bash
task trust
```

That prints what Grok currently sees. If the line says
`ticket-enhancer (project, disabled)`, or the plugin is missing, you have not
granted trust yet. Run `grok` here once with no arguments, accept the trust
prompt, then quit and run `task trust` again.

Headless `grok -p` never prompts. Until trust exists, `task run` finds no
skill and does nothing useful. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)
covers this and the other three dead ends.

## One-time setup

1. Copy the config and fill in your GitHub username.

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval`, default `"10m"`. Use `"1m"` or
   `"30s"` while you are testing.

2. Clone your fork.

   ```bash
   task clone
   ```

   It clones into `../../work/northwind-field-crm`. The upstream repo is
   public, so forking always works. If GitHub refuses to fork into an account
   that already owns the repo, create an empty one with
   `gh repo create <owner>/<name> --public`, clone upstream, repoint `origin`,
   and push. The loop needs the same `tickets/` layout, not a real fork
   relationship.

3. Optional. Seed a few more draft tickets to work on.

   ```bash
   task create-test-tickets
   ```

   That writes `T900` (bug), `T901` (ui), and `T902` (feature). It skips a
   file that already exists, so it is safe to re-run.

## Run one poll

```bash
task run -- --ticket T001
```

A ticket's first poll never needs a comment. It creates the GitHub issue and
runs one round, so the human has something to react to.

`--simulate-comment "<text>"` stands in for a real issue comment. It is
dev-only.

```bash
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
task run -- --ticket T001 --simulate-comment "LGTM"
```

Drop `--ticket` to poll every open draft ticket.

## Repeated polling

```bash
task poll-forever --
```

That is the seminar answer: `while true: task run; sleep poll_interval`. Press
Ctrl-C to stop. It is not production shape. See SPEC.md for what is.

Grok has no built-in loop skill, so nothing inside the process can schedule
the next poll. A cron job or a scheduled GitHub Actions workflow is the real
answer.

## Debug logging

`grok -p` prints nothing until the whole run finishes, so a run that spawns
two agents looks hung when it is working fine.

Set `"debug": true` in `config.json`, then in a second terminal:

```bash
touch debug.log && tail -f debug.log
```

Create the file first. On macOS `tail -f` fails on a file that does not exist.

The `PreToolUse` and `PostToolUse` hooks in
`.grok/plugins/ticket-enhancer/hooks/hooks.json` write one line per tool call,
and only while `debug` is true. `debug.log` is gitignored. Leave `debug` false
the rest of the time.

Hook execution needs the same checkout trust as the plugin.

## Two bugs this port fixes

The Claude Code answer in `solutions/sol1_enhancer/` has both. This one does
not.

1. **The state file dropped `last_comment_id`.** Step 3 compares the newest
   comment's id against it, but step 8 wrote back only `round` and
   `previous_signature`. Every poll then saw the same comment as new and ran
   the same round again. Step 8 here always writes `last_comment_id`, and a
   `--simulate-comment` gets a stable derived id, so a repeated simulated
   comment behaves like the repeated real comment it stands in for.
2. **Discovery did not skip candidate files.** Step 0 excluded `*.ready.md`
   only. A run that died after writing `tickets/<id>.enhancer-candidate.md`
   left it behind, and the next run groomed that scratch file as a ticket of
   its own. Step 0 here skips it too.
