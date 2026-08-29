# Instructions for the instructor

## Before saturday

```bash
task setup
task test
```

Then confirm the Saturday answers run from their own folders.
Module 1 is one plugin per CLI. `solutions/sol1_enhancer` always calls
`claude`. Grok, Codex, and OpenCode live in sibling folders. The lab
folder dispatches from the skill tree (`task detect`).

```bash
# Module 1 needs an LLM. Pick the folder for the CLI on PATH.
# Claude Code:
cd solutions/sol1_enhancer && task create-test-tickets && task run --

# Grok Build:
cd solutions/sol1_enhancer_grok_build && task trust && task create-test-tickets && task run --

# OpenCode:
cd solutions/sol1_enhancer_opencode && task create-test-tickets && task run --

# Codex:
cd solutions/sol1_enhancer_codex && task create-test-tickets && task run --

# Lab folder (detects the skill tree you built, does not assume Claude):
cd labs/lab1_enhancer && task detect && task create-test-tickets && task run --

# Modules 2 and 4 still run with no model key (extra-credit copies of the loops):
cd solutions/extra_credit/s_ext_1_webhook
python implementer.py --repo ../../../work/northwind-field-crm --ticket T001 --doer reference

cd solutions/extra_credit/s_ext_4_fix_pr
python fixer.py --repo ../../../work/northwind-field-crm --doer reference
```

The fixer needs the target on its broken branch:

```bash
git -C work/northwind-field-crm checkout broken-pr
```

## The two repositories

| Repository | Role |
|---|---|
| `reliable-agentic-lab` | The labs, the solutions, the decks. Attendees clone this. |
| `northwind-field-crm` | The first target. Cloned into `work/` by `task setup`. |

There is no shared `loops/` engine. Each solution folder is standalone.
`CLAUDE.md` is the rule. Do not recreate the library.

## The target's branches

| Branch | State |
|---|---|
| `main` | No due dates. 75 percent coverage, below the floor. The starting point. |
| `known-good` | Due dates implemented. Everything green. The reference answer. |
| `broken-pr` | A dropped null guard. One test red. What the fixer repairs. |

## Module to lab

| Module | Lab | Deck |
|---|---|---|
| 1 | `labs/lab1_enhancer` | `slides/session-1-system-architecture` |
| 2 | `labs/lab2_implementer` | `slides/session-2-harness-engineering` |
| 3 | `labs/lab3_research` | `slides/session-3-research-loops-mcp` |
| 4 | `labs/lab4_fixer` | `slides/session-4-production-architecture` |

The outline and the clock live in [README.md](README.md). Do not restate them
anywhere else.

## Live demos worth rehearsing

1. **The push gate refusing.** Break a test in the target, ask an agent to push,
   read the refusal aloud.
2. **The red gate refusing.** From `solutions/extra_credit/s_ext_1_webhook`,
   `python implementer.py --repo ../../../work/northwind-field-crm --ticket T001 --doer none`.
   No test was ever red, so nothing has been proven.
3. **Reading a trace.** `.harness/last-implementer.json` in the target. Ten rows,
   the gate, and the reason.

## Do not rebuild the labs from a generator

`scripts/build_labs.py` is a no-op leftover. Edit lab and solution folders by
hand. Duplicate code. Do not extract a shared library to make that easier.
