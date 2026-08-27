# Folder policy

This folder is the ticket enhancer, built for Codex CLI. Three roles share
it, and Codex loads this file into all three. Read the rule for your own role
and ignore the others.

## If you are a judge or a doer

You were started by `bin/role.sh` with `$enhancer-judge` or `$enhancer-doer`.
Follow your own `SKILL.md` and nothing else on this page.

Do not run `bin/role.sh`. Do not start another `codex` process. Do not
delegate your grading or your drafting to anything. You read files, you
answer, you stop. Running `bin/role.sh` from here starts a copy of you, which
starts a copy of you, and the loop never returns.

Your process is read-only. Writes fail by design. That is not an error to
work around.

## If you are the orchestrator

You were started by `task run` with `$enhancer-loop`. You are the only role
that writes the ticket file or calls `gh`.

Run the judge and the doer with `bin/role.sh`, as shell commands. Never
invoke `$enhancer-judge` or `$enhancer-doer` as a skill in your own session:
a skill inherits your `workspace-write` sandbox, and the read-only jail is
the whole point of those two roles.

`check_fields.py` and `check_stop.py` decide `ready` and `stop`. Do not
decide either one in prose.

## Both

`IMPLEMENTATION_NOTES.md` explains why this port uses separate processes
where the Claude Code port uses a per-agent tool list. Read it before you
change how a role is launched.
