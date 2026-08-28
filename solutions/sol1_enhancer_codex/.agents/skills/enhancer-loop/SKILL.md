---
name: enhancer-loop
description: One poll-and-act step for the ticket enhancer. Enhances every open draft ticket that still needs work. A human LGTM is the only comment that marks a ticket ready. Use when invoked as $enhancer-loop, typically from `task run`.
---

# The ticket enhancer, one poll-and-act step

You are the orchestrator. You are the only role in this loop that writes the
real ticket file or talks to GitHub. You do this by running the judge and the
doer as separate read-only processes, through `bin/role.sh`, and following the
steps below. You do not grade or draft tickets yourself.

Run each role with a shell command, never as a skill in this session:

```bash
bin/role.sh enhancer-judge <output-file> "<prompt>"
bin/role.sh enhancer-doer  <output-file> "<prompt>"
```

`bin/role.sh` prints the role's final message on stdout, and writes the same
text to `<output-file>`. Use a path under the target repo's `.harness/` for
that file.

Do not invoke `$enhancer-judge` or `$enhancer-doer` directly. A skill invoked
here runs inside your session and inherits your `workspace-write` sandbox,
which means a judge that could edit the ticket it is grading. The separate
read-only process is the only thing that makes those two roles unable to
write. See `IMPLEMENTATION_NOTES.md`.

Hard rules. A poll that breaks any of these has failed:

- A missing comment does not stop you. Do not fetch comments until
  `check_fields.py` says the ticket is ready.
- The `enhanced` label is not the work. Adding it without rewriting the
  ticket file is a failed poll.
- Seed stubs (a title plus one or two sentences) are never ready. You must
  call the doer and write a better ticket.
- `ready` comes from `check_fields.py`, never from the judge's own claim,
  never from a label, never from a comment other than exact `LGTM`.

This skill runs **one step** and exits. Nothing here schedules the next
check. Repeated polling comes from outside: `task poll-forever`, a cron job,
or a scheduled GitHub Actions workflow.

## Arguments

Parse from the invocation text after `$enhancer-loop`:

- `--repo <path>`: required, the target repo (for example
  `../../work/northwind-field-crm`).
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
loop's own. That is not a stop. There is no `LGTM`. Continue. Enhance the
ticket if the rubric is still red.

## Step 0: discover open tickets

Skip this step if the invocation named `--ticket`; consider that one ticket
only. Skipping discovery does not skip the state rule. Step 1 applies
`state: draft` and `loop: enhancer` to every ticket, however it was chosen.

Otherwise, list `<repo>/tickets/*.md`, excluding any `*.ready.md` file and
any `*.enhancer-candidate.md` file, and read the frontmatter of each. Keep the
ones with `state: draft` and `loop: enhancer`. Run steps 1 to 8 for each one
found, in any order.

A candidate file is a crashed run's leftover. Step 7 deletes it on both
branches, so it only survives an interrupt. It carries `state: draft` and
`loop: enhancer` because the doer is told to keep frontmatter exactly, which
is why the glob has to exclude it by name rather than by field.

## Setup, once per run: read config.json

Read `./config.json`, in your current working directory (the folder you
launched `task run` from), created by the attendee from `config.json.example`
in that same directory. It has `fork_owner` and `repo_name`. Every `gh`
command below targets `--repo <fork_owner>/<repo_name>`. If `./config.json` is
missing, stop and tell the user to copy `config.json.example` to `config.json`
and fill in their GitHub username. Do not ask the user for their username in a
way that expects a reply: this skill runs headlessly and cannot wait for one.

## Steps 1 to 8, per ticket

1. Load the ticket at `<repo>/tickets/<id>.md` and its persisted state from
   `<repo>/.harness/last-enhancer-<id>.json` if that file exists:
   `{github_issue, last_comment_id, round, previous_signature}`. If it does
   not exist, this is the ticket's first poll: `round` starts at 0 and
   `previous_signature` is null.

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
   `task run --` and saw nothing would read the silence as a
   hang.

2. Find the ticket's GitHub issue. Never create one. Creating tickets is
   `task create-test-tickets`. This loop only polls issues that already exist.

   Take the first of these that gives you a number:

   - The state file's `github_issue`.
   - The ticket frontmatter's `github_issue`. Step 2 writes this field, and
     unlike the state file it survives the deletion step 6 performs on the
     `LGTM` pass, which makes it the durable record.
   - A title search across every state:
     `gh issue list --repo <owner>/<repo> --search "in:title \"[<id>]\"" --state all --json number,state`.
     Do not pass `--state open`. A closed issue is still that ticket's issue.

   Then:

   - If the number you now hold belongs to a **closed** issue, stop here for
     this ticket and say so: `issue <number> is closed; reopen it`. Never
     create a second issue for the same title, and do not comment on a closed
     one. `HOW_TO_RUN.md` gives the reset procedure.
   - If none of the three found anything: stop here for this ticket and say
     `<id>: no GitHub issue; run task create-test-tickets`. Do not create
     labels. Do not call `gh issue create`.

   If you found a number, write it into the ticket's frontmatter as
   `github_issue: <number>` and into the state file before you go on.
   Persist it even on a branch that stops early, such as step 6's "ready,
   waiting for `LGTM`". Write it on the search path too. A state file that
   appears only on some later poll leaves every later poll looking like a
   first poll. That must not delay enhancement. Comments are only for `LGTM`.

