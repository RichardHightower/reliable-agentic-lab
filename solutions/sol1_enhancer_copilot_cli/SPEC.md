# Spec. Lab 1. Ticket enhancer, as a GitHub Copilot CLI agent plugin.

A vague ticket goes in. A ready contract comes out. No human sits in an
interactive session while it happens. The loop polls the ticket's GitHub issue
for comments and acts on what it finds.

The artifact is a GitHub Copilot CLI agent plugin: one skill and two custom
agents, under `.github/plugins/ticket-enhancer/`. It grooms every open ticket
in your fork, one poll at a time.

Copilot CLI discovers project skills from `.github/skills/` and custom agents from
`.github/agents/*.agent.md`, not from a plugin directory on its own. This folder ships
three symlinks under those paths that point into the plugin. The plugin stays
the source of truth. Tool names are the CLI aliases (`read`, `search`, `edit`,
`execute`, `agent`), not the VS Code ids. See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).

This folder is the finished answer. Build yours in `labs/lab1_enhancer/` and
compare. It is standalone on purpose: no dependency on the repository root
Taskfile and no imports from a shared engine, so you can deploy it as its own
repo.

## The roles

| Role | Kind | Writes? |
|---|---|---|
| `enhancer-judge` | custom agent (`.agent.md`) | no |
| `enhancer-doer` | custom agent (`.agent.md`) | no |
| `enhancer-loop` | plugin skill | yes, the only one |

`enhancer-judge` reads one ticket and reports which required fields hold real
content. It holds no write tool. A judge that could edit the ticket could
grade its own work.

`enhancer-doer` investigates the ticket and the target app, then returns a
full candidate ticket body as the text of its reply. It holds no write tool
either, so its draft reaches a file only after the orchestrator saves it and
the judge scores it.

`enhancer-loop` is the orchestrator. It runs one poll-and-act step and exits.

### The lockdown is deliberately uneven

Both custom agents carry a read-only allowlist (`read`, `search`). Neither has
`edit`, `execute`/`shell`, or `agent`, so neither can write a file, run `gh`,
or spawn another agent. The orchestrator is the parent Copilot CLI agent. It
holds the shell, writes the ticket file, and runs `gh`.

That asymmetry is the design, not an oversight. The roles that could grade or
draft their own work cannot act, and the role that acts does not grade. An
allowlist on the two agents is what makes that split real rather than a
promise in a prompt.

## Set up your fork

Fork `RichardHightower/northwind-field-crm` into your own account. Copy
`config.json.example` to `config.json` and fill in your GitHub username.
`task clone` reads `fork_owner` and `repo_name` from it and clones into
`work/northwind-field-crm`.

Run Copilot CLI from this folder. Skills live relative to that cwd. See
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).

## Run it

```bash
task run --
task run --                 # every open ticket
```

Interactive: `copilot` in this folder, then `/enhancer-loop --repo ../../work/northwind-field-crm`.

## Keep it running

Three ways, in order of realism.

1. **For the seminar, run forever in one terminal.**
   `task poll-forever --`. It is `while true: task run; sleep poll_interval`
   and nothing more. It never stops on its own, whether every ticket has
   passed or not. Press Ctrl-C when you are done. This is not production
   shape.
2. **A cron job.** One `task run` per trigger. The state file already
   persists everything a stateless run needs.
3. **How this should really run.** A scheduled GitHub Actions workflow on a
   cron interval, running `task run` once per trigger.
   `.harness/last-enhancer-<id>.json` exists for exactly that case. The
   workflow file is out of scope for this lab.

Copilot CLI has no built-in loop skill, so the skill cannot re-invoke
itself the way the Claude Code answer does. Repeated polling always comes
from outside the process.

## GitHub has no "ready" status

The orchestrator creates three labels on demand and uses them as the status
this loop needs.

| Label | Means |
|---|---|
| `enhanced` | At least one draft has been posted. A history marker, it stays after `ready`. |
| `ready` | The newest comment was `LGTM` on a ticket the rubric already accepts. The ticket file becomes `state: ready`, `loop: implementer`. |
| `needs-human` | The same gaps came back twice running, or the round budget is spent. |

## The exits

Checked per ticket, per poll:

1. The newest comment is `LGTM` **and** the rubric already reads ready. Pass.
   `LGTM` on a red rubric finalizes nothing.
2. Two rounds in a row find exactly the same gaps. Escalate.
3. The round budget (3) is spent. Escalate.

`check_stop.py` decides exits 2 and 3. The skill never decides them in prose.

## What "ready" means

| Kind | Required |
|---|---|
| `bug` | title of 8 or more characters, numbered steps, expected, actual, environment, and source evidence for the claimed failure |
| `feature` | problem, proposal, value, 2 or more testable acceptance criteria |
| `ui` | the feature fields, plus a wireframe or mockup |

`check_fields.py` is the deterministic half of the judge. The agent reports
which fields it found. The script looks up the rubric for that kind and
computes `missing_fields` itself, so a model's own claim about readiness is
never the thing that decides.

The first successful Judge call also records that kind in the ticket's
frontmatter. Later polls use the recorded kind for the deterministic check.
That keeps a feature ticket from becoming a UI ticket merely because its
implementation mentions a form or page.

For bugs, the Judge also checks the app before it calls a candidate ready. A
ticket needs a named code path that supports its claimed actual behavior. If
the source contradicts the report, the loop preserves the original ticket and
marks it `needs-human`; a polished but invented bug is not an enhancement.

## Known limitations

No dollar or token spend tracking, and no cap.

## Worth reading

- `.github/plugins/ticket-enhancer/skills/enhancer-loop/SKILL.md`
- `.github/plugins/ticket-enhancer/com.github.copilot/agents/enhancer-judge.agent.md`
- `.github/plugins/ticket-enhancer/skills/enhancer-loop/scripts/check_fields.py`

## Deploy on GitHub Actions (ticket change events)

Saturday still polls. Production is an event: `issues` opened / edited /
labeled, and `issue_comment` created.

Copy-me workflow and the backend matrix live in the Saturday lab notes, not
here:

- `labs/lab1_enhancer/GITHUB-ACTIONS.md`
- `labs/lab1_enhancer/workflows/enhance-on-issue.yml`

Copy the YAML onto **your CRM fork**. Do not enable it on the shared
instructor repo. The trigger starts one poll. This folder still owns the
exits. Skip comments that contain `<!-- enhancer-loop -->`. Set
`ENHANCER_BACKEND` to `copilot-cli`.

Copilot CLI on hosted runners needs a Copilot token. Prefer Claude
Code, Agent SDK, or Deep Agents in Actions. Keep this port on a laptop or
`ext_5_digitalocean`.
