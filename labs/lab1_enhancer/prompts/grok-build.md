# Prompt for grok build

Build the ticket enhancer as a Grok Build project plugin. The finished answer
is `solutions/sol1_enhancer_grok_build/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_grok_build/SPEC.md) for the design
and
[IMPLEMENTATION_NOTES.md](../../../solutions/sol1_enhancer_grok_build/IMPLEMENTATION_NOTES.md)
for how Grok loads a plugin, which is the part that will surprise you.

Work from this folder:

```bash
cd labs/lab1_enhancer
grok -p "$(cat prompts/grok-build.md)"
```

Interactive instead: run `grok` here and paste each prompt below in turn.

---

## Prompt 0: the two things that will waste your hour

Learn these before you build anything. Both fail silently.

**Grok loads a project plugin only from a trusted checkout.** Trust attaches
to the git root, not to this folder. Run `grok` here once with no arguments
and accept the trust prompt. Headless `grok -p` never prompts, so until trust
exists your loop finds no skill and does nothing.

**On grok 1.0.5 a project plugin registers no skills and no agents on its
own.** The plugin directory alone is not enough. Three symlinks under `.grok/`
are what make it runnable, and prompt 1 writes them.

Check names, never counts:

```bash
grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
```

All three must be listed. The count on the **Plugins** line counts
directories, so `1 agents` shows even when two agent files loaded. It is not
proof of anything.

## Prompt 1: the plugin, and the three symlinks

Create the plugin under `.grok/plugins/ticket-enhancer/`:

```
.grok/plugins/ticket-enhancer/
  plugin.json                       name, description, version
  agents/enhancer-doer.md           drafts the ticket, writes tickets/** only
  agents/enhancer-judge.md          grades against the rubric, writes nothing
  skills/enhancer-loop/SKILL.md     the orchestrator, one poll-and-act step
```

Then register it with the three symlinks Grok actually reads:

```bash
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-doer.md  .grok/agents/enhancer-doer.md
ln -sfn ../plugins/ticket-enhancer/agents/enhancer-judge.md .grok/agents/enhancer-judge.md
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop     .grok/skills/enhancer-loop
```

The judge writes nothing. That is the whole point of splitting it from the
doer, so check it before you go on.

## Prompt 2: the deterministic half

Two scripts under `skills/enhancer-loop/scripts/` decide the things a model
must not decide for itself:

- `check_fields.py` returns the authoritative `{kind, missing_fields, ready}`
  from the judge's JSON.
- `check_stop.py` returns the authoritative `{stop, reason}` from the round,
  the budget, and this round's signature against the previous one.

A stop condition written as prose is a stop condition a model can talk itself
past. Copy both scripts verbatim from the answer.

## Prompt 3: the loop

Write `skills/enhancer-loop/SKILL.md` as numbered steps. It takes `--repo`,
`--ticket`, and `--simulate-comment`. Keep every step number and every `gh`
command.

Four rules that cost the most to rediscover. Every one of them produced a
real duplicate or a real infinite reply before somebody wrote it down.

- Apply `state: draft` and `loop: enhancer` to every ticket, however it was
  chosen. `--ticket <id>` names a ticket to consider, it does not excuse the
  check. Skip a finished ticket out loud, on one line, so the attendee does
  not read silence as a hang.
- Look the issue up in this order and stop at the first hit: the state file's
  `github_issue`, then the ticket frontmatter's `github_issue`, then a title
  search across **all** states. Create only when none of the three found
  anything. Do not search with `--state open`, a closed issue is still that
  ticket's issue, and skipping it makes your loop open a second one for the
  same title. The frontmatter matters because it outlives the state file,
  which the `LGTM` pass deletes. If the issue you find is closed, stop and say
  so rather than creating another. However you got the number, found or
  created, write it into both the state file and the ticket's frontmatter as
  `github_issue` before you go on. Nothing else writes that frontmatter entry,
  so a lookup that only reads it never finds one.
- Every comment the loop posts ends with the marker line
  `<!-- enhancer-loop -->`, and step 3's newest-comment query skips any
  comment carrying it. Without that the loop reads its own last reply as the
  newest comment and answers it again on every poll. Do not filter by author
  instead, you run as your own `gh` account and would drop your own `LGTM`.
- Write the state file whenever you learn the issue number, on the search path
  as well as the create path. A state file that appears only when the loop
  creates the issue makes every later poll look like a first poll, and a first
  poll skips the comment fetch. That ticket would never read `LGTM`.

Grok's subagent tool is `spawn_subagent`. `IMPLEMENTATION_NOTES.md` explains
why the plugin ships no hooks.

## Prompt 4: the Taskfile

Give the folder `trust`, `clone`, `create-test-tickets`, `run`, and
`poll-forever`. `task trust` is step zero and prints what Grok currently sees,
so a reader can tell a trust problem from a code problem in one command.

## Verify

```bash
task trust                      # names all three, not counts
task create-test-tickets
task run -- --ticket T001
```

Run `task run` twice on a rubric-green ticket with no `LGTM`. The second run
must post nothing. If it posts a second identical reply, your step 3 is not
filtering the marker.

## If you fall behind

[FALL-BEHIND.md](../FALL-BEHIND.md) has the copy commands for the Grok tree.
