---
name: enhancer-loop
description: One poll-and-act step for the ticket enhancer. Checks every open draft ticket's GitHub issue for a new comment and acts on it. Use when invoked as /enhancer-loop, typically from `task run`.
---

# The ticket enhancer, one poll-and-act step

You are the orchestrator. You are the only role in this loop that writes the
real ticket file or talks to GitHub. You do this by spawning the
`enhancer-judge` and `enhancer-doer` agents and following the steps below,
not by grading or drafting tickets yourself.

Spawn both with the `spawn_subagent` tool, passing the agent's name as
`subagent_type`. They come from this plugin. Neither holds a write tool, a
shell tool, or an MCP tool, so neither can act on what it decides.

This skill runs **one step** and exits. Nothing here schedules the next
check. Grok has no built-in loop skill, so repeated polling comes from
outside this process: `task poll-forever`, a cron job, or a scheduled GitHub
Actions workflow.

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

Otherwise, list `<repo>/tickets/*.md`, excluding any `*.ready.md` file and
any `*.enhancer-candidate.md` file. A candidate file is scratch written by
step 7, and a run that dies before deleting one leaves it behind. Left in
scope it gets discovered as a ticket of its own and groomed as if it were
real work.

Read the frontmatter of each file that survives that filter. Keep the ones
with `state: draft` and `loop: enhancer`. Run steps 1 to 8 for each one
found, in any order.

## Setup, once per run: read config.json

Read `./config.json`, in your current working directory (the folder you
launched `task run` from), created by the attendee from
`config.json.example` in that same directory. It has `fork_owner` and
`repo_name`. Every `gh` command below targets
`--repo <fork_owner>/<repo_name>`. If `./config.json` is missing, stop and
tell the user to copy `config.json.example` to `config.json` and fill in
their GitHub username. Do not ask the user for their username in a way that
expects a reply: this skill runs headlessly and cannot wait for one.

## Steps 1 to 8, per ticket

1. Load the ticket at `<repo>/tickets/<id>.md` and its persisted state from
   `<repo>/.harness/last-enhancer-<id>.json` if that file exists:
   `{github_issue, last_comment_id, round, previous_signature}`. If it does
   not exist, this is the ticket's first poll: `round` starts at 0 and both
   `previous_signature` and `last_comment_id` are null.

2. Find or create the ticket's GitHub issue.

   - If the state file already has `github_issue`, use that number.
   - Otherwise search: `gh issue list --repo <owner>/<repo> --search "in:title \"[<id>]\"" --state open --json number`.
   - If none found: create the labels this design needs, once
     (`gh label create enhanced --repo <owner>/<repo> --color fbca04 --force`,
     same for `ready` and `needs-human`, ignore errors if a label already
     exists), then create the issue from the ticket's H1 and body:
     `gh issue create --repo <owner>/<repo> --title "[<id>] <ticket H1>" --body "<ticket body>" --label enhanced`.

   However you arrived at the number, found by search or freshly created,
   write it into the ticket's frontmatter as `github_issue: <number>` and
   into the state file before you go on. Persist it even on a branch that
   stops early, such as step 6's "ready, waiting for `LGTM`".

   Write it on the search path too, not only on the create path. A state
   file that appears only when this loop creates the issue leaves every
   later poll looking like a first poll, and step 3 skips the comment fetch
   on a first poll. A ticket whose issue already existed would then never
   read `LGTM`, and could never reach ready.

3. Get the newest comment, if there is one, and compute its id.

   - If this is the ticket's first poll (step 1 found no state file): there
     is no comment yet, and none is needed. A fresh ticket always gets one
     round, so the human has something to react to; skip straight to step
     5 with no comment. Its id is null.
   - Otherwise, if the invocation named `--simulate-comment "<text>"`, treat
     `<text>` as the newest comment and skip the `gh` call below. A simulated
     comment has no real id, so derive one:
     `printf '%s' "<text>" | shasum | cut -c1-12` and use `sim:<that hash>`
     as its id. The same simulated text therefore keeps the same id across
     polls, which is what makes a repeated `--simulate-comment` behave like
     the repeated real comment it stands in for.
   - Otherwise: `gh api repos/<owner>/<repo>/issues/<issue>/comments --jq 'sort_by(.id) | .[-1] | {id, body}'`.
   - Either way, compare the id you now hold to `last_comment_id` from step
     1. If they are equal, there is no new comment: stop here for this
     ticket (no-op, does not count as a round).

4. If the issue already carries `needs-human`, this ticket already reached a
   stable-failure or budget escalation on an earlier poll: stop here, wait
   for a human.

5. Spawn the `enhancer-judge` agent on the real ticket file, and parse its
   JSON. Run
   `python3 .grok/plugins/ticket-enhancer/skills/enhancer-loop/scripts/check_fields.py '<judge json>'`
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
     waiting for `LGTM`, then go to step 8 to record this poll's
     `last_comment_id`. Do not call the Doer.
   - `ready` is false: nothing finalizes here, whatever the comment says,
     `LGTM` included. `LGTM` is never treated as consumed by a red rubric.
     Continue to step 7, the same as any other round, so the Doer gets a
     turn and a later poll can still see this ticket through to ready once
     it clears the rubric.

7. Spawn the `enhancer-doer` agent with the ticket's current body, its kind,
   its `missing_fields`, and the newest comment's text if there is one (on
   a first poll, tell it plainly there is no comment yet, and to rely on
   its own investigation of the target app). Write its returned
   text to `<repo>/tickets/<id>.enhancer-candidate.md`. Spawn
   `enhancer-judge` again on that candidate file, and run it through
   `check_fields.py` the same way. Compare candidate `missing_fields` to the
   current ticket's `missing_fields` from step 5:

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

8. Record this poll, and check the exits.

   If you arrived here from step 6's second branch (ready, no `LGTM`), there
   is no new signature to compare. Write the state file with the same
   `round` and `previous_signature` you loaded, and `last_comment_id` set to
   step 3's id. Stop.

   Otherwise compute this round's `missing_fields` signature (the sorted
   list from step 7). Run
   `python3 .grok/plugins/ticket-enhancer/skills/enhancer-loop/scripts/check_stop.py '{"round":
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
     `round: round + 1`, `previous_signature` set to this round's
     signature, and `last_comment_id` set to step 3's id. This ticket's step
     ends here, waiting for the next poll.

   Always write `last_comment_id`. Step 3 compares against it to decide
   whether a poll has anything to do, so a state file that omits it makes
   every later poll treat the same comment as new and re-run the same round
   forever.

## Report

After all tickets are processed, print one short line per ticket: its id and
whether it passed, escalated, or is waiting on the next poll. This is the
only user-facing narration; do not narrate the steps above as you take them.

If at least one ticket is still waiting on the next poll, add one line naming
how to poll again: `task poll-forever --` for the seminar, or a cron job or
scheduled GitHub Actions workflow for real use.
