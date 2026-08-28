---
name: enhancer-loop
description: One poll-and-act step for the ticket enhancer. Checks every open draft ticket's GitHub issue for a new comment and acts on it. Use when invoked as enhancer-loop, typically from `task run` or `opencode run --command enhancer-loop`.
---

# The ticket enhancer, one poll-and-act step

You are the orchestrator. You are the only role in this loop that writes the
real ticket file or talks to GitHub. You do this by calling the
`enhancer-judge` and `enhancer-doer` subagents and following the steps below,
not by grading or drafting tickets yourself.

Call those two roles through the Task tool:

- `subagent_type: enhancer-judge` to grade one file. Parse the JSON it
  returns. It holds `edit: deny` and `bash: deny`. Do not grade the ticket
  yourself.
- `subagent_type: enhancer-doer` to draft a candidate body. Its entire
  reply is markdown text. It holds `edit: deny` and `bash: deny`. Do not
  write the draft yourself except to copy that text into the candidate file.

This skill runs **one step** and exits. Nothing in this skill schedules the
next check by itself. Repeated polling has to come from outside: a human
re-running `task run`, `task poll-forever`, a cron job, or a scheduled
GitHub Actions workflow.

Headless `opencode run` exits the moment this turn ends. Do not wait for
another poll inside this process.

## Arguments

Parse from the invocation text after `enhancer-loop`:

- `--repo <path>`: required, the target repo (for example
  `work/northwind-field-crm`).
- `--ticket <id>`: optional. If given, act on only that ticket. If omitted,
  discover every open ticket (step 0).
- `--simulate-comment "<text>"`: dev-only. Use this text in place of
  fetching new issue comments, and skip the GitHub round trip in step 3. Only
  valid together with `--ticket`.

## The comment marker

Every comment this loop posts ends with this exact line:

```
<!-- enhancer-loop -->
```

GitHub renders an HTML comment as nothing, so a human never sees it.

Step 3 uses the marker to skip this loop's own replies when it looks for the
newest comment. Without it the loop reads its own last reply as the newest
comment and answers it again, once per poll, forever. Storing
`last_comment_id` does not help, because the reply genuinely carries a newer
id.

Do not filter by comment author instead. The loop runs as the attendee's own
`gh` account, so an author filter would also drop their `LGTM`, the one
comment this loop must never miss.

If step 3's query prints nothing, every comment on the issue is one of this
loop's own. Treat that exactly like no new comment.

## Step 0: discover open tickets

Skip this step if the invocation named `--ticket`; act on that one ticket
only.

Otherwise, list `<repo>/tickets/*.md`, excluding any `*.ready.md` file and
any `*.enhancer-candidate.md` file, and read the frontmatter of each. Keep
the ones with `state: draft` and `loop: enhancer`. Run steps 1 to 8 for each
one found, in any order.

A candidate is the Doer's unjudged draft from step 7, and step 7 deletes it
again. A run that dies in between leaves one behind, carrying the real
ticket's `state: draft` and `loop: enhancer` frontmatter. A glob that does
not exclude it hands the next run a second copy of a ticket that no Judge
ever accepted.

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
   `previous_signature` is null. `last_comment_id` stays null, or absent,
   until some poll actually uses a comment; treat null and absent the same.

   Then check the ticket's own frontmatter before you go any further. Unless
   it reads `state: draft` **and** `loop: enhancer`, this ticket is not this
   loop's work. Print one line naming the ticket and the state you found, for
   example `T900: already ready / implementer, skipping`, and stop here. Do
   not create an issue, do not post a comment, and do not write a state file.
   `--ticket <id>` names a ticket to consider, not a reason to skip the check.

2. Find or create the ticket's GitHub issue.

   Take the first of these that gives you a number:

   - The state file's `github_issue`.
   - The ticket frontmatter's `github_issue`. Step 2 writes this field, and
     unlike the state file it survives the deletion step 6 performs on the
     `LGTM` pass, which makes it the durable record.
   - A title search across every state:
     `gh issue list --repo <owner>/<repo> --search "in:title \"[<id>]\"" --state all --json number,state`.
     Do not pass `--state open`. A closed issue is still that ticket's issue.
   - If the number you now hold belongs to a **closed** issue, stop here for
     this ticket and say so: `issue <number> is closed; reopen it`. Never
     create a second issue for the same title, and do not comment on a closed
     one.
   - Only when none of the three found anything: create the labels this design
     needs, once
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

