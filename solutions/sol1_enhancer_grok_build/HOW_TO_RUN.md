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
skill and does nothing useful.

Then check the names, not the counts:

```bash
grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
```

All three must be listed. If they are not, the symlinks under `.grok/skills/`
and `.grok/agents/` are missing. On grok 1.0.5 a project plugin registers no
skills and no agents on its own, so those three symlinks are what make the
loop runnable. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) has the
`ln -sfn` commands and the reason.

The counts on the **Plugins** line count directories, so `1 agents` shows even
when two agent files are loaded. Never read them as proof.

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

3. Create the GitHub tickets. This is the only command that opens issues.

   ```bash
   task create-test-tickets
   ```

   Writes `T900` (bug), `T901` (ui), `T902` (feature) if missing, then opens
   a GitHub issue for every draft enhancer ticket, including `T001`.

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

```bash
task poll-forever --
```

That is the seminar answer: `while true: task run; sleep poll_interval`. Press
Ctrl-C to stop. It is not production shape. See SPEC.md for what is.

Grok has no built-in loop skill, so nothing inside the process can schedule
the next poll. A cron job or a scheduled GitHub Actions workflow is the real
answer.

## Debug logging

`grok -p` prints nothing until the whole run finishes, so a run that spawns two
agents looks hung when it is working fine. That is normal. Wait for it.

There is no `debug.log` here. The Claude Code answer gets one from plugin
hooks, and plugin hooks never fire on grok 1.0.5. See
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).

For live progress, run the poll yourself with streaming output:

```bash
grok --always-approve --output-format streaming-json \
  -p "/enhancer-loop --repo ../../work/northwind-field-crm --ticket T001"
```

## Reset a ticket to run it again

Closing the GitHub issue is not a reset. It is the one thing that reliably
breaks the next poll.

The loop finds a ticket's issue through the state file, then the ticket
frontmatter, then a title search. Close the issue and the first two still
point at it, so the loop stops and tells you to reopen it. Delete the
frontmatter line as well and the search finds nothing, so the loop creates a
second issue for the same ticket, and the original's comment history is
stranded on an issue nothing reads.

Reset all three pieces instead:

1. Put the ticket file back to a draft. Keep the issue number.

   ```
   ---
   id: T001
   state: draft
   loop: enhancer
   github_issue: 8
   ---
   ```

2. Drop the loop's memory of the ticket.

   ```bash
   rm -f ../../work/northwind-field-crm/.harness/last-enhancer-T001.json
   ```

3. Reopen the same issue, so its comments survive.

   ```bash
   gh issue reopen 8 --repo <owner>/<repo>
   ```

Same number, same title, new poll. To start completely fresh instead, delete
the ticket file and run `task create-test-tickets`, then let the loop open a
new issue.

## Two poll-loop bugs this skill avoids

Both bugs were in the original Claude Code skill. This port and
`solutions/sol1_enhancer/` fixed them separately and landed on the same
answer, so both skills are correct now. They are worth knowing, because they
are the two ways a poll loop quietly stops being a loop.

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

A third poll on the same simulated comment is the test for the first bug. It
must report "no new comment" and not count as a round.
