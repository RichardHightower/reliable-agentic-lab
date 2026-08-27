# Implementation notes: what changes when you move this loop to Codex

Read this before you change how a role is launched.

The Claude Code version of this lab lives in `solutions/sol1_enhancer/`. It
runs the same loop with the same rubric and the same exits. The two ports
look different in one place only, and everything else here follows from it.

## Codex has no per-agent tool list

In Claude Code, the judge is a subagent file that declares its tools:

```yaml
---
name: enhancer-judge
tools: Read, Grep, Glob
---
```

No `Write`, no `Edit`. The judge cannot save a file because it was never
handed a tool that saves files. That is what stops a judge from grading its
own draft.

Codex has no equivalent. A Codex skill cannot declare a tool list. A skill
you invoke with `$enhancer-judge` runs **inside your current session** and
inherits whatever that session is allowed to do. Invoking a skill does not
open a tighter jail.

**Isolation in Codex is a process sandbox, not a role flag.**

## The two knobs, always read together

`--sandbox` / `-s` picks what the process may touch:

| Mode | Reads | Writes | Network |
|---|---|---|---|
| `read-only` | anywhere | nothing | no |
| `workspace-write` | anywhere | the workspace and any `--add-dir` | off by default |
| `danger-full-access` | anywhere | anywhere | yes |

The approval policy picks when a human is asked. `codex exec` already fixes
it at `never`, because a headless process has nobody to ask. Do not pass
`-a` / `--ask-for-approval` to `codex exec`. This build has no such flag and
the command fails.

Two traps live in that table:

- **`codex exec` defaults to `read-only`.** A process that has to write needs
  `-s workspace-write` spelled out.
- **`workspace-write` does not turn the network on.** Every step of this loop
  calls `gh`. Without
  `-c sandbox_workspace_write.network_access=true`, every one of them fails.

## How this port is wired

Three processes, not one.

| Role | Process | Sandbox | May write? |
|---|---|---|---|
| `enhancer-loop` | `task run` starts it | `workspace-write` plus network | yes, the ticket and `gh` |
| `enhancer-judge` | `bin/role.sh` starts it | `read-only` | no |
| `enhancer-doer` | `bin/role.sh` starts it | `read-only` | no |

`bin/role.sh` holds the flags. They are not in `SKILL.md`, on purpose: a
sandbox flag the orchestrator retypes each round is a flag the orchestrator
can mistype or drop. `-o` / `--output-last-message` captures the role's final
message to a file, so the parent reads the judge's JSON without parsing
progress output around it.

### Why not just invoke the skills in one process

It is cheaper and faster, and it gives up the thing this lab is about. A
skill in the orchestrator's session inherits `workspace-write`. The judge's
`SKILL.md` would say "do not write," and nothing would stop it. That is the
same hole you would refuse in the Claude version if the judge held `Write`.

A hybrid (jail the judge, leave the doer in-session) is worse than it sounds.
The doer is the role that most wants to just fix the file. It is the write
you care about.

### The cost

Two extra model starts per round. Slower, and more money. On this machine a
single judge call takes about 12 to 25 seconds, so one full round is roughly
70 seconds of child processes before the orchestrator's own turns. Budget
five minutes for one poll, not one.

## Four things that will bite you

### 1. Never pipe a prompt into `codex exec` without closing stdin

When you pass a prompt as an argument **and** stdin is open, `codex exec`
appends stdin to the prompt as a `<stdin>` block, so it waits for EOF. Task
pipes stdin. The result is not an error. There is no output, no exit code,
and no log line. It looks exactly like a slow model.

Every `codex exec` in this folder ends with `< /dev/null`, in `bin/role.sh`
and in `Taskfile.yml`. Keep it that way.

### 2. `AGENTS.md` reaches every role, including the children

Codex loads `AGENTS.md` from the working directory for every session started
there. `bin/role.sh` starts the judge with `--cd` pointed at this folder, so
the judge reads the same `AGENTS.md` the orchestrator does.

The first version of this port's `AGENTS.md` said "run the judge and the doer
through `bin/role.sh`." The judge read it, obeyed it, and ran `bin/role.sh`,
which started another judge, which read it again. Infinite recursion, each
level waiting on the one below, no error.

`AGENTS.md` here is now split by role, and each role's `SKILL.md` repeats the
rule: a judge does not start a judge. If you add a fourth role, split it the
same way.

### 3. A trusted project silently turns the fence off

`trust_level = "trusted"` under a `[projects."<path>"]` block in
`~/.codex/config.toml` relaxes the sandbox. A `workspace-write` orchestrator
in a trusted project can write anywhere on your disk. No warning, no log
line, the write just works.

Run `task fence-check` once before you demo the sandbox. It reads your config
and tells you whether any trusted entry covers this folder.

This does **not** weaken the judge or the doer. `-s read-only` holds in a
trusted project. That was tested: the judge was told to edit a ticket, and
the file came back byte-identical.

### 4. A Codex process cannot start another Codex process from inside a plain sandbox

A child `codex exec` needs to write session state under `$CODEX_HOME`
(usually `~/.codex`). A sandboxed parent does not grant that, so the child
dies in well under a second with:

```
failed to initialize in-process app-server client: Operation not permitted
```

The fix is one flag on the parent, and it is already in `Taskfile.yml`:

```
--add-dir "$HOME/.codex"
```

The orchestrator stays fenced. Adding `$CODEX_HOME` as a writable root does
not open the rest of your home directory, which was tested: with these exact
flags, a write to `$HOME` is still refused.

## Do not copy this answer onto the Grok Build branch

Grok Build is a different jail, with plugin agents and project-plugin trust.
Same lesson, different knob. Work its sandbox out from its own documentation
rather than translating these flags.