3. Get the newest comment, if there is one. Whichever branch below applies,
   note that comment's id: step 6 and step 8 write it back into the state
   file, and a poll that never records the id it acted on will act on the
   same comment again on the next poll, and on every poll after that.

   - If the invocation named `--simulate-comment "<text>"`: there is no
     GitHub comment and so no GitHub id. The id is the literal `sim:`
     followed by the exact `<text>`, so the same simulated text always
     produces the same id. If that id equals `last_comment_id`, this poll
     has no new comment: stop here for this ticket (no-op, does not count as
     a round). Otherwise treat `<text>` as the newest comment, and skip the
     `gh` call below.
   - Otherwise, if this is the ticket's first poll (step 1 found no state
     file): there is no comment yet, and none is needed. A fresh ticket
     always gets one round, so the human has something to react to; skip
     straight to step 5 with no comment and no comment id.
   - Otherwise: `gh api repos/<owner>/<repo>/issues/<issue>/comments --jq '[.[] | select((.body // "") | contains("<!-- enhancer-loop -->") | not)] | sort_by(.id) | .[-1] // empty | {id, body}'`.
     The id is that comment's numeric `id`. If it is not newer than
     `last_comment_id`, there is no new comment: stop here for this ticket
     (no-op, does not count as a round).

4. If the issue already carries `needs-human`, this ticket already reached a
   stable-failure or budget escalation on an earlier poll: stop here, wait
   for a human.

5. Call the `enhancer-judge` subagent on the real ticket file, and parse its
   JSON. Run
   `python3 .opencode/skills/enhancer-loop/scripts/check_fields.py '<judge json>'`
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
     waiting for `LGTM`, ending the body with the marker line. Write the
     state file with `last_comment_id` set to step 3's comment id, keeping
     `round` and `previous_signature` as step 1 loaded them, then stop here
     without calling the Doer. This branch never reaches step 8, so it has
     to record the id itself, or the same comment draws the same reply on
     every later poll.
   - `ready` is false: nothing finalizes here, whatever the comment says,
     `LGTM` included. `LGTM` is never treated as consumed by a red rubric.
     Continue to step 7, the same as any other round, so the Doer gets a
     turn and a later poll can still see this ticket through to ready once
     it clears the rubric.

7. Call the `enhancer-doer` subagent with the ticket's current body, its
   kind, its `missing_fields`, and the newest comment's text if there is one
   (on a first poll, tell it plainly there is no comment yet, and to rely on
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

   Either way, delete the candidate file, then post one issue comment,
   ending its body with the marker line: on improvement, what changed and
   what is still missing (or that it is now ready for `LGTM`); otherwise,
   that the suggestion did not clear the rubric for this kind and what is
   still needed.

8. Compute this round's `missing_fields` signature (the sorted list from
   step 7, the only path that reaches here: step 6's other two branches
   already stopped). Run
   `python3 .opencode/skills/enhancer-loop/scripts/check_stop.py '{"round":
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
     signature, and `last_comment_id` set to step 3's comment id, so the
     next poll can tell that comment apart from a new one. If this poll used
     no comment at all (the first-poll branch of step 3), leave
     `last_comment_id` null or omit it. Never invent an id for a comment
     that does not exist. This ticket's step ends here, waiting for the next
     poll.

## Report, and whether to keep polling

After all tickets are processed, print one short line per ticket: its id and
whether it passed, escalated, or is waiting on the next poll. This is the
only user-facing narration; do not narrate the steps above as you take them.

If every ticket passed or escalated, stop, there is nothing left to poll for.

If at least one ticket is still waiting on the next poll, this process is
about to exit. Print one line naming the command to run again, using
`poll_interval` from `config.json`: `task poll-forever --`, or
`task run --` on a cron job or scheduled GitHub Actions workflow. Do not
try to sleep and poll again inside this process.
