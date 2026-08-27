# Troubleshooting. Lab 1

## The skill stops and asks for `config.json`

Copy the template and fill in your GitHub username:

```bash
cp config.json.example config.json
```

## `task: command not found`

Install Task. See [SETUP.md](../../SETUP.md).

## `gh: command not found`, or `gh` asks you to log in

Install the GitHub CLI and run `gh auth login`. The orchestrator uses `gh`
for every issue, comment, and label operation.

## `task run` says no target repo

Run `task clone` from this folder. It clones your fork from `config.json`
into `work/`.

## Nothing happens on a second run

This is often correct, not a bug. Step 3 of the skill treats no new comment
since the last poll as a no-op, on purpose: it does not spend a round until
a human has said something. Comment on the ticket's GitHub issue, then run
it again.

## The loop escalates and you expected a pass

Read the issue comment it posted. It names the fields still missing, or why
the last draft did not clear the rubric. Reading that comment is the skill
this workshop is about, not a sign something broke.

## You are out of time

Stop and copy the answer's scaffolding in. See [FALL-BEHIND.md](FALL-BEHIND.md).

## Something is genuinely broken

Tell Rick. A fresh `config.json`, `task clone`, and one `task run` should
reach a pass or an honest escalation, and anything else is a real bug.
