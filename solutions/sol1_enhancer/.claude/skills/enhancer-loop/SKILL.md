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
- `--ticket <id>`: optional. If given, consider only that ticket. If omitted,
  discover every open ticket (step 0). This flag chooses which ticket to look
  at, and nothing more. Step 1 still requires `state: draft` and
  `loop: enhancer`, so naming a finished ticket skips it rather than running
  it again.
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

Skip this step if the invocation named `--ticket`; consider that one ticket
only. Skipping discovery does not skip the state rule. Step 1 applies
`state: draft` and `loop: enhancer` to every ticket, however it was chosen.

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

   This rule holds whichever path chose the ticket. Step 0 applies it to
   every ticket it discovers, and `--ticket <id>` names a ticket to consider,
   not a reason to skip the check. Without it, a finished ticket gets a
   second run as though it were a fresh draft.

   Say it out loud rather than exiting quietly. Somebody who just typed
   `task run -- --ticket T900` and saw nothing would read the silence as a
   hang.

2. Find or create the ticket's GitHub issue.

   Take the first of these that gives you a number:

   - The state file's `github_issue`.
   - The ticket frontmatter's `github_issue`. Step 2 writes this field, and
     unlike the state file it survives the deletion step 6 performs on the
     `LGTM` pass, which makes it the durable record.
   - A title search across every state:
     `gh issue list --repo <owner>/<repo> --search "in:title \"[<id>]\"" --state all --json number,state`.
     Do not pass `--state open`. A closed issue is still that ticket's issue,
     and searching only open ones is what makes the loop create a second issue
     for a title that already has one. The search also indexes lazily and can
     miss an issue created moments ago, which is why it ranks below the two
     recorded sources rather than above them.
   - If the number you now hold belongs to a **closed** issue, stop here for
     this ticket and say so: `issue <number> is closed; reopen it`. Never
     create a second issue for the same title, and do not comment on a closed
     one. You only reach this when somebody closed the issue for a ticket
     that is still a draft, which is not how you reset a ticket. `HOW_TO_RUN.md`
     gives the procedure that is.
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
     waiting for `LGTM`, ending the body with the marker line. Write the
     state file with `last_comment_id` set to step 3's comment id, keeping
     `round` and `previous_signature` as step 1 loaded them, then stop here without calling the Doer. This branch never
     reaches step 8, so it has to record the id itself, or the same comment
     draws the same reply on every later poll.
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

   Either way, delete the candidate file, then post one issue comment,
   ending its body with the marker line: on improvement, what changed and
   what is still missing (or that it is now ready for `LGTM`); otherwise,
   that the suggestion did not clear the rubric for this kind and what is
   still needed.

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