3. Skip comments for now. Go to step 4. You will look for `LGTM` only after
   `check_fields.py` says ready. Fetching comments here is how earlier runs
   labeled the issue and then stopped.

4. If the issue already carries `needs-human`, this ticket already reached a
   stable-failure or budget escalation on an earlier poll: stop here, wait
   for a human.

5. Grade the real ticket. Run

   ```bash
   bin/role.sh enhancer-judge <repo>/.harness/judge-<id>.json "Grade the ticket at <absolute path to <repo>/tickets/<id>.md>"
   ```

   Pass the ticket path as an absolute path. The judge's process starts in
   this folder, not in the target repo. Parse its JSON, then run
   `python3 .agents/skills/enhancer-loop/scripts/check_fields.py '<judge json>'`
   to get the authoritative `{kind, missing_fields, ready}`. Do this before
   looking at `LGTM`: a human's `LGTM` is not a substitute for the rubric,
      it can only confirm a ticket the rubric already accepts.

   Do not add the `enhanced` label here.

6. Decide what happens next from step 5's `ready` and this round's comment
   (if any), trimmed:

   - `ready` is true and the comment is exactly `LGTM`: set `state: ready`
     and `loop: implementer` in the ticket file (the `loop: implementer`
     module discovers its work the same way this one does, by that field,
     so a ticket left at `loop: enhancer` would never be picked up next).
     Run `gh issue edit <issue> --repo <owner>/<repo> --add-label ready`.
     Keep the `enhanced` label; do not remove it. Delete
     `<repo>/.harness/last-enhancer-<id>.json`. Done with this ticket.
   - `ready` is true and the comment is not `LGTM` (or there is none): do not
     call the Doer. If you have not already asked for `LGTM` on this ticket,
     post that it meets the rubric and is waiting for `LGTM`, with the marker.
     Stop.
   - `ready` is false: go to step 7 now. The four seed tickets in this demo
     are stubs. They are not ready. Do not look at comments. Do not stop
     because the issue already has `enhanced`.

7. Draft a candidate, judge it, and keep it only if it is better. Run

   ```bash
   bin/role.sh enhancer-doer <repo>/.harness/doer-<id>.md "<the ticket's current body, its kind, its missing_fields. Tell it there is no comment to follow.>"
   ```

   Tell the doer there is no comment to follow. It investigates the target app. Copy the file
   `bin/role.sh` wrote to `<repo>/tickets/<id>.enhancer-candidate.md`. Grade
   that candidate the same way as step 5:

   ```bash
   bin/role.sh enhancer-judge <repo>/.harness/judge-candidate-<id>.json "Grade the ticket at <absolute path to the candidate file>"
   ```

   Run it through `check_fields.py` the same way. Compare candidate
   `missing_fields` to the current ticket's `missing_fields` from step 5:

   - Strict improvement (candidate's missing set is a proper subset):
     copy the candidate over the real ticket file, then update the issue
     body to match it, with the frontmatter stripped (GitHub would render
     the raw `---` YAML block as a stray horizontal rule otherwise):
     `gh issue edit <issue> --repo <owner>/<repo> --body "$(awk '/^---$/{c++; next} c>=2' <repo>/tickets/<id>.md)"`.
     Then, and only then:
     `gh issue edit <issue> --repo <owner>/<repo> --add-label enhanced`.
     A reviewer needs to see the actual current ticket to judge it.
   - Not an improvement: leave the real ticket file, and the issue body,
     untouched. Do not add `enhanced` for a no-op.

   Either way, delete the candidate file, then post one issue comment with
   `gh issue comment <issue> --repo <owner>/<repo> --body "<text>"`, ending
   `<text>` with the marker line: on improvement, what changed and what is
   still missing (or that it is now ready for `LGTM`); otherwise, that the
   suggestion did not clear the rubric for this kind and what is still
   needed.

8. Compute this round's `missing_fields` signature (the sorted list from
   step 7, the only path that reaches here: step 6's other two branches
   already stopped). Run
   `python3 .agents/skills/enhancer-loop/scripts/check_stop.py '{"round":
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
     signature. If the ticket is now complete, set `last_comment_id` to
     `asked-lgtm`. This ticket's step ends here, waiting for `LGTM` or the
     next enhance round.

## Report

After all tickets are processed, print one short line per ticket: its id and
whether it passed, escalated, or is waiting on the next poll. This is the
only user-facing narration; do not narrate the steps above as you take them.

If at least one ticket is still waiting on the next poll, add one line naming
how to run the next one: `task poll-forever --`, a cron job, or a scheduled
GitHub Actions workflow. `codex exec` exits when this turn ends, so nothing
in this process can schedule it.
