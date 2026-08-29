# How to run this solution

Everything here runs from `solutions/sol1_enhancer/`, standalone. No task in
this folder depends on the repo root or on any other folder outside it.

This folder is Claude Code. `task run` calls `claude`. If that binary is
missing, the preflight prints the Grok, OpenCode, and Codex folders and
exits 127. Do not install Claude Code just to satisfy a Grok lab.

| Tool | Folder |
|---|---|
| Claude Code | `solutions/sol1_enhancer/` (this one) |
| Grok Build | `solutions/sol1_enhancer_grok_build/` |
| OpenCode | `solutions/sol1_enhancer_opencode/` |
| Codex | `solutions/sol1_enhancer_codex/` |
| Lab (detects the skill tree) | `labs/lab1_enhancer/` (`task detect`) |

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

3. Create tickets with the seed task, or file one in the GitHub UI.

   ```bash
   task create-test-tickets
   ```

   Writes `T900` (bug), `T901` (ui), `T902` (feature) if they are missing,
   then opens a GitHub issue for every draft enhancer ticket, including
   `T001`. Stamps `github_issue:` into each file. Reuses an existing issue
   with the same `[Txxx]` title. Reopens a closed one. Safe to run again.

   You can also file a ticket in the GitHub UI. Next `task run --` lists
   open issues, writes a local draft if one is missing, and enhances it.
   No seed file required. Title `[Txxx] ...` keeps that id; otherwise the
   id is `T{issue number}`.


## Retest from scratch

`create-test-tickets` reopens an issue whose title still starts with `[Txxx]`.
Closing by hand is not enough. This retires those issues so a new seed
creates new ones.

```bash
task reset-test-tickets
task create-test-tickets
task run --
```

It rewrites each matching GitHub title to `[retired-Txxx-<timestamp>] ...`,
closes it, drops `github_issue` from the ticket files, deletes enhancer
state, restores tracked tickets from git, and removes T900/T901/T902 so
they are rewritten as fresh drafts.

## Run one poll over every open ticket

This is the demo. No ticket name. No simulated comment. The loop evaluates
every open draft and enhances it if it still needs work. Comments do not
trigger edits. The `enhanced` label is added on first touch, not at create
time. A human reviews the issue and comments `LGTM`. Only then, and only if
the rubric is already green, does the loop mark the ticket ready.

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

## Reset a ticket to run it again

Closing the GitHub issue is not a reset. It is the one thing that reliably
breaks the next poll.

The loop finds a ticket's issue through the state file, then the ticket
frontmatter, then a title search. Close the issue and the first two still
point at it, so the loop stops and tells you to reopen it. The loop never
opens a second issue.

Reset all three pieces instead:

1. Put the ticket file back to a draft. Keep the issue number.

   ```
   ---
   id: T901
   state: draft
   loop: enhancer
   github_issue: 8
   ---
   ```

2. Drop the loop's memory of the ticket.

   ```bash
   rm -f ../../work/northwind-field-crm/.harness/last-enhancer-T901.json
   ```

3. Reopen the same issue, so its comments survive.

   ```bash
   gh issue reopen 8 --repo <owner>/<repo>
   ```

Same number, same title, new poll. To start completely fresh instead, delete
the ticket file and run `task create-test-tickets`. That task opens the new
issue. `task run` does not.

Two messages send you back to this section:

- `issue N is closed; reopen it`. Somebody closed the issue for a ticket that
  is still a draft. Reopen it, or reset the ticket properly.
- `<id>: no GitHub issue; run task create-test-tickets`. The markdown file
  exists, but no issue does. Run the seed task. Do not expect `task run` to
  open one.
- `T901: already ready / implementer, skipping`. The ticket is finished.
  Reset it if you meant to run it again.

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
