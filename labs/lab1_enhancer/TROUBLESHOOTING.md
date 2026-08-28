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

## `task run` says no GitHub issue

`task run` never opens issues. Run `task create-test-tickets` first. That
task writes the draft files and opens a GitHub issue for each one.

## Nothing happens on a second run

If the ticket already meets the rubric, that is correct. The loop is waiting
for an exact `LGTM` on the GitHub issue. Other comments do not trigger
another edit. If the ticket is still missing fields, a second `task run --`
should enhance it again without any comment.

## The loop escalates and you expected a pass

Read the issue comment it posted. It names the fields still missing, or why
the last draft did not clear the rubric. Reading that comment is the skill
this workshop is about, not a sign something broke.

## You are out of time

Stop and copy the answer's scaffolding in. See [FALL-BEHIND.md](FALL-BEHIND.md).

## Something is genuinely broken

Tell Rick. A fresh `config.json`, `task clone`, and one `task run` should
reach a pass or an honest escalation, and anything else is a real bug.
