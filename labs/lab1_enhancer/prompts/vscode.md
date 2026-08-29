# Prompt for Visual Studio Code

Build the ticket enhancer as a VS Code agent plugin. The finished answer
is `solutions/sol1_enhancer_vscode/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_vscode/SPEC.md) for the design
and
[IMPLEMENTATION_NOTES.md](../../../solutions/sol1_enhancer_vscode/IMPLEMENTATION_NOTES.md)
for how VS Code loads a plugin, which is the part that will surprise you.

Work from this folder:

```bash
cd labs/lab1_enhancer
```

Interactive: open this folder in VS Code and paste each prompt below into
Copilot Chat in Agent mode. Headless: `copilot --allow-all --prompt "$(cat prompts/vscode.md)"`.

---

## Prompt 0: the two things that will waste your hour

Learn these before you build anything. Both fail silently.

**VS Code does not auto-load a plugin folder.** `.github/plugins/ticket-enhancer/`
is the packagable unit. What Copilot Chat actually discovers are project
skills under `.github/skills/` and custom agents under `.github/agents/`.
Three symlinks under those paths are what make the loop runnable, and
prompt 1 writes them.

**Open this folder, not the lab repo root.** Skills are discovered from the
workspace root. Copilot CLI started at the repo root cannot see
`/enhancer-loop`. `task run` pins `dir:` for that reason.

Check names, never counts:

```bash
task inspect
copilot skill list
```

`enhancer-loop` must be listed. `bin/fence_check.py` also fails if the
judge or the doer gained `edit`, `runCommands`, or `agent`.

## Prompt 1: the plugin, and the three symlinks

Create the plugin under `.github/plugins/ticket-enhancer/`:

```
.github/plugins/ticket-enhancer/
  plugin.json                                          Agent Plugins 1.0, name ticket-enhancer
  skills/enhancer-loop/SKILL.md                        the orchestrator, one poll-and-act step
  com.github.copilot/agents/enhancer-doer.agent.md     drafts the ticket, writes nothing
  com.github.copilot/agents/enhancer-judge.agent.md    grades against the rubric, writes nothing
```

Then register it with the three symlinks VS Code actually reads:

```bash
ln -sfn ../plugins/ticket-enhancer/skills/enhancer-loop .github/skills/enhancer-loop
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-doer.agent.md .github/agents/enhancer-doer.agent.md
ln -sfn ../plugins/ticket-enhancer/com.github.copilot/agents/enhancer-judge.agent.md .github/agents/enhancer-judge.agent.md
```

The judge writes nothing. That is the whole point of splitting it from the
doer, so check it before you go on. `tools:` is an allowlist:
`search/codebase`, `search/usages`, `web/fetch`. No `edit`. No `runCommands`.
No `agent`.

Do not put a namespace in the skill `name`. `enhancer-loop` is correct.
`ticket-enhancer/enhancer-loop` is silently skipped.

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

VS Code's subagent tool is `agent`. Custom agents live in
`com.github.copilot/agents/*.agent.md`. `IMPLEMENTATION_NOTES.md` explains
why the plugin also ships hooks, and why `chat.pluginLocations` is left off.

## Prompt 4: the Taskfile

Give the folder `inspect`, `clone`, `create-test-tickets`, `run`, and
`poll-forever`. `task inspect` is step zero and checks the three names plus
the read-only allowlist, so a reader can tell a registration problem from a
code problem in one command.

`task run` starts Copilot CLI from this folder:

```bash
copilot --allow-all --prompt "/enhancer-loop --repo <target> ..."
```

## Verify

```bash
task inspect                    # names all three, fence holds
task create-test-tickets
task run --
```

Run `task run` twice on a rubric-green ticket with no `LGTM`. The second run
must post nothing. If it posts a second identical reply, your step 3 is not
filtering the marker.

## If you fall behind

[FALL-BEHIND.md](../FALL-BEHIND.md) has the copy commands for the VS Code tree.
