# How to run this

Everything runs from `solutions/sol1_enhancer_copilot_cli/`. This folder is
standalone.

## Step zero: confirm the three names

Copilot CLI loads project skills from `.github/skills/` and custom agents from
`.github/agents/`, from the directory it starts in.
`task run` sets `dir:` to this folder for that reason.

```bash
task inspect
```

That checks the plugin name, the skill name, the two agent allowlists, and
the three registration symlinks. If it fails, recreate the links:

```bash
mkdir -p .github/skills .github/agents
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop .github/skills/enhancer-loop
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-judge.agent.md .github/agents/enhancer-judge.agent.md
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-doer.agent.md .github/agents/enhancer-doer.agent.md
```

Headless check:

```bash
copilot skill list
```

`enhancer-loop` must be listed. If it is not, you started Copilot from the
wrong directory.

Interactive: `copilot` in this folder, then type `/enhancer-loop`.

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

3. Create tickets with the seed task, or file one in the GitHub UI.

   ```bash
   task create-test-tickets
   ```

   Writes `T900` (bug), `T901` (ui), `T902` (feature) if missing, then opens
   a GitHub issue for every draft enhancer ticket, including `T001`.

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

Interactive instead of headless:

```bash
copilot
# then:
/enhancer-loop --repo ../../work/northwind-field-crm
```

## Repeated polling

```bash
task poll-forever --
```

That is the seminar answer: `while true: task run; sleep poll_interval`. Press
Ctrl-C to stop. It is not production shape. See SPEC.md for what is.

Copilot CLI has no built-in loop skill, so nothing inside the process can
schedule the next poll. A cron job or a scheduled GitHub Actions workflow is
the real answer.

## Debug logging

Set `"debug": true` in `config.json`. Plugin hooks under
`com.github.copilot/hooks/hooks.json` append one line per tool call to
`debug.log` in this folder when the host runs them.

`task run` already uses Copilot CLI, which streams as it works.

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
