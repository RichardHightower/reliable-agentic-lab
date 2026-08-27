# Instructions for the instructor

## Before saturday

```bash
task setup
task test
```

129 checks. Then confirm each loop runs with no model key:

```bash
task loop:enhancer    -- --ticket T001 --incorporate
task loop:implementer -- --ticket T001 --doer reference
task loop:research    -- --question "sqlalchemy nullable datetime column" --backend fixture
task loop:fixer       -- --doer reference
```

`task loop:enhancer` here checks the root `loops/enhancer.py` reference
engine, not lab 1: lab 1 is a Claude Code plugin and needs an LLM, so
this no-model-key check does not cover it. Verify lab 1 separately with
`cd solutions/sol1_enhancer && task run -- --ticket T001
--simulate-comment "..."`.

The fixer needs the target on its broken branch:

```bash
git -C work/northwind-field-crm checkout broken-pr
```

## The two repositories

| Repository | Role |
|---|---|
| `reliable-agentic-lab` | The engine, the labs, the decks. Attendees clone this. |
| `northwind-field-crm` | The first target. Cloned into `work/` by `task setup`. |

The engine never imports the target. That is the test of whether it is generic,
and `loops/tests/fixtures/node-target` proves it by being JavaScript.

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
2. **The red gate refusing.** `task loop:implementer -- --doer none`. No test was
   ever red, so nothing has been proven.
3. **Swap the object.** Point the implementer at
   `loops/tests/fixtures/node-target`. Same engine, different language.
4. **Reading a trace.** `.harness/last-implementer.json` in the target. Ten rows,
   the gate, and the reason.

## Rebuilding the labs

`labs/` is generated:

```bash
python scripts/build_labs.py
```

Sixteen prompts, four stubs, and four sets of docs come from one description per
module. Edit `scripts/build_labs.py`, never a generated file.
