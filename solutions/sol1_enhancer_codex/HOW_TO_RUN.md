# How to run the Codex ticket enhancer

Every command runs from this folder. Read [SPEC.md](SPEC.md) for the design,
and [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) before you change how
a role is launched.

You need `codex`, `gh`, `jq`, `task`, and `python3`.

## Set up, once

1. Copy the config and fill in your GitHub username.

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval`, which defaults to `"10m"`. Use
   `"1m"` or `"30s"` while you test.

2. Clone your fork.

   ```bash
   task clone
   ```

   The clone lands in `../../work/northwind-field-crm`, a shared folder
   outside this tree, on purpose. It is gitignored.

   If GitHub refuses your fork because you already have a repo by that name,
   create an empty one and push the upstream into it:

   ```bash
   gh repo create <owner>/<name> --public
   git clone https://github.com/RichardHightower/northwind-field-crm.git
   cd northwind-field-crm
   git remote set-url origin https://github.com/<owner>/<name>.git
   git push -u origin main
   ```

   The loop only needs a repo with the same `tickets/` layout.

3. Check the orchestrator's sandbox is real.

   ```bash
   task fence-check
   ```

   See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) if it reports
   `TRUSTED`.

4. Create the GitHub tickets. This is the only command that opens issues.

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

## Expect five minutes, not one

One poll starts three model processes: judge, doer, judge again. Each child
takes 12 to 25 seconds, and the orchestrator has its own turns around them.
A full round that promotes a candidate runs about four minutes here.

Always put a cap on it while you are developing:

```bash
timeout 420 task run --
```

A run that produces no output for minutes is usually a hang, not slow
thinking. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) lists the two
that look identical from outside.

## Keep polling

```bash
task poll-forever --
```

That loops `task run` on `poll_interval` until you press Ctrl-C. It never
stops on its own, even when every ticket has passed. The loop stands in for
a scheduler, so running forever is the point.

## Watch what it is doing

`codex exec` prints its own progress as it goes, so a run is not silent. The
noisy parts are worth knowing:

- `bin/role.sh` sends its child's progress to `/dev/null` and prints only the
  role's final message. A judge call therefore looks like a 20-second pause
  followed by one line of JSON.
- Each child also writes its final message to a file under
  `<repo>/.harness/`. Read `judge-<id>.json` or `doer-<id>.md` after a run to
  see exactly what a role returned.

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
the ticket file and run `task create-test-tickets`, then let the loop open a
new issue.

## When something goes wrong

| What you see | Likely cause |
|---|---|
| No output at all, forever | A `codex exec` with stdin open. See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). |
| A child dies in under a second | The parent cannot write `$CODEX_HOME`. Check `--add-dir "$HOME/.codex"` is on the `run` task. |
| A judge that never answers | Recursion. A role started another role. |
| Every `gh` call fails | The network is off. `workspace-write` disables it unless `sandbox_workspace_write.network_access=true` is set. |
| A leftover `*.enhancer-candidate.md` | A run was interrupted mid-round. Delete it. Ticket discovery already skips it. |
| `issue N is closed; reopen it` | Somebody closed the issue for a ticket that is still a draft. Reopen it, or reset the ticket properly. See the reset section above. |
| `already ready / implementer, skipping` | The ticket is finished. `--ticket` names a ticket, it does not override that. Reset it if you meant to run it again. |
