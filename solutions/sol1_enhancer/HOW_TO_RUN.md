# How to run this solution

Everything here runs from `solutions/sol1_enhancer/`, standalone. No task in
this folder depends on the repo root or on any other folder outside it.

## One-time setup

1. Copy the config template and fill in your GitHub username:

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval` (`"10m"` by default), the
   interval to use with `/loop` when you wrap `task run` for repeated
   polling. Use a short one (`"1m"`, `"30s"`) while testing.

2. Clone your fork:

   ```bash
   task clone
   ```

   This reads `fork_owner` and `repo_name` from `config.json` and clones
   that repo into `../../work/northwind-field-crm`. The upstream
   `northwind-field-crm` repo is public, so forking it is always possible.
   The one known edge case: if you cannot fork the upstream repo into your
   own account (GitHub refuses to fork a repo into an account that
   already owns it), create a plain independent copy instead:
   `gh repo create <owner>/<name> --public`, clone the upstream, repoint
   its `origin` at your new repo, and push. The enhancer loop does not
   care whether the relationship is a real GitHub fork, it only needs a
   repo with the same `tickets/` layout.

3. Optional: seed a few extra draft tickets, one per kind, beyond the real
   `T001` fixture:

   ```bash
   task create-test-tickets
   ```

   Writes `T900` (bug), `T901` (ui), `T902` (feature) into
   `../../work/northwind-field-crm/tickets/`. Skips any that already exist,
   safe to run again.

## Run one poll

```bash
task run -- --ticket T001
```

A ticket's first poll never needs a comment: it creates the ticket's GitHub
issue and runs one round automatically, so there is something for a human
to react to. `--simulate-comment "<text>"` is a dev-only flag that stands in
for a real issue comment, for testing without a `gh` round trip:

```bash
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
task run -- --ticket T001 --simulate-comment LGTM
```

Drop `--ticket` to poll every open draft ticket in one run:

```bash
task run --
```

## Repeated polling

This skill runs one step and exits; something else has to call it again.

For the seminar, run it forever in one terminal:

```bash
task poll-forever --
```

`while true: task run; sleep poll_interval`, nothing more. It never stops
on its own. `Ctrl-C` when you are done. This is a seminar stand-in, not
production shape, see `SPEC.md`'s "How this should really run".

Two other ways:

- **Interactive session** (`claude`, then type `/enhancer-loop --repo ...`):
  once any ticket is still waiting on its next poll, the skill invokes the
  built-in `loop` skill itself with `poll_interval` from `config.json`. No
  `/loop` typed by hand needed. Works because the CLI process stays alive
  between polls in an interactive session, unlike `task run` or
  `task poll-forever`.
- Wrap `task run` in `/loop` yourself:

  ```
  /loop 10m task run --
  ```

## Debug logging

`claude -p` (what `task run` invokes) prints nothing until the whole run
finishes, so a run with several subagent calls in a row can look hung when
it is not. Set `"debug": true` in `config.json`, then watch it live in a
second terminal. `touch debug.log` first: on macOS, `tail -f` on a file
that does not exist yet fails once instead of waiting for it to appear.

```bash
touch debug.log && tail -f debug.log
```

`PreToolUse` and `PostToolUse` hooks in `.claude/settings.json` write one
line per tool call, timestamp and tool name, only while `debug` is `true`.
`debug.log` is gitignored. Leave `debug` `false` for normal use, it is a
diagnostic, not a feature you need on to run this.

## Known issues fixed along the way

- `Write(path)` deny rules in `.claude/settings.json` are silently ignored
  by Claude Code; only `Edit(path)` rules are enforced (they cover every
  file-editing tool, Write included). Fixed here and in
  `labs/lab1_enhancer/.claude/settings.json`.
- The very first poll on a ticket used to require a comment before it would
  do anything, which is backwards: a ticket with never any comment has
  nothing for a human to react to yet. Fixed: the first poll always runs
  one round.
- `SKILL.md` used to say "read `config.json` next to `SKILL.md`," which is
  a different directory than where `config.json` actually lives. Fixed to
  say the current working directory, `solutions/sol1_enhancer/`.
- `TARGET`'s default was a relative path (`../../work/northwind-field-crm`),
  so it depended on the invoking process's working directory being exactly
  right. A git worktree shares one repo across multiple checkouts, each
  with its own separate, gitignored `work/` folder, and this once resolved
  against the wrong checkout: the orchestrator read and wrote a stray
  candidate file in an unrelated `work/northwind-field-crm`, caught its own
  mistake mid-run, cleaned up the stray file, but reported a stale result
  from the wrong checkout in its final summary. Fixed: `TARGET` and every
  other path in this Taskfile now build from Task's `TASKFILE_DIR`, which
  is always absolute, and `clone` and `run` pin `dir` to it too, so the
  `claude -p` subprocess always starts from this exact folder no matter
  where `task` itself was invoked from.
- On a real end-to-end run, the ticket file got fully enhanced (Problem,
  Proposal, Value, Wireframe, acceptance criteria), but the GitHub issue's
  body still showed the original two-line draft. Only the comment described
  the change in prose. A reviewer could not actually see what changed,
  only a claim about it. Fixed: step 7 now updates the issue body to match
  the ticket file's current content (frontmatter stripped) whenever it
  improves the ticket, not only the comment.
- On `LGTM`, the ticket's `loop:` field stayed `enhancer`. The next module
  (`loop: implementer`) discovers its own work the same way this one
  does, by that field, so a ticket left at `loop: enhancer` after passing
  would never be picked up. Fixed: step 4 now also sets `loop: implementer`
  when it sets `state: ready`, matching the reference
  `T001-due-dates.ready.md` fixture (`state: ready`, `loop: implementer`).
- `task run` runs one poll and exits; nothing polls in the background on
  its own. A comment you add on GitHub (including `LGTM`) sits there until
  the next `task run`, manual or `/loop`-wrapped, notices it.
