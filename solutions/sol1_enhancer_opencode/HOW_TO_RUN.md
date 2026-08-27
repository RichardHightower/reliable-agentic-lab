# How to run this solution

Everything here runs from `solutions/sol1_enhancer_opencode/`, standalone. No
task in this folder depends on the repo root or on any other folder outside
it.

You need `opencode`, `gh`, `jq`, `task`, and `python3`.

## One-time setup

1. Copy the config template and fill in your GitHub username:

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval` (`"10m"` by default). Use a
   short one (`"1m"`, `"30s"`) while testing.

2. Clone your fork:

   ```bash
   task clone
   ```

   This reads `fork_owner` and `repo_name` from `config.json` and clones
   that repo into `../../work/northwind-field-crm`. The upstream
   `northwind-field-crm` repo is public, so forking it is always possible.
   The one known edge case: if you cannot fork the upstream repo into your
   own account (GitHub refuses to fork a repo into an account that
   already owns it), create a plain independent copy instead:
   `gh repo create <owner>/<name> --public`, clone the upstream, repoint
   its `origin` at your new repo, and push. The enhancer loop does not
   care whether the relationship is a real GitHub fork, it only needs a
   repo with the same `tickets/` layout.

3. Optional: seed a few extra draft tickets, one per kind, beyond the real
   `T001` fixture:

   ```bash
   task create-test-tickets
   ```

   Writes `T900` (bug), `T901` (ui), `T902` (feature) into
   `../../work/northwind-field-crm/tickets/`. Skips any that already exist,
   safe to run again.

## Run one poll

```bash
task run -- --ticket T001
```

A ticket's first poll never needs a comment: it creates the ticket's GitHub
issue and runs one round automatically, so there is something for a human
to react to. `--simulate-comment "<text>"` is a dev-only flag that stands in
for a real issue comment, for testing without a comment fetch:

```bash
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
task run -- --ticket T001 --simulate-comment LGTM
```

Drop `--ticket` to poll every open draft ticket in one run:

```bash
task run --
```

Cap it while you are developing. A first poll starts three model calls
(judge, doer, judge again) and has taken about six minutes here, so 180
seconds is often too short:

```bash
timeout 360 task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
```

## Repeated polling

This skill runs one step and exits; something else has to call it again.

For the seminar, run it forever in one terminal:

```bash
task poll-forever --
```

`while true: task run; sleep poll_interval`, nothing more. It never stops
on its own. `Ctrl-C` when you are done. This is a seminar stand-in, not
production shape, see `SPEC.md`.

## Scripts you can run without a model

```bash
python3 .opencode/skills/enhancer-loop/scripts/check_fields.py --demo
python3 .opencode/skills/enhancer-loop/scripts/check_stop.py --demo
```
