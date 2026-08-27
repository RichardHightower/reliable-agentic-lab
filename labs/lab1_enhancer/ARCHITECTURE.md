# Architecture. Lab 1

A vague ticket in, a ready contract out.

## The shape

Every loop in this workshop is the same three parts. Only the object
changes, and only this lab's orchestrator is a Claude Code skill instead of
Python.

```
orchestrator  owns the polling, the round budget, and the exits.
   (skill)    Writes the real ticket file and talks to GitHub. Nothing else does.
     |
     +-- doer    investigates and drafts. Returns text, writes no file.
     |  (agent)
     |
     +-- judge   scores a ticket (real or candidate). Holds no write tool.
        (agent)
```

For this lab: the `enhancer-loop` skill owns the poll and the exits, the
`enhancer-doer` agent drafts a replacement ticket body, and the
`enhancer-judge` agent scores a ticket against the rubric for its kind.

## Why write scope matters

In the Python loops, scope is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. Here, `enhancer-judge` and `enhancer-doer`
carry no write tool at all in their agent definitions, so there is no path
for either to touch a file. The `enhancer-doer`'s draft is text output, not a
file: the orchestrator is the one that writes it, as a candidate, and only
after `enhancer-judge` has scored that candidate does the orchestrator
decide whether it replaces the real ticket. Neither agent can talk its way
past a tool it does not have.

## The exits

Three, and no fourth: pass, retry, escalate. The skill's own step list holds
the loop, so the model never counts its own retries against itself
mid-round, but nothing enforces the round budget except the skill following
its own instructions. That is a real limitation, see the SPEC's known
limitations.

The exit people forget is stable failure. When a round finds exactly the
same gaps as the last one, spending the rest of the budget to watch it fail
identically buys a surprise bill rather than a fix.

## Where the human fits

Nobody sits in an interactive session driving this loop. The orchestrator
polls the ticket's GitHub issue, and the only human input is a comment on
that issue: `LGTM` accepts the ticket, anything else is feedback to enhance
from. Repeated polling is `/loop`'s job, external to the skill.

## Where the code lives

The answer for this lab is `solutions/sol1_enhancer/.claude/`.

Worth reading:

- `solutions/sol1_enhancer/.claude/skills/enhancer-loop/SKILL.md`
- `solutions/sol1_enhancer/.claude/agents/enhancer-judge.md`
- `solutions/sol1_enhancer/.claude/agents/enhancer-doer.md`
- `solutions/sol1_enhancer/.claude/skills/enhancer-loop/scripts/check_fields.py`
