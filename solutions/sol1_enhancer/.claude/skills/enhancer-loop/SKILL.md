---
name: enhancer-loop
description: One poll-and-act step for the ticket enhancer. Checks every open draft ticket's GitHub issue for a new comment and acts on it. Use when invoked as /enhancer-loop, typically from `task run` or wrapped in /loop for repeated polling.
---

# The ticket enhancer, one poll-and-act step

You are the orchestrator. You are the only role in this loop that writes the
real ticket file or talks to GitHub. You do this by calling the
`enhancer-judge` and `enhancer-doer` agents and following the steps below,
not by grading or drafting tickets yourself.

This skill runs **one step** and exits. Nothing in this skill schedules the
next check by itself, but you can, using the built-in `loop` skill, in the
Report step below. Whether that actually works depends on how you were
invoked:

- **Interactive or backgrounded session** (someone ran `claude` and typed
  `/enhancer-loop ...`, or an agent view session): calling `loop` really
  works. The CLI process stays alive between iterations, so `loop` re-runs
  this skill on the interval and the polling continues on its own.
- **Headless, via `claude -p`** (this is what `task run` does): the process
  exits the moment this turn ends. Calling `loop` here does nothing useful,
  there is nothing left running to act on it, it is not harmful, just a
  no-op. For this path, repeated polling has to come from outside: a human
  re-running `task run`, a cron job, or a scheduled GitHub Actions workflow.

## Arguments

Parse from the invocation text after `/enhancer-loop`:

- `--repo <path>`: required, the target repo (for example
  `work/northwind-field-crm`).
- `--ticket <id>`: optional. If given, act on only that ticket. If omitted,
  discover every open ticket (step 0).
- `--simulate-comment "<text>"`: dev-only. Use this text in place of
  fetching new issue comments, and skip the GitHub round trip in step 3. Only
  valid together with `--ticket`.

## Step 0: discover open tickets

Skip this step if the invocation named `--ticket`; act on that one ticket
only.

Otherwise, list `<repo>/tickets/*.md`, excluding any `*.ready.md` file, and
read the frontmatter of each. Keep the ones with `state: draft` and
`loop: enhancer`. Run steps 1 to 8 for each one found, in any order.

## Setup, once per run: read config.json

Read `./config.json`, in your current working directory (the folder you
launched `task run` from), created
by the attendee from `config.json.example` in that same directory. It has
`fork_owner` and `repo_name`. Every `gh` command below targets
`--repo <fork_owner>/<repo_name>`. If `./config.json` is missing, stop and
tell the user to copy `config.json.example` to `config.json` and fill in
their GitHub username. Do not ask the user for their username in a way that
expects a reply: this skill runs headlessly and cannot wait for one.

## Steps 1 to 8, per ticket

1. Load the ticket at `<repo>/tickets/<id>.md` and its persisted state from
   `<repo>/.harness/last-enhancer-<id>.json` if that file exists:
   `{github_issue, last_comment_id, round, previous_signature}`. If it does
   not exist, this is the ticket's first poll: `round` starts at 0 and
   `previous_signature` is null.

2. Find or create the ticket's GitHub issue.

   - If the state file already has `github_issue`, use that number.
   - Otherwise search: `gh issue list --repo <owner>/<repo> --search "in:title \"[<id>]\"" --state open --json number`.
   - If none found: create the labels this design needs, once
     (`gh label create enhanced --repo <owner>/<repo> --color fbca04 --force`,
     same for `ready` and `needs-human`, ignore errors if a label already
     exists), then create the issue from the ticket's H1 and body:
     `gh issue create --repo <owner>/<repo> --title "[<id>] <ticket H1>" --body "<ticket body>" --label enhanced`.
     Write the returned issue number into the ticket's frontmatter as
     `github_issue: <number>`, and into the state file.

3. Get the newest comment, if there is one.

   - If this is the ticket's first poll (step 1 found no state file): there
     is no comment yet, and none is needed. A fresh ticket always gets one
     round, so the human has something to react to; skip straight to step
     5 with no comment.
   - Otherwise, if the invocation named `--simulate-comment "<text>"`, treat
     `<text>` as the newest comment and skip the `gh` call below.
   - Otherwise: `gh api repos/<owner>/<repo>/issues/<issue>/comments --jq 'sort_by(.id) | .[-1] | {id, body}'`.
     If its `id` is not newer than `last_comment_id`, there is no new
     comment: stop here for this ticket (no-op, does not count as a round).

4. If the issue already carries `needs-human`, this ticket already reached a
   stable-failure or budget escalation on an earlier poll: stop here, wait
   for a human.

