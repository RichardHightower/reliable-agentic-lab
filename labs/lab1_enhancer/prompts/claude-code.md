# Prompt for claude code

This lab is a Claude Code plugin: two agents and one skill, under
`.claude/` in this folder. Build it with the four prompts below, one at a
time, pasted into an interactive `claude` session run from this folder.
Verify after each one, then do the last prompt, which compares your result
against the answer.

```bash
cd labs/lab1_enhancer
claude
```

---

## Prompt 1: the judge agent

Paste this first.

```
Create .claude/agents/enhancer-judge.md, a subagent named enhancer-judge.

Its job: read one ticket file (a path I give it) and report which required
fields, for the ticket's kind, have real content. Give it Read, Grep, and
Glob tools only, no write tool of any kind: a judge that could edit the
ticket could grade itself, so it must not be able to.

The required fields, by kind:
- bug: title (8+ characters), steps, expected, actual, environment
- feature: problem, proposal, value, criteria (2+ acceptance criteria a
  test could fail, not just one)
- ui: same as feature, plus wireframe (a fenced diagram or ASCII mockup is
  enough)

Classify the kind from the title and body: words like broken, crash, error,
fails, or regression mean bug; words like form, page, button, screen, or
layout mean ui; otherwise feature.

Its entire final message must be one JSON object and nothing else:
{"kind": "...", "present_fields": [...]}. List only fields it is confident
are genuinely present with real content, not a bare heading.
```

## Prompt 2: the doer agent

```
Create .claude/agents/enhancer-doer.md, a subagent named enhancer-doer.

Its job: given a ticket's current body, its kind, its missing fields, and
(if there is one) the latest comment on its GitHub issue, draft a full
replacement ticket body with every required field filled in. Give it Read,
Grep, and Glob tools only, no write tool: its draft must be judged before it
can reach the real ticket file, so it must return the draft as its final
message's text, not write it to a file itself.

It should investigate before it invents: read the target app's code (under
app/ in the target repo) for how similar fields already behave, and use any
GitHub comment as the strongest signal for what a human actually wants.
Where neither settles a field, it should still fill it with the most
reasonable value a careful engineer would propose, stated plainly, rather
than leave it blank: a missing field blocks the ticket, a stated guess does
not.
```

## Prompt 3: the deterministic check

```
Create .claude/skills/enhancer-loop/scripts/check_fields.py.

It reads a JSON object shaped like {"kind": "...", "present_fields": [...]}
(as a CLI argument or on stdin) and prints {"kind", "present_fields",
"missing_fields", "ready"}. It computes missing_fields itself, from a fixed
table of required fields per kind (the same table from prompt 1), by
subtracting present_fields. It does not trust any missing_fields the caller
might also send: the whole point is that this one small piece of the judge
needs no model and should never be fooled by one.

Include a --demo mode with a few assert statements I can run to check it
works.
```

Run it: `python3 .claude/skills/enhancer-loop/scripts/check_fields.py --demo`

## Prompt 3b: the deterministic stop

`ready` is one exit, decided in code by prompt 3. The other two, budget
spent and a stable failure, are not: nothing yet stops the skill from
trusting its own read of "did the signature repeat" instead of computing
it.

```
Create .claude/skills/enhancer-loop/scripts/check_stop.py.

It reads a JSON object shaped like {"round": int, "budget": int,
"signature": [...], "previous_signature": [...] or null} (CLI argument or
stdin) and prints {"stop": bool, "reason": str or null}. stop is true when
signature equals previous_signature (not the first round), or when round +
1 reaches budget. It computes this itself; it does not trust a caller's own
claim about whether the signatures matched.

Include a --demo mode with a few assert statements I can run to check it
works.
```

Run it: `python3 .claude/skills/enhancer-loop/scripts/check_stop.py --demo`

## Prompt 4: the orchestrator skill

This is the real design work. Describe the shape, let Claude Code write the
steps.

