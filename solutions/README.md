# Solutions

The answer to every lab. `sol<n>` matches `lab<n>`. The suffix names the tool or
the runtime, so a folder is `sol<n>_<name>_<product>`.

Labs 2 to 4 no longer ship four coding-tool copies of the same Python file.
Saturday fills the stub in `labs/`. The solutions tree keeps Lab 1 (six real
shapes: four products plus two runtimes) and the two runtime ports of labs
2 to 4.

Each of those folders has one prompt in the matching lab. The table lives in
[`labs/README.md`](../labs/README.md).

## Lab 1 is the exception

Its answer is a plugin or a skill set, not a Python stub, and every product
loads one its own way. The four columns are four different shapes, not four
copies of one file. Read each folder's own `README.md` and `SPEC.md`.

| Folder | Shape |
|---|---|
| `sol1_enhancer` | Claude Code plugin under `.claude/`. The reference answer. |
| `sol1_enhancer_codex` | Codex skill set under `.agents/`, plus `bin/role.sh`. Each role runs as its own read-only `codex exec` process, because Codex isolation is a process sandbox. |
| `sol1_enhancer_grok_build` | Grok Build project plugin under `.grok/plugins/ticket-enhancer/`, plus three registration symlinks. On grok 1.0.5 a project plugin registers nothing on its own. |
| `sol1_enhancer_opencode` | OpenCode skill set under `.opencode/`. Isolation is per-agent `edit: deny`. |

Both runtime ports of Lab 1 run the same poll. `enhancer.py` is the same
orchestrator in `sol1_enhancer_agent_sdk` and `sol1_enhancer_deep_agents`, it
imports no runtime, and each folder tests it against its own fakes. Only the
wiring in `loop.py` differs. The two copies are not byte-identical: the Deep
Agents one marks every comment it posts and skips those when it reads, a fix the
Agent SDK one still needs.

## Two runtimes, one role table

These are different code, not a different prompt. Every loop runs a cast of
roles, and each runtime keeps a role out of a path its own way.

| Lab | Claude Agent SDK | LangChain Deep Agents |
|---|---|---|
| `lab1_enhancer` | `sol1_enhancer_agent_sdk` | `sol1_enhancer_deep_agents` |
| `lab2_implementer` | `sol2_implementer_agent_sdk` | `sol2_implementer_deep_agents` |
| `lab3_research` | `sol3_research_agent_sdk` | `sol3_research_deep_agents` |
| `lab4_fixer` | `sol4_fixer_agent_sdk` | `sol4_fixer_deep_agents` |

`sol3_research_deep_agents` carries a second entry point. `loop.py --question`
is the Saturday artifact, a question in and a cited brief out.
`loop.py --paper --topic` is the take-home, a nine stage pipeline that produces
an evidence-backed white paper with rendered figures. Same gates, same three
exits, one more object. See that folder's `SPEC.md`.

| Runtime | How it keeps a role out of a path |
|---|---|
| Claude Code plugin | subagent tool lists; the judge has no write tools |
| Claude Agent SDK | a tool list per subagent, plus a `PreToolUse` hook for paths |
| LangChain Deep Agents | a tool list per subagent, with the path check inside the tool |

Read a port's cast without installing anything, and without cloning the target
repo:

```bash
cd solutions/sol4_fixer_agent_sdk
python loop.py --table-only
```

The judge must print `no` in the writes column. If it prints `yes`, stop.

With no target repo the command prints the declared scopes and says so on the
first line. Anything past the table still needs the real repo.

## The four casts

One loop, one cast. `roleplan.py` is the reference copy of this list, and
every port carries the same table.

| Loop | Roles |
|---|---|
| enhancer | orchestrator, doer, judge |
| implementer | orchestrator, planner, test_implementer, code_implementer, judge |
| research | orchestrator, researcher, writer, judge |
| fixer | orchestrator, code_implementer, judge |

The implementer's scopes come from `.loop.yml` in the target repo. The roles no
target repo has heard of fall back to the table's own scopes, and anything in
neither writes nothing. Failing closed is the safe way to be wrong.

## Copied into every port, on purpose

| File | What it is |
|---|---|
| `roleplan.py` | the cast per loop, and the scope per role |
| `observability.py` | the trace writer all three runtimes share |
| `extra_credit/` | ngrok and Droplet procedure answers |

`roles.py` for each runtime lives inside the port folder, not up here. An
attendee can copy one folder somewhere else and run it, with no path shim
reaching back up this tree. Standalone beats DRY here, because the folder is
the teaching unit.

The copies really are copies. Each port's own tests assert the cast by value,
not by identity, precisely because each port defines its own `RolePlan` class.

## Edit this tree by hand

`scripts/build_labs.py` used to write all 24 folders from one description per
lab. Its `LABS_SPEC` is now empty, so running it is a no-op. Every folder here
is maintained by hand.

Do not add a folder back to the generator to avoid editing it. Duplicate the
file into the folder that needs it. There is no shared engine.

## Run the tests

```bash
task test
```

Those checks need no SDK and no key. Run `task test` from a port folder for
that folder's own suite.

## Why a second runtime exists at all

To show that the harness is the product and the framework is not. The rubric,
the red gate, the write scope, and the exits are the same in all three. Only
the plumbing changes.

If a port imports a shared engine, the design leaked. Copy the file.
