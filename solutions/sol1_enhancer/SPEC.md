# Spec. Lab 1. Ticket enhancer, as a Claude Code plugin

A vague ticket in, a ready contract out. No human sits in an interactive
session driving this loop: it polls the ticket's GitHub issue for comments
and acts on what it finds.

**Artifact: A Claude Code plugin (agents and skills) that grooms every open
ticket in your fork, one poll at a time.**

This folder holds the finished answer: `.claude/agents/`,
`.claude/skills/enhancer-loop/`, and `config.json.example`. Build it in
`labs/lab1_enhancer/` by following `prompts/claude-code.md`, then compare
your result against this folder.

This folder is standalone. It does not depend on the root Taskfile. Every
command here runs from this folder, start to finish: clone your fork, seed
some test tickets, run a poll. It does not depend on any scripts either. 
All code, skills, plugins, agents are in this folder alone. 
This is by design to make the labs self-contained and easy to run.
This also makes it easier to deploy this via a new repo if/when needed. 

## The roles

- **`enhancer-judge`** (agent). Reads a ticket, real or a candidate draft,
  and reports which required fields for its kind are genuinely present. It
  holds no write tool: a judge that could edit the ticket could grade
  itself.
- **`enhancer-doer`** (agent). Given a ticket, its missing fields, and the
  latest issue comment if there is one, investigates the target app's code
  and drafts a full replacement body. It holds no write tool either: its
  draft is text output, not a file, so nothing it writes can reach the real
  ticket without being judged first.
- **`enhancer-loop`** (skill, the orchestrator). The only role that writes
  the real ticket file or talks to GitHub. Runs one poll-and-act step, then
  exits.

## Set up your fork

1. Fork the target repo into your own GitHub account. The canonical
   upstream is `RichardHightower/northwind-field-crm` today, moving to
   `SpillwaveSolutions/northwind-field-crm` around Saturday. Fork whichever
   is canonical when you do this, into your own account, not into
   `SpillwaveSolutions`.

2. From this folder, copy the config template and fill in your GitHub
   username:

   ```bash
   cd solutions/sol1_enhancer
   cp config.json.example config.json
   ```

3. Clone your fork:

   ```bash
   task clone
   ```

   This reads `fork_owner` and `repo_name` from `config.json` and clones
   that repo into `work/northwind-field-crm`. Every task here runs from this
   folder; you never need the repo root.

## Run it

One step, by hand:

```bash
task run -- --ticket T001
```

Every open ticket, one poll:

```bash
task run --
```

## Keep it running

`enhancer-loop` runs one poll and exits. Something else has to call it
again, and again, for this to be an actual loop over time. Three ways to do
that, in order of how real each one is meant to be:

### For the seminar: run forever, in one terminal

```bash
task poll-forever -- --ticket T001    # one ticket
task poll-forever --                  # every open ticket
```

This is `while true: task run; sleep poll_interval`, nothing more. It never
stops on its own, whether every ticket has passed or not. Leave it running
in a terminal for the length of the session, pretend it is a process
running somewhere in the cloud, and `Ctrl-C` it when you are done. Use this
only for a live seminar, where a real scheduler is overkill. It is not the
shape this takes in production. See "How this should really run" below.

### Interactively, letting the skill re-invoke itself

Run `claude`, then type `/enhancer-loop --repo ...` directly. Once any
ticket is still waiting on its next poll, the skill invokes the built-in
`loop` skill itself, using `poll_interval` from `config.json`, and keeps
polling without you typing `/loop` by hand. This only works because the CLI
process stays alive between polls in an interactive (or backgrounded)
session. It does not work through `task run` or `task poll-forever`
(`claude -p`, which exits right after each poll) or the seminar's forever
loop above, which does not use `/loop` at all.

You can also wrap `task run` in `/loop` yourself, the same idea, spelled
out by hand instead of automatic:

```
/loop 10m task run --
```

### How this should really run

Neither of the above is the production shape. A terminal that has to stay
open, whether looping by hand or running `poll-forever`, is not a
deployable system: close the laptop and the polling stops. The real target
is a scheduled GitHub Actions workflow, triggered on a cron interval,
running `task run` once per trigger, the same one-shot, stateless
invocation this skill already is. `.harness/last-enhancer-<id>.json`
already persists state file-to-file in the target repo for exactly this
reason: a scheduled job with no memory of its own between runs can pick up
exactly where the last run left off. Porting this is out of scope here,
that workflow file does not exist yet.

## GitHub has no "ready" status

Issues have open and closed state, and labels, nothing else built in. This
design tracks progress with three labels the orchestrator creates the first
time it needs one:

| Label | Means |
|---|---|
| `enhanced` | The enhancer has posted at least one draft. Stays on the issue even after `ready`, it is a history marker, not a status. |
| `ready` | The newest comment was `LGTM`. The ticket's `state: ready` and `loop: implementer`. |
| `needs-human` | Escalated: the same gaps twice running, or the round budget is spent. |

## The exits

Same three as before, now checked per ticket, per poll, not in one long-
running process:

- The newest comment is `LGTM` **and** the rubric already reads ready:
  pass. `LGTM` on a ticket the rubric has not cleared finalizes nothing.
- Two rounds in a row find exactly the same gaps: escalate, the human has
  not acted and another round will not help.
- The round budget (3) is spent: escalate.

## What "ready" means

| Kind | Required fields |
|---|---|
| Bug | title (8+ characters), numbered steps, expected, actual, environment |
| Feature | problem, proposal, value, 2+ acceptance criteria a test can fail |
| UI | same as feature, plus a wireframe or mockup |

`.claude/skills/enhancer-loop/scripts/check_fields.py` is the deterministic
half of the judge: it takes the agent's `{kind, present_fields}` and
computes `missing_fields` itself, against this table, rather than trusting
the model's own claim about what is missing.
`.claude/skills/enhancer-loop/scripts/check_stop.py` does the same for the
other two exits: it takes `{round, budget, signature, previous_signature}`
and computes `{stop, reason}` itself, rather than trusting the skill's own
read of whether two signatures matched.

## Known limitations

- There is no dollar or token spend tracking or cap.

## Worth reading

- `.claude/skills/enhancer-loop/SKILL.md`, the orchestrator's full step list
- `.claude/agents/enhancer-judge.md`, `.claude/agents/enhancer-doer.md`
- `.claude/skills/enhancer-loop/scripts/check_fields.py`
