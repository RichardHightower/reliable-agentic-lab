# Troubleshooting. Lab 1

## `"claude": executable file not found in $PATH`

If you ran `task create-test-tickets && task run --` from
`solutions/sol1_enhancer`, that is expected. That folder is Claude Code
only. Leave it. Use this lab folder, or `solutions/sol1_enhancer_grok_build`
/ `solutions/sol1_enhancer_opencode`.

This is also the error `task run` used to always throw from *this* folder
if Claude Code was not installed, even when you had built a Grok, Codex,
or OpenCode plugin.

`task run` now looks at the skill tree in this folder and calls that CLI:

```bash
task detect
```

A `.claude/settings.json` stub is not a plugin. You need one of:

- `.claude/skills/enhancer-loop` → needs `claude` on PATH
- `.grok/plugins/ticket-enhancer/skills/enhancer-loop` → needs `grok`
- `.agents/skills/enhancer-loop` → needs `codex`
- `.opencode/skills/enhancer-loop` → needs `opencode`

If `task detect` prints `grok` and then `task run` still dies on `grok`
not found, install the Grok CLI. Do not install Claude Code just to
satisfy a Grok lab.

If `task detect` says there is no enhancer-loop skill, build from
`prompts/`, or copy the answer for your tool from
[FALL-BEHIND.md](FALL-BEHIND.md).

If more than one tree is present:

```bash
AGENT=grok task run --
```

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

## `create-test-tickets` reopens the old issues

It matches on a title that still starts with `[Txxx]`. Closing by hand is
not enough. Retire them, then seed again:

```bash
task reset-test-tickets
task create-test-tickets
```

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
