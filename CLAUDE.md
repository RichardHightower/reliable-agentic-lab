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
