# Prompt for Codex

Build the ticket enhancer as a Codex skill set. The finished answer is
`solutions/sol1_enhancer_codex/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_codex/SPEC.md) for the design and
[IMPLEMENTATION_NOTES.md](../../../solutions/sol1_enhancer_codex/IMPLEMENTATION_NOTES.md)
for the sandbox rules, which are the part that will surprise you.

Work from this folder:

```bash
cd labs/lab1_enhancer
codex exec "$(cat prompts/codex.md)" < /dev/null
```

The `< /dev/null` is not decoration. Read prompt 0.

Interactive instead: run `codex` here and paste each prompt below in turn.

---

## Prompt 0: the one thing that will waste your hour

Before you build anything, learn these four facts. Each one fails silently.

1. `codex exec` appends open stdin to your prompt and waits for EOF. Called
   from a script or from Task, it hangs with no output and no error. End
   every `codex exec` with `< /dev/null`.
2. `codex exec` defaults to the `read-only` sandbox. A process that writes
   needs `-s workspace-write` spelled out.
3. `workspace-write` turns the network off. Every `gh` call fails until you
   pass `-c sandbox_workspace_write.network_access=true`.
4. `AGENTS.md` loads into every session started in that directory, including
   the child processes you start. An instruction meant for the orchestrator
   will be read and obeyed by the judge.

## Prompt 1: the roles, and the jail

Build three skills under `.agents/skills/`: `enhancer-loop` (the
orchestrator), `enhancer-judge`, and `enhancer-doer`.

The judge grades one ticket and returns one JSON object,
`{"kind": ..., "present_fields": [...]}`, and nothing else. The doer drafts a
replacement ticket body and returns it as text, and nothing else. The
orchestrator is the only role that writes the ticket file or calls `gh`.

Here is the problem. Under Claude Code the judge declares
`tools: Read, Grep, Glob` and simply has no way to write. Codex has no
per-agent tool list, and a skill you invoke with `$enhancer-judge` runs
inside your session with your permissions.

Write `bin/role.sh`, which starts one role as its own
`codex exec -s read-only` process and prints only its final message. Put the
sandbox flags in that script, not in `SKILL.md`. A flag the orchestrator
retypes each round is a flag it can drop.

Prove the jail before you trust it. Tell the judge to edit a ticket, and
check the file is byte-identical afterward.

## Prompt 2: the deterministic half

Write `check_fields.py`. The judge decides which fields have real content,
which is a judgment call. This script decides whether that adds up to
`ready`, which is a fact. Give it the judge's `{kind, present_fields}` and
have it compute `missing_fields` from its own rubric table. Never trust a
model's own claim about what is missing.

Bug: `bug` needs title, steps, expected, actual, environment. `feature` needs
problem, proposal, value, criteria. `ui` needs those four plus a wireframe.

Add a `--demo` flag that asserts its own behavior and prints a pass line.

## Prompt 3: the loop

Write `enhancer-loop/SKILL.md` as numbered steps. It takes `--repo`,
`--ticket`, and a dev-only `--simulate-comment`.

Per ticket: load the state file at
`<repo>/.harness/last-enhancer-<id>.json`, find or create the GitHub issue,
read the newest comment, grade the real ticket, and decide. If the rubric
passes and the comment is exactly `LGTM`, set `state: ready` and
`loop: implementer`. If the rubric fails, call the doer, write its draft to a
candidate file, grade the candidate, and keep it only if it fixes strictly
more than it breaks.

Persist the issue number as soon as you know it, whether you found it or
created it. A state file written only on the create path makes every later
poll look like a first poll, and a first poll never reads a comment.

Two rules about which ticket and which issue. Both look like details and both
produced real duplicates before they were written down.

Apply `state: draft` and `loop: enhancer` to every ticket, however it was
chosen. `--ticket <id>` names a ticket to consider, it does not excuse the
check. Skip a finished ticket out loud, on one line, so the attendee does not
read silence as a hang.

Look the issue up in this order, and stop at the first hit: the state file's
`github_issue`, then the ticket frontmatter's `github_issue`, then a title
search across **all** states. Create only when none of the three found
anything. Do not search with `--state open`: a closed issue is still that
ticket's issue, and skipping it makes your loop open a second one for the
same title. The frontmatter matters because it outlives the state file, which
the `LGTM` pass deletes. If the issue you find is closed, stop and say so
rather than creating another.

## Prompt 3b: the deterministic stop

Write `check_stop.py`. Two more exits are facts, not judgment calls: the
round budget ran out, and two rounds in a row found exactly the same gaps.
Give it `{round, budget, signature, previous_signature}` and have it return
`{stop, reason}`. Add a `--demo` flag like the other script.

Call it from the skill. A stop condition decided in prose is a stop
condition a model can talk itself past.

## Prompt 4: the Taskfile

Write a standalone `Taskfile.yml` with `clone`, `create-test-tickets`, and
`run`. Include nothing from the repo root.

The `run` task starts the orchestrator. It needs `-s workspace-write`,
network access on, `--add-dir` for the target repo, and `--add-dir` for
`$HOME/.codex`, without which your read-only children cannot start at all.

Escape the `$` in `$enhancer-loop` or the shell eats it.

## Verify

```bash
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
```

Cap it while you develop: `timeout 420 task run, ...`. One poll starts
three model processes and takes about four minutes. A run with no output for
minutes is a hang, not deep thought.

## If you fall behind

Copy the finished answer and read it:

```bash
cp -r ../../solutions/sol1_enhancer_codex/.agents .
cp -r ../../solutions/sol1_enhancer_codex/bin .
cp ../../solutions/sol1_enhancer_codex/AGENTS.md .
cp ../../solutions/sol1_enhancer_codex/config.json.example .
```
