# Solutions

The answer to every lab. `sol<n>` matches `lab<n>`. The suffix names the tool or
the runtime, so a folder is `sol<n>_<name>_<product>`.

## Four tools, one answer each

For labs 2 to 4, the tool you drive does not change the answer, so the code in
these four columns is the same file. What changes is `SPEC.md`, which tells you
how to drive that tool.

| Lab | Claude Code | Codex | Grok Build | OpenCode |
|---|---|---|---|---|
| `lab1_enhancer` | `sol1_enhancer` | `sol1_enhancer_codex` | `sol1_enhancer_grok_build` | `sol1_enhancer_opencode` |
| `lab2_implementer` | `sol2_implementer` | `sol2_implementer_codex` | `sol2_implementer_grok_build` | `sol2_implementer_opencode` |
| `lab3_research` | `sol3_research` | `sol3_research_codex` | `sol3_research_grok_build` | `sol3_research_opencode` |
| `lab4_fixer` | `sol4_fixer` | `sol4_fixer_codex` | `sol4_fixer_grok_build` | `sol4_fixer_opencode` |

For labs 2 to 4 each folder holds `SPEC.md`, the filled stub file, and a
`Taskfile.yml` so `task test` works from the folder.

### Lab 1 is the exception

Its answer is a plugin or a skill set, not a Python stub, and every product
loads one its own way. The four columns are four different shapes, not four
copies of one file. Read each folder's own `README.md` and `SPEC.md`.

| Folder | Shape |
|---|---|
| `sol1_enhancer` | Claude Code plugin under `.claude/`. The reference answer. |
| `sol1_enhancer_codex` | Codex skill set under `.agents/`, plus `bin/role.sh`. Each role runs as its own read-only `codex exec` process, because Codex isolation is a process sandbox. |
| `sol1_enhancer_grok_build` | Grok Build project plugin under `.grok/plugins/ticket-enhancer/`, plus three registration symlinks. On grok 1.0.5 a project plugin registers nothing on its own. |
| `sol1_enhancer_opencode` | OpenCode skill set under `.opencode/`. Isolation is per-agent `edit: deny`. |

Both runtime ports of Lab 1 run the same poll. `enhancer.py` is one file, copied
into `sol1_enhancer_agent_sdk` and `sol1_enhancer_deep_agents` unchanged, and
each folder tests it against its own fakes. Only the wiring in `loop.py` differs.

## Two runtimes, one role table

These are different code, not a different prompt. Every loop runs a cast of
roles, and each runtime keeps a role out of a path its own way.

| Lab | Claude Agent SDK | LangChain Deep Agents |
|---|---|---|
| `lab1_enhancer` | `sol1_enhancer_agent_sdk` | `sol1_enhancer_deep_agents` |
| `lab2_implementer` | `sol2_implementer_agent_sdk` | `sol2_implementer_deep_agents` |
| `lab3_research` | `sol3_research_agent_sdk` | `sol3_research_deep_agents` |
| `lab4_fixer` | `sol4_fixer_agent_sdk` | `sol4_fixer_deep_agents` |

| Runtime | How it keeps a role out of a path |
|---|---|
| Plain Python, `loops/` | the `Judge` class has no `write` method |
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
| `agent_sdk/roles.py` | the Agent SDK translation, one loop at a time |
| `deep_agents/roles.py` | the Deep Agents translation, one loop at a time |
| `observability.py` | the trace writer all three runtimes share |
| `extra_credit/` | the five event-driven assignments |

These files live here as the reference copy, and each port folder carries its
own flat copy of the ones it needs. An attendee can copy one folder somewhere
else and run it, with no path shim reaching back up this tree. Standalone beats
DRY here, because the folder is the teaching unit.

The copies really are copies. `loops/tests/test_runtime_ports.py` asserts every
port's cast matches the table by value, not by identity, precisely because each
port defines its own `RolePlan` class.

## Edit this tree by hand

`scripts/build_labs.py` used to write all 24 folders from one description per
lab. Its `LABS_SPEC` is now empty, so running it is a no-op. Every folder here
is maintained by hand, and `loops/tests/test_build_labs.py` iterates that empty
list and asserts nothing about them.

Do not add a folder back to the generator to avoid editing it. The generator is
kept only so the tests that import it still load.

## Run the tests

```bash
task test -- loops/tests/test_runtime_ports.py
```

Those checks need no SDK and no key. They assert that all three runtimes read
the same table, in all four loops, and that the judge holds no write tool in any
of them.

## Why a second runtime exists at all

To show that the harness is the product and the framework is not. The rubric,
the red gate, the write scope, and the exits are the same in all three. Only
the plumbing changes.

If porting a loop to a new runtime requires changing `loops/`, the design leaked.
