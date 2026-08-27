# Lab 1 ticket enhancer, for Codex CLI

A vague ticket goes in. A ticket that meets a written contract comes out.
Nobody sits in a chat window: the loop polls the ticket's GitHub issue,
reads the newest comment, and acts on it.

This folder is the finished Codex answer for lab 1. The Claude Code answer is
`../sol1_enhancer/`. Both run the same loop, the same rubric, and the same
exits.

## Read these first

| File | What it covers |
|---|---|
| [SPEC.md](SPEC.md) | The design: roles, labels, exits, and what "ready" means. |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Set up your fork and run a poll. |
| [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) | **Why the Codex port differs from the Claude one, and the four things that will bite you.** |

Read [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) before you change how
a role is launched. The short version: Codex has no per-agent tool list, so
the judge and the doer are kept from writing by running in their own
`read-only` process, not by a `tools:` line.

## The roles

| Role | What it is | May write? |
|---|---|---|
| `enhancer-loop` | The orchestrator skill. One poll-and-act step, then it exits. | Yes. It is the only role that writes the ticket or calls `gh`. |
| `enhancer-judge` | Grades one ticket against the rubric for its kind. | No. It runs `-s read-only`. |
| `enhancer-doer` | Drafts a better ticket body and returns it as text. | No. It runs `-s read-only`. |

## Quick start

```bash
cp config.json.example config.json   # fill in your GitHub username
task clone
task fence-check
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
```

Give one poll about five minutes. It starts three model processes, and each
child takes 12 to 25 seconds before the orchestrator's own turns.