5. Call the `enhancer-judge` agent on the real ticket file, and parse its
   JSON. Run
   `python3 .claude/skills/enhancer-loop/scripts/check_fields.py '<judge json>'`
   to get the authoritative `{kind, missing_fields, ready}`. Do this before
   looking at `LGTM`: a human's `LGTM` is not a substitute for the rubric,
   it can only confirm a ticket the rubric already accepts.

6. Decide what happens next from step 5's `ready` and this round's comment
   (if any), trimmed:

   - `ready` is true and the comment is exactly `LGTM`: set `state: ready`
     and `loop: implementer` in the ticket file (the `loop: implementer`
     module discovers its work the same way this one does, by that field,
     so a ticket left at `loop: enhancer` would never be picked up next).
     Run `gh issue edit <issue> --repo <owner>/<repo> --add-label ready`.
     Keep the `enhanced` label; do not remove it. Delete
     `<repo>/.harness/last-enhancer-<id>.json`. Done with this ticket.
   - `ready` is true and the comment is anything else, or there is none (a
     human commented something other than `LGTM` on an already-complete
     ticket, or this is the first poll and the ticket somehow already meets
     the rubric): post an issue comment saying it looks ready and is
     waiting for `LGTM`, and stop here without calling the Doer.
   - `ready` is false: nothing finalizes here, whatever the comment says,
     `LGTM` included. `LGTM` is never treated as consumed by a red rubric.
     Continue to step 7, the same as any other round, so the Doer gets a
     turn and a later poll can still see this ticket through to ready once
     it clears the rubric.

7. Call the `enhancer-doer` agent with the ticket's current body, its kind,
   its `missing_fields`, and the newest comment's text if there is one (on
   a first poll, tell it plainly there is no comment yet, and to rely on
   its own investigation of the target app). Write its returned
   text to `<repo>/tickets/<id>.enhancer-candidate.md`. Call `enhancer-judge`
   again on that candidate file, and run it through `check_fields.py` the
   same way. Compare candidate `missing_fields` to the current ticket's
   `missing_fields` from step 5:

   - Strict improvement (candidate's missing set is a proper subset):
     copy the candidate over the real ticket file, then update the issue
     body to match it, with the frontmatter stripped (GitHub would render
     the raw `---` YAML block as a stray horizontal rule otherwise):
     `gh issue edit <issue> --repo <owner>/<repo> --body "$(awk '/^---$/{c++; next} c>=2' <repo>/tickets/<id>.md)"`.
     A reviewer needs to see the actual current ticket to judge it, not a
     comment's prose description of a change they cannot verify.
   - Not an improvement: leave the real ticket file, and the issue body,
     untouched.

   Either way, delete the candidate file, then post one issue comment: on
   improvement, what changed and what is still missing (or that it is now
   ready for `LGTM`); otherwise, that the suggestion did not clear the
   rubric for this kind and what is still needed.

8. Compute this round's `missing_fields` signature (the sorted list from
   step 7, the only path that reaches here: step 6's other two branches
   already stopped). Run
   `python3 .claude/skills/enhancer-loop/scripts/check_stop.py '{"round":
   round, "budget": 3, "signature": <this round's signature>,
   "previous_signature": previous_signature}'` to get the authoritative
   `{stop, reason}`. Do not compare the signatures yourself: the same
   reason `check_fields.py` computes `ready` instead of trusting the
   Judge's own claim, a stop condition decided by the skill's own prose
   is a stop condition a model can talk itself past.

   - `stop` is `true`: escalate.
     `gh issue edit <issue> --repo <owner>/<repo> --add-label needs-human`.
     Stop.
   - `stop` is `false`: write the updated state file with
     `round: round + 1` and `previous_signature` set to this round's
     signature. This ticket's step ends here, waiting for the next poll.

## Report, and whether to keep polling

After all tickets are processed, print one short line per ticket: its id and
whether it passed, escalated, or is waiting on the next poll. This is the
only user-facing narration; do not narrate the steps above as you take them.

If every ticket passed or escalated, stop, there is nothing left to poll for.

If at least one ticket is still waiting on the next poll, decide by how you
were invoked:

- **Interactive or backgrounded session**: after printing the report,
  invoke the `loop` skill yourself, with `poll_interval` from `config.json`
  as the interval and the same `/enhancer-loop` invocation (same `--repo`,
  plus `--ticket` if this call named one) as the command to repeat. This
  keeps the polling going, so the human never has to type `/loop`
  themselves.
- **Headless, via `claude -p`** (`task run`): calling `loop` here would be a
  no-op, this process exits right after this turn. Instead, add one line
  naming the command to run again, using `poll_interval` from
  `config.json`: `/loop <poll_interval> task run --`, for someone to run
  interactively, or point at a cron job or scheduled GitHub Actions
  workflow instead.
