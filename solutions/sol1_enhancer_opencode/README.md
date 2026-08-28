# Lab 1 ticket enhancer, for OpenCode

A vague ticket goes in. A ticket that meets a written contract comes out.
Nobody sits in a chat window: the loop polls the ticket's GitHub issue,
reads the newest comment, and acts on it.

This folder is the finished OpenCode answer for lab 1. It replaces the
stub left by #96. The Claude Code answer is `../sol1_enhancer/`. Both run
the same loop, the same rubric, and the same exits.

## Read these first

| File | What it covers |
|---|---|
| [SPEC.md](SPEC.md) | The design: roles, labels, exits, and what "ready" means. |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Set up your fork and run a poll. |
| [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) | How OpenCode loads this tree, the headless argv, and the judge jail. |

## The roles

| Role | What it is | May write? |
|---|---|---|
| `enhancer-loop` | The orchestrator skill. One poll-and-act step, then it exits. | Yes. It is the only role that writes the ticket or calls `gh`. |
| `enhancer-judge` | Grades one ticket against the rubric for its kind. | No. `edit: deny`, `bash: deny`. |
| `enhancer-doer` | Drafts a better ticket body and returns it as text. | No. `edit: deny`, `bash: deny`. |

Isolation is OpenCode's per-agent `permission` block, not a nested process
and not a `plugin.json` pack. Agents live in `.opencode/agents/`. The skill
lives in `.opencode/skills/enhancer-loop/`.

## Run it

```bash
cp config.json.example config.json   # fill in your GitHub username
task clone
task create-test-tickets && task run --
```
