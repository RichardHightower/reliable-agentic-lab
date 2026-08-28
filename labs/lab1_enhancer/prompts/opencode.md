# Prompt for OpenCode

Build the ticket enhancer as native OpenCode skills and agents. The finished
answer is `solutions/sol1_enhancer_opencode/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_opencode/SPEC.md) for the design
and
[IMPLEMENTATION_NOTES.md](../../../solutions/sol1_enhancer_opencode/IMPLEMENTATION_NOTES.md)
for how OpenCode loads this tree, which is the part that will surprise you.

This is not a copy of `.claude/`. A `.claude/` tree is not something OpenCode
runs. OpenCode plugins are JS/TS hooks under `.opencode/plugins/`. That is
also not this loop. OpenCode already discovers `SKILL.md` from
`.opencode/skills/` and agents from `.opencode/agents/`.

Work from this folder, or compare against the answer:

```bash
cd labs/lab1_enhancer
opencode run --dir . --auto "$(cat prompts/opencode.md)"
```

Interactive instead: run `opencode` here and paste each prompt below in turn.

---

## Prompt 0: the two things that will waste your hour

**`--agent enhancer-judge` does not start the judge.** OpenCode prints that
the judge is a subagent, not a primary agent, and falls back to `build`. The
orchestrator is the default `build` agent. It loads the skill and spawns
`enhancer-judge` / `enhancer-doer` through the Task tool.

**Headless is `opencode run`, not the TUI.** `task run` uses:

```
opencode run --dir <this folder> --auto --command enhancer-loop -- --repo <TARGET> <args> < /dev/null
```

`--auto` approves asks that are not explicitly denied. It does not override
`edit: deny` on the judge. Close stdin. Task pipes it, and a hang with no
output looks like a slow model.

Check names:

```bash
cd labs/lab1_enhancer
opencode agent list
```

You want `enhancer-judge (subagent)` and `enhancer-doer (subagent)` with
`edit: deny` and `bash: deny` as last matching rules.

---

## Prompt 1: the judge agent

Create `.opencode/agents/enhancer-judge.md`.

```
Create .opencode/agents/enhancer-judge.md, a subagent named enhancer-judge.

Frontmatter:

---
description: Grade one enhancer ticket. Return JSON only.
mode: subagent
permission:
  edit: deny
  bash: deny
---

Its job: read one ticket file (a path I give it) and report which required
fields, for the ticket's kind, have real content. A judge that could edit
the ticket could grade itself, so it must not be able to.

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

Prove the jail before you trust it. Spawn `enhancer-judge` via the Task tool
with a prompt that asks it to edit a ticket. The file must come back
byte-identical.

---

## Prompt 2: the doer agent

```
Create .opencode/agents/enhancer-doer.md, a subagent named enhancer-doer.

Same permission jail as the judge: mode: subagent, edit: deny, bash: deny.

Its job: given a ticket's current body, its kind, its missing fields, and
(if there is one) the latest comment on its GitHub issue, draft a full
replacement ticket body with every required field filled in. Its draft must
be judged before it can reach the real ticket file, so it must return the
draft as its final message's text, not write it to a file itself.

It should investigate before it invents: read the target app's code (under
app/ in the target repo) for how similar fields already behave, and use any
GitHub comment as the strongest signal for what a human actually wants.
Where neither settles a field, it should still fill it with the most
reasonable value a careful engineer would propose, stated plainly, rather
than leave it blank: a missing field blocks the ticket, a stated guess does
not.
```

---

## Prompt 3: the deterministic check

```
Create .opencode/skills/enhancer-loop/scripts/check_fields.py.

It reads a JSON object shaped like {"kind": "...", "present_fields": [...]}
(as a CLI argument or on stdin) and prints {"kind", "present_fields",
"missing_fields", "ready"}. It computes missing_fields itself, from a fixed
table of required fields per kind (the same table from prompt 1), by
subtracting present_fields. It does not trust any missing_fields the caller
might also send.

Include a --demo mode with a few assert statements I can run to check it
works.
```

Run it: `python3 .opencode/skills/enhancer-loop/scripts/check_fields.py --demo`

## Prompt 3b: the deterministic stop

```
Create .opencode/skills/enhancer-loop/scripts/check_stop.py.

It reads a JSON object shaped like {"round": int, "budget": int,
"signature": [...], "previous_signature": [...] or null} (CLI argument or
stdin) and prints {"stop": bool, "reason": str or null}. stop is true when
signature equals previous_signature (not the first round), or when round +
1 reaches budget. It computes this itself.

Include a --demo mode with a few assert statements I can run to check it
works.
```

Run it: `python3 .opencode/skills/enhancer-loop/scripts/check_stop.py --demo`

You may copy both scripts from
`solutions/sol1_enhancer_opencode/.opencode/skills/enhancer-loop/scripts/`.
Do not import them from the Claude folder.

---

## Prompt 4: the orchestrator skill

```
Create .opencode/skills/enhancer-loop/SKILL.md, invoked as enhancer-loop
--repo <path> [--ticket <id>] [--simulate-comment "<text>"].

It is the orchestrator: the only role that writes the real ticket file or
talks to GitHub, by calling the enhancer-judge and enhancer-doer subagents
via the Task tool, not by grading or drafting tickets itself. It runs one
poll-and-act step and exits.

Read config.json in your current working directory for {fork_owner,
repo_name}; every gh call targets that repo.

Without --ticket, discover every tickets/*.md in the target repo (excluding
both *.ready.md and *.enhancer-candidate.md) whose frontmatter has
state: draft and loop: enhancer.

Persist state per ticket in .harness/last-enhancer-<id>.json:
{github_issue, last_comment_id, round, previous_signature}.

Keep these protocol rules:
- Step 2 writes github_issue to both the state file and the ticket
  frontmatter, whether the number was found or freshly created. The
  frontmatter is the durable record: the LGTM pass deletes the state file,
  and nothing else in this loop writes that frontmatter entry.
- Step 2 looks the issue up in this order and stops at the first hit: the
  state file, the ticket frontmatter, then a title search with --state all.
  Never --state open: a closed issue is still that ticket's issue, and
  skipping it opens a second one for the same title. Create only when none
  of the three found a number.
- Step 3: sim: plus exact text for --simulate-comment. Persist
  last_comment_id in step 8 and on the ready-but-not-LGTM branch.
- Ready requires check_fields.py first. LGTM alone cannot set state: ready.
- Tag every comment this loop posts with <!-- enhancer-loop -->. Step 3 ignores
  comments that contain that marker. Do not filter by author.

Also create .opencode/command/enhancer-loop.md so `opencode run --command
enhancer-loop` can pass the args through $ARGUMENTS. Pin Taskfile `run` to
TASKFILE_DIR, pass --repo, --auto, and close stdin.
```

---

## Verify

```bash
cp config.json.example config.json   # fill in your GitHub username
task clone
python3 .opencode/skills/enhancer-loop/scripts/check_fields.py --demo
python3 .opencode/skills/enhancer-loop/scripts/check_stop.py --demo
timeout 180 task create-test-tickets && task run --
```

A first poll can take longer than 180 seconds here (three model calls). Cap
it anyway. Run the same comment again: it must not rewrite a green ticket.
Then `LGTM` sets `state: ready` and `loop: implementer`.

## Prompt 5: compare against the answer

```
Diff what I built in .opencode/ against
../../solutions/sol1_enhancer_opencode/.opencode/, field by field and step
by step, not just the raw text. Tell me where they differ in behavior, not
just wording, and for each difference, whether it is a real gap or a
legitimate different choice. I will decide what to change.
```
