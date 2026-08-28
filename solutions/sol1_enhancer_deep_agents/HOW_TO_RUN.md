# How to run this solution

Everything here runs from `solutions/sol1_enhancer_deep_agents/`, standalone. No
task in this folder depends on the repo root or on any other folder outside
it.

You need `python3`, `gh`, `jq`, `task`, `deepagents>=0.7`, and an
`ANTHROPIC_API_KEY`.

This is the take-home runtime. Saturday live path is `solutions/sol1_enhancer`.
Do not copy these harness fences into that folder.

Python is the harness. The model drafts and grades. It does not write files
and it does not run `/enhancer-loop`.

## One-time setup

1. Copy the config template and fill in your GitHub username:

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval` (`"10m"` by default). Use a
   short one (`"1m"`, `"30s"`) while testing.

2. Put the API key in the repo root `.env`. Task loads that file first, then
   this folder's `.env`. The first file that defines a variable wins.

   ```bash
   # in the lab repo root
   echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
   ```

3. Install the runtime.

   ```bash
   task setup
   ```

   This creates `.venv` in this folder and installs `deepagents` plus pytest.
   `task run` uses that virtual environment automatically; you do not need to
   activate it manually.

4. Clone your fork:

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

   Default `TARGET` is that path, not `northwind-field-crm-test`.

5. Create tickets with the seed task, or file one in the GitHub UI.

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

`task run` calls `python3 loop.py --once --repo <target>`. Extra flags after
`--` go to `loop.py`.

It prints one line per ticket: `passed`, `escalated`, or `waiting`.

Cap it while you are developing. A first poll starts three model calls
(judge, doer, judge again):

```bash
timeout 420 task run --
```

Work one ticket:

```bash
task run -- --ticket T001
```

To work one ticket without waiting on a real comment, pass your own:

```bash
task run -- --ticket T001 --simulate-comment LGTM
```

`--simulate-comment` needs `--ticket`.

## Repeated polling

This loop runs one step and exits; something else has to call it again.

For the seminar, run it forever in one terminal:

```bash
task poll-forever --
```

`while true: task run; sleep poll_interval`, nothing more. It never stops
on its own. `Ctrl-C` when you are done. This is a seminar stand-in, not
production shape, see `SPEC.md`.

## Scripts you can run without a model

```bash
task table
task checks
task test
```

`task table` prints the role table. The judge must print `no` in the writes
column. If it prints `yes`, stop. `task test` is the pytest suite. None of
these need the SDK, a key, or a clone.

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

Same number, same title, new poll. To start completely fresh instead, run
the three commands in "Retest from scratch". `task run` never opens an issue.

Two messages send you back to this section:

- `issue N is closed; reopen it`. Somebody closed the issue for a ticket that
  is still a draft. Reopen it, or reset the ticket properly.
- `<id>: no GitHub issue; run task create-test-tickets`. The markdown file
  exists, but no issue does. Run the seed task. Do not expect `task run` to
  open one.
- `T901: already ready / implementer, skipping`. The ticket is finished.
  Reset it if you meant to run it again.