```
Create .claude/skills/enhancer-loop/SKILL.md, invoked as /enhancer-loop
--repo <path> [--ticket <id>] [--simulate-comment "<text>"].

It is the orchestrator: the only role that writes the real ticket file or
talks to GitHub, by calling the enhancer-judge and enhancer-doer agents,
not by grading or drafting tickets itself. It runs one poll-and-act step and
exits; it does not loop internally. Repeated polling, over time, is /loop's
job, external to this skill.

Read config.json in your current working directory (task run always runs
this from the folder that holds config.json) for {fork_owner, repo_name};
every gh call targets that repo.

Without --ticket, discover every tickets/*.md in the target repo (excluding
both *.ready.md and *.enhancer-candidate.md) whose frontmatter has
state: draft and loop: enhancer, and run the step below for each. A
candidate is the doer's unjudged draft from step 7, which a crashed run can
leave behind carrying the real ticket's draft frontmatter; it is not a
ticket.

Apply state: draft and loop: enhancer to every ticket, however it was
chosen. --ticket <id> names a ticket to consider, it does not excuse the
check, so a finished ticket is skipped rather than run a second time as
though it were a fresh draft. Skip it out loud, on one line naming the
ticket and the state you found, so nobody reads the silence as a hang.

Persist state per ticket in .harness/last-enhancer-<id>.json:
{github_issue, last_comment_id, round, previous_signature}.

The step, per ticket:
1. Find the ticket's GitHub issue. Never create one. Creating tickets is
   task create-test-tickets. Take the first of these that gives you a
   number: the state file's github_issue, then the ticket frontmatter's
   github_issue, then a title search on the "[<id>]" prefix across all
   states. Do not search --state open. If the issue is closed, stop and say
   so. If none of the three found anything, stop and say to run
   task create-test-tickets. Do not call gh issue create. However you got
   the number, write it into both the state file and the ticket's
   frontmatter as github_issue before you go on.
2. Look at the newest human comment only for exact LGTM. Comments never
   start an enhance round. A missing comment never stops one. Add the
   enhanced label the first time this loop touches the ticket. Create-test-tickets
   must not add it.
3. Issue already carries "needs-human": stop, wait for a person.
4. Judge the current ticket (enhancer-judge, then check_fields.py) to get
   this round's kind, missing_fields, and ready. LGTM must never skip this:
   a human blessing a two-line draft is not the same as the rubric passing.
5. Comment is exactly "LGTM" and the ticket is already ready: set
   state: ready in the ticket, swap the "enhanced" label for "ready",
   delete the state file, done. LGTM on a ticket that is not yet ready
   finalizes nothing, the comment is not consumed; fall through to step 7
   like any other comment, so the next poll can still see this ticket
   through to ready.
6. Ticket is already ready but the comment was something other than LGTM
   (or there was none): post a comment saying it looks ready and is
   waiting for LGTM, stop, do not call the doer.
7. Otherwise: call enhancer-doer with the newest comment. Judge its
   candidate draft the same way. Only if the candidate's missing_fields is a
   strict improvement, replace the real ticket with it. Either way, post one
   issue comment: what changed, or why the draft did not clear the rubric.
8. Run check_stop.py with this round's missing-fields signature, the
   budget (3), and previous_signature. Do not compare them yourself.
   stop is true: add "needs-human", stop. stop is false: persist the
   updated state, done for this poll. Persisting includes the id of the
   comment this poll used: a state file that never records it lets the next
   poll read the same comment as new, forever. Step 6 stops before this step
   and has to record the id itself.
```

## Verify

```bash
cp config.json.example config.json   # fill in your GitHub username
task clone
task create-test-tickets && task run --
```

A first poll needs no comment. It grooms every open draft. Run it again
with no new GitHub comments: those tickets should be no-ops.

## Prompt 5: compare against the answer

```
Diff what I built in .claude/ against ../../solutions/sol1_enhancer/.claude/,
field by field and step by step, not just the raw text. Tell me where they
differ in behavior, not just wording, and for each difference, whether it is
a real gap or a legitimate different choice. I will decide what to change.
```
