# Worklog git hooks

These are Git hooks from the Worklog plugin. They protect the event log
and the generated roadmap. They are not workshop loop code, and they are
not Claude Code hooks.

Git does not run a tracked `hooks/` folder on its own. Default is
`.git/hooks/`. These scripts fire only after `core.hooksPath` points here.

## Install

`task setup` does this:

```bash
git config --local core.hooksPath hooks
```

`--local` keeps it on this repository. It does not touch the CRM clone in
`work/` and it does not write a global gitconfig. Running setup twice is a
no-op for this line. The relative path `hooks` is relative to the working
tree root.

An existing clone that never ran setup after this landed still has them as
plain files. Run the `git config` line, or `task setup` again.

`git commit --no-verify` skips them. CI does not.

## The three scripts

| Script | Git event | What it does |
|---|---|---|
| `pre-commit` | every `git commit` | Branch guard, conflict markers, log schema, merge integrity, roadmap freshness, then optional fold / ADR / IA gates |
| `commit-msg` | after the message is written | The message must cite a worklog item or a ticket |
| `pre-merge-commit` | auto-commit of a merge | Sets `WORKLOG_MERGE_COMMIT=1` and execs `pre-commit` |

Git runs `pre-merge-commit` instead of `pre-commit` when a merge
auto-commits. Without the wrapper, two PRs that each refresh the roadmap
can land a stale one on `main` and only CI notices. `MERGE_HEAD` is not
yet on disk when Git invokes this hook, so the wrapper is Git's own
signal that a merge commit is being created.

All three are executable (`100755`). Failures print to stderr as
`worklog: ...` and exit 1.

The hook never writes bytecode. It exports `PYTHONDONTWRITEBYTECODE=1` so
an import cannot dirty the worktree with `__pycache__` after `git add`.

## `pre-commit`, in order

Each step is a hard fail unless noted. Later steps do not run after a fail.

### 1. Branch guard

Rejects a commit whose current branch is `main` or `master`.

Exempt when any of these is set:

- `WORKLOG_MERGE_COMMIT` — `pre-merge-commit` sets this
- `MERGE_HEAD` on disk — a merge resumed with a later `git commit`
- `WORKLOG_SKIP_BRANCH_GUARD` — CI, and any other non-commit caller

Main is pull-only. Author work on a branch.

### 2. Conflict markers

Scans staged files (`git diff --cached`, added / copied / modified only).
Fails if a staged file contains a conflict marker line: seven `<`, seven
`=`, or seven `>`, at column 0, followed by a space or end of line.

Unstaged conflicts elsewhere in the tree are ignored. There is no merge
exemption. A merge is exactly when this check matters.

### 3. Event log: `.work/todo.jsonl` and `.work/done.jsonl`

Skipped if the file is missing. For each file that exists:

**Trailing newline.** The last byte must be a newline. Without it, a union
merge fuses the last line of one side with the first line of the other and
two events become one unparseable line. This is invariant 15.1, and the
reason this hook exists.

**Schema.** Each non-empty line must be JSON with `ev`, `ts`, `actor`, and
`op`. Every event except `op: compact` must also have `item`.

**Taxonomy**, on `create` and `snapshot` events only, reading `set.level`
and `set.kind`:

- `level` if present: `epic`, `story`, `task`, or `subtask`
- `kind` if present: `feature`, `bug`, `ops`, or `triage`
- `level: epic` cannot have `kind: bug` or `kind: triage`
- `level: epic` cannot have `milestone` (milestone lives on leaves)

Legacy `type` events are left for the fold to normalize.

### 4. Merge integrity

Runs only when a merge is in flight (`WORKLOG_MERGE_COMMIT` or
`MERGE_HEAD`) and `bin/compact.py` exists.

```text
python3 bin/compact.py --merge-check .work/todo.jsonl .work/done.jsonl
```

A union merge can resurrect lines a compaction just deleted, or land two
branches that each claimed the same external ticket. Failure means resolve
by hand, then `git merge --continue` or `git merge --abort`.

### 5. Roadmap freshness

Runs only when `bin/render_roadmap.py` and `docs/roadmap.md` both exist.
Renders to a temp file and diffs. Fail means the file is stale or was
hand-edited. Fix: `worklog roadmap-render`, and commit the log and the
roadmap together.

### 6. Fold tests (guarded)

Runs `python3 tests/test_fold.py -q` only if that file exists. Scaffolded
repos have no `tests/`; the suite lives in the source Worklog repo. This
repository does not have it, so the step is skipped.

### 7. ADRs (guarded)

Runs `worklog adr check` only if `docs/adr/` exists and `bin/worklog` is
executable. This repository has no `docs/adr/`, so the step is skipped.

### 8. IA gates (guarded)

Runs only if `bin/ia.py` exists, `bin/worklog` is executable, **and**
`docs/.index/` exists. The extra directory check is the opt-in: a scaffold
gets `bin/` from the plugin but has never generated an index, and must not
be blocked on its first commit. This repository has no `docs/.index/`, so
the whole block is skipped.

When it does run, these are hard fails:

- `worklog ia-normalize --check`
- `worklog ia-inventory --check`
- `worklog ia-render --check` if `bin/ia_render.py` exists

These warn only:

- `worklog trace-check` if `bin/ia_graph.py` exists
- `worklog doc-verify --staged --strict` if `bin/doc_verify.py` exists

`trace-check` stays warn-level here forever; `--strict` is the release
gate. `doc-verify` is scoped to documents this commit touches, not the
whole tree, and is skipped on a shallow clone.

## `commit-msg`

The message must contain one of:

- a 26-character Crockford ULID (`[0-9A-HJKMNP-TV-Z]{26}`), a worklog item id
- a GitHub-style ticket (`#` plus digits), for example `#127`

Merge commits are exempt: if `MERGE_HEAD` exists, the hook exits 0. They
are not new work.

## What this repository actually enforces

| Check | Runs here |
|---|---|
| Branch guard | yes, locally |
| Conflict markers | yes |
| `.work/*.jsonl` trailing newline and schema | yes |
| Merge integrity via `bin/compact.py` | yes, during a merge |
| `docs/roadmap.md` freshness | yes |
| Fold tests | no, no `tests/test_fold.py` |
| ADR check | no, no `docs/adr/` |
| IA / wiki inventory | no, no `docs/.index/` |
| Commit message cites a ULID or `#N` | yes, locally and on PRs |

## CI

[`.github/workflows/worklog.yml`](../.github/workflows/worklog.yml) runs on
every push and pull request.

1. `WORKLOG_SKIP_BRANCH_GUARD=1 hooks/pre-commit` — same script, but a CI
   checkout of `main` is not a commit in flight, so the branch guard would
   false-fail without the skip.
2. On pull requests only, `hooks/commit-msg` over every non-merge commit
   in `base..HEAD`.

A push of a message with no ticket can still succeed. The matching PR will
fail. That is the intended split.

## Policy this is enforcing

See `CLAUDE.md` / `AGENTS.md`. Do not hand-edit `.work/*.jsonl` or
`docs/roadmap.md`. After changing work items, run `worklog roadmap-render`
and commit the log and the roadmap together.
