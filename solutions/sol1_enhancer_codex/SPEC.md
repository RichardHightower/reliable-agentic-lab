# Spec. Lab 1. Ticket enhancer, as a Codex CLI skill set

A vague ticket in, a ready contract out.

Nobody sits in a chat window waiting to answer. The loop polls the ticket's
GitHub issue, reads the newest comment, and acts on it. One poll does one
step and exits.

This folder holds the finished answer, and it runs as it stands. The Claude
Code answer to the same lab is `../sol1_enhancer/`. Both run the same rubric,
the same three exits, and the same state file. They differ in how a role is
denied write access, which
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) explains.

Everything here is standalone. No import reaches into the repo root, and the
Taskfile includes nothing. You can copy this folder out and deploy it as its
own repo.

## The roles

| Role | What it is | May write? |
|---|---|---|
| `enhancer-loop` | The orchestrator skill, at `.agents/skills/enhancer-loop/`. One poll-and-act step, then it exits. | Yes. It is the only role that writes the ticket file or calls `gh`. |
| `enhancer-judge` | Grades one ticket against the rubric for its kind. Returns one JSON object. | No. |
| `enhancer-doer` | Investigates the target app and drafts a better ticket body. Returns it as text. | No. |

The judge holds no write access because a judge that could edit a ticket
could grade its own draft. The doer holds none because the role that most
wants to just fix the file is the one you least want holding a pen.

Codex has no per-agent tool list, so neither rule can be a `tools:` line the
way it is under Claude Code. `bin/role.sh` starts each of those two roles as
its own `codex exec -s read-only` process instead. The sandbox refuses the
write before the model gets a say. Read
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) before you change how a
role is launched.

## Set up your fork

1. Fork the target repo. The canonical upstream today is
   `RichardHightower/northwind-field-crm`.

2. Copy the config and fill in your GitHub username.

   ```bash
   cd solutions/sol1_enhancer_codex
   cp config.json.example config.json
   ```

3. Clone your fork into `work/`.

   ```bash
   task clone
   ```

4. Check that the orchestrator's sandbox is real, once.

   ```bash
   task fence-check
   ```

   A `trust_level = "trusted"` entry in your `~/.codex/config.toml` turns the
   orchestrator's fence off silently. The check tells you if one covers this
   folder. It does not affect the judge or the doer, which stay read-only
   either way.

## Run it

One ticket:

```bash
task run -- --ticket T001
```

Every open ticket:

```bash
task run --
```

Give one poll about five minutes. It starts three model processes, and each
child takes 12 to 25 seconds before the orchestrator's own turns.

## Keep it running

Two ways, in order of realism.

1. **Seminar.** `task poll-forever --` loops `task run` on `poll_interval`
   from `config.json` until you press Ctrl-C. It never stops on its own,
   whether every ticket has passed or not. It is a stand-in for a scheduler,
   not a scheduler.

2. **Production.** A scheduled GitHub Actions workflow on a cron interval,
   running `task run` once per trigger. That is the same one-shot, stateless
   invocation. `<repo>/.harness/last-enhancer-<id>.json` exists precisely so
   a memoryless scheduled job can resume where the last one stopped. The
   workflow file does not exist yet.

There is no third way. `codex exec` exits when its turn ends, so nothing
inside the loop can schedule the next poll.

## GitHub has no "ready" status

The orchestrator creates three labels on first need:

| Label | Meaning |
|---|---|
| `enhanced` | The loop posted at least one draft. It stays after the ticket is ready, as a history marker. |
| `ready` | The newest comment was `LGTM` and the rubric already passed. The ticket file now reads `state: ready` and `loop: implementer`. |
| `needs-human` | Two rounds found the same gaps, or the round budget ran out. |

`loop: implementer` matters. The next module finds its work by that field,
so a ticket left at `loop: enhancer` would never be picked up.

## The exits

Per ticket, per poll, there are three:

1. **Pass.** The newest comment is exactly `LGTM` **and** the rubric already
   reads ready. `LGTM` on an unready ticket finalizes nothing. A human's
   approval can confirm the rubric, never replace it.
2. **Stable failure.** Two rounds in a row find exactly the same gaps.
   Escalate.
3. **Budget spent.** Three rounds. Escalate.

`check_fields.py` decides the first. `check_stop.py` decides the other two.
Neither is decided in prose, because a stop condition a model reasons about
is a stop condition a model can talk itself past.

## What "ready" means

| Kind | Required fields |
|---|---|
| `bug` | title (8+ characters), numbered steps, expected, actual, environment |
| `feature` | problem, proposal, value, two or more acceptance criteria |
| `ui` | the feature fields, plus a wireframe or mockup |

Each acceptance criterion has to be concrete enough that a test could fail
it. One criterion is not acceptance criteria.

## Known limitations

- No dollar or token spend cap. The loop counts rounds, not money, and this
  port spends roughly three times what the Claude port does per round.
- The scheduled workflow named above is not written yet.

## Worth reading

- `.agents/skills/enhancer-loop/SKILL.md`, the orchestrator.
- `.agents/skills/enhancer-judge/SKILL.md` and `enhancer-doer/SKILL.md`.
- `.agents/skills/enhancer-loop/scripts/check_fields.py`, the deterministic
  half of the judge.
- [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md), for why this port is
  three processes.
