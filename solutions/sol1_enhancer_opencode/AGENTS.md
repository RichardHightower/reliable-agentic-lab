# Folder policy

This folder is the ticket enhancer, built for OpenCode. Three roles share
it. OpenCode loads this file into the session. Read the rule for your own
role and ignore the others.

## If you are a judge or a doer

You were started as a subagent (`enhancer-judge` or `enhancer-doer`) via
the Task tool. Follow your own agent file and nothing else on this page.

Do not start another `opencode` process. Do not spawn another agent. Do not
load `enhancer-loop`. You read files, you answer, you stop.

Your tools cannot write. `edit: deny` and `bash: deny` are the jail. That is
not an error to work around.

## If you are the orchestrator

You were started by `task run` / `opencode run --command enhancer-loop`.
You are the only role that writes the ticket file or calls `gh`.

Load the `enhancer-loop` skill and follow it. Run the judge and the doer
through the Task tool (`subagent_type: enhancer-judge` or
`enhancer-doer`). Never grade or draft a ticket in this session: those two
roles hold `edit: deny` on purpose, and grading here would skip the jail.

`check_fields.py` and `check_stop.py` decide `ready` and `stop`. Do not
decide either one in prose.

## Both

`IMPLEMENTATION_NOTES.md` explains how OpenCode loads this tree, why the
judge is a subagent and not `--agent enhancer-judge`, and the jail probe.
Read it before you change how a role is launched.
