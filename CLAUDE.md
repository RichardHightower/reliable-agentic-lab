# Workshop shape (non-negotiable)

This is a **five-hour seminar**. Not a framework. Not a library. Not a generic
loop engine.

Rick has said this many times. Do not "improve" it back into a shared
abstraction.

## What you may not do

- **No shared libraries.** Not `loops/`. Not `from loops import ...`. Not a
  package whose job is "the engine". If you are about to extract a helper so
  two folders can import it, stop. Copy the file.
- **No generic looping system.** Do not invent a repo-agnostic orchestrator,
  a shared role table that every runtime must match, or a `python -m loops.*`
  command spine. That design leaked through the whole repo once. It is gone.
- **Do not recreate `loops/`.** If you find a dangling import, fix the folder
  that needs the code by copying the code into that folder.

## What this repo actually is

- **Saturday:** Claude Code agents, as Claude Code actually works. Plugins,
  skills, subagents, hooks. Fill-ins live in `labs/`. Lab 1 answers live in
  `solutions/sol1_*` (and the Codex / Grok / OpenCode twins). Labs 2 to 4
  fill the stub; the shipped answers for those loops are the two runtime ports.
- **Take-home:** Claude Agent SDK and LangChain Deep Agents, as those products
  actually work. Each port is a **standalone folder**. An attendee copies one
  folder somewhere else and it runs. Duplicate code is the point.
- Every lab folder and every solution folder is self-contained. `task test`
  from inside the folder is the check. The root Taskfile is setup, clone, and
  a receipt — not an engine.

## If you are an agent reading this

The tempting move is to DRY the four loops into one package. Do not. The
product is four concrete artifacts, each in its own folder, each using the
runtime the vendor shipped. Duplication is cheaper than a five-hour audience
having to learn your abstraction.

`AGENTS.md` is a symlink to this file. Keep it that way.

<!-- worklog:policy:start -->
## Work tracking policy

- Every plan MUST end by running `worklog plan-capture` — it writes
  `docs/plans/<date>-<slug>.md` and appends the plan's steps as work items.
- Work discovered mid-flight that wasn't in the plan: run
  `worklog add --unplanned --discovered-during <item>` BEFORE doing the work.
- Never hand-edit `.work/*.jsonl` (use `worklog`) or `docs/roadmap.md`
  (it is generated; change the work items instead).
- After changing work items, run `worklog roadmap-render` and commit the log
  and roadmap together.
- One session per working directory. Two assistant sessions sharing a checkout
  switch branches under each other and solve the same problem twice; give each
  its own `git worktree`. `worklog` warns when it sees more than one, but the
  warning is advisory and arrives after the fact.
<!-- worklog:policy:end -->
