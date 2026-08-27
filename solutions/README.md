# Solutions

The answer to every lab. `sol<n>` matches `lab<n>`. The suffix names the tool or
the runtime, so a folder is `sol<n>_<name>_<product>`.

## Four tools, one answer each

The tool you drive does not change the answer, so the code in these four columns
is the same file. What changes is `SPEC.md`, which tells you how to drive that
tool.

| Lab | Claude Code | Codex | Grok Build | OpenCode |
|---|---|---|---|---|
| `lab1_enhancer` | `sol1_enhancer` | `sol1_enhancer_codex` | `sol1_enhancer_grok_build` | `sol1_enhancer_opencode` |
| `lab2_implementer` | `sol2_implementer` | `sol2_implementer_codex` | `sol2_implementer_grok_build` | `sol2_implementer_opencode` |
| `lab3_research` | `sol3_research` | `sol3_research_codex` | `sol3_research_grok_build` | `sol3_research_opencode` |
| `lab4_fixer` | `sol4_fixer` | `sol4_fixer_codex` | `sol4_fixer_grok_build` | `sol4_fixer_opencode` |

Each holds `SPEC.md`, the filled stub file, and a `Taskfile.yml` so `task test`
works from the folder.

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

Read a port's cast without installing anything:

```bash
cd solutions/sol4_fixer_agent_sdk
python loop.py --table-only
```

The judge must print `no` in the writes column. If it prints `yes`, stop.

## The four casts

One loop, one cast. Only `roleplan.py` carries this list.

| Loop | Roles |
|---|---|
| enhancer | orchestrator, doer, judge |
| implementer | orchestrator, planner, test_implementer, code_implementer, judge |
| research | orchestrator, researcher, writer, judge |
| fixer | orchestrator, code_implementer, judge |

The implementer's scopes come from `.loop.yml` in the target repo. The roles no
target repo has heard of fall back to the table's own scopes, and anything in
neither writes nothing. Failing closed is the safe way to be wrong.

## Shared, because every port reads it

| File | What it is |
|---|---|
| `roleplan.py` | the cast per loop, and the scope per role |
| `agent_sdk/roles.py` | the Agent SDK translation, one loop at a time |
| `deep_agents/roles.py` | the Deep Agents translation, one loop at a time |
| `observability.py` | the trace writer all three runtimes share |
| `extra_credit/` | the five event-driven assignments |

A port folder holds the lab's entry point. The translation itself stays here,
because all four labs use it and four copies would drift.

## Do not edit this tree by hand

`scripts/build_labs.py` writes all 24 folders and the four lab folders from one
description per lab. `loops/tests/test_build_labs.py` reads every generated file
and fails when one stops matching. Change the generator and re-run it:

```bash
python scripts/build_labs.py
```

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
