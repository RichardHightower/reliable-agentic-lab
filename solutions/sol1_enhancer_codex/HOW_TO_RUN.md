# How to run the Codex ticket enhancer

Every command runs from this folder. Read [SPEC.md](SPEC.md) for the design,
and [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) before you change how
a role is launched.

You need `codex`, `gh`, `jq`, `task`, and `python3`.

## Set up, once

1. Copy the config and fill in your GitHub username.

   ```bash
   cp config.json.example config.json
   ```

   `config.json` also holds `poll_interval`, which defaults to `"10m"`. Use
   `"1m"` or `"30s"` while you test.

2. Clone your fork.

   ```bash
   task clone
   ```

   The clone lands in `../../work/northwind-field-crm`, a shared folder
   outside this tree, on purpose. It is gitignored.

   If GitHub refuses your fork because you already have a repo by that name,
   create an empty one and push the upstream into it:

   ```bash
   gh repo create <owner>/<name> --public
   git clone https://github.com/RichardHightower/northwind-field-crm.git
   cd northwind-field-crm
   git remote set-url origin https://github.com/<owner>/<name>.git
   git push -u origin main
   ```

   The loop only needs a repo with the same `tickets/` layout.

3. Check the orchestrator's sandbox is real.

   ```bash
   task fence-check
   ```

   See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) if it reports
   `TRUSTED`.

4. Optional. Seed three more draft tickets, one per kind.

   ```bash
   task create-test-tickets
   ```

   The script writes `T900` (bug), `T901` (ui), and `T902` (feature).

## Run one poll

```bash
task run -- --ticket T001
task run -- --ticket T001 --simulate-comment "please add acceptance criteria"
task run -- --ticket T001 --simulate-comment LGTM
task run --
```

`--simulate-comment` stands in for a real GitHub comment and skips the
fetch. It is dev-only, and only valid with `--ticket`.

A ticket's first poll needs no comment. The loop creates or finds the issue,
runs one round, and gives the human something to react to.

## Expect five minutes, not one

One poll starts three model processes: judge, doer, judge again. Each child
takes 12 to 25 seconds, and the orchestrator has its own turns around them.
A full round that promotes a candidate runs about four minutes here.

Always put a cap on it while you are developing:

```bash
timeout 420 task run -- --ticket T001
```

A run that produces no output for minutes is usually a hang, not slow
thinking. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) lists the two
that look identical from outside.

## Keep polling

```bash
task poll-forever --
task poll-forever -- --ticket T001
```

Both loop `task run` on `poll_interval` until you press Ctrl-C. Neither stops
on its own, even when every ticket has passed. The loop stands in for a
scheduler, so running forever is the point.

## Watch what it is doing

`codex exec` prints its own progress as it goes, so a run is not silent. The
noisy parts are worth knowing:

- `bin/role.sh` sends its child's progress to `/dev/null` and prints only the
  role's final message. A judge call therefore looks like a 20-second pause
  followed by one line of JSON.
- Each child also writes its final message to a file under
  `<repo>/.harness/`. Read `judge-<id>.json` or `doer-<id>.md` after a run to
  see exactly what a role returned.

## When something goes wrong

| What you see | Likely cause |
|---|---|
| No output at all, forever | A `codex exec` with stdin open. See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). |
| A child dies in under a second | The parent cannot write `$CODEX_HOME`. Check `--add-dir "$HOME/.codex"` is on the `run` task. |
| A judge that never answers | Recursion. A role started another role. |
| Every `gh` call fails | The network is off. `workspace-write` disables it unless `sandbox_workspace_write.network_access=true` is set. |
| A leftover `*.enhancer-candidate.md` | A run was interrupted mid-round. Delete it. Ticket discovery already skips it. |
