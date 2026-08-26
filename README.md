# reliable-agentic-lab

Working code for **Engineering Reliable Agentic AI Systems**, a Packt workshop.

Saturday 29 August 2026, 10:00 to 15:00 Central (11:00 to 16:00 Eastern).
Instructor: Rick Hightower, Spillwave.

You leave with four artifacts and the architecture that connects them. Point the
same loops at your own repository on Monday.

## Agreed outline (30 July 2026, confirmed 31 July 2026)

Source: Rick's email to `denimp@packt.com`, subject "revised outline as
discussed on LinkedIn". Denim Pinto replied on 31 July 2026: "I really like the
revised structure." The four-hour format is approved. Module 2 stays the
centerpiece. Module 3 stays a hands-on build.

Total: 4 hours, including three 15-minute breaks.

### Open (10 min)

What Loop Engineering is. Why prompting does not scale. What everyone will have
built by the end.

### Module 1: System Architecture, the foundation (45 min)

- 0 to 15: Anatomy of an agent loop. Triggers, actions, verification, memory,
  human oversight.
- 15 to 40: Hands-on. Build a first autonomous agent loop with Claude Code, live.
- 40 to 45: Where this breaks at scale. Sets up Module 2.

Artifact: a working autonomous loop, running on the attendee's machine inside
the first hour.

### Break (15 min)

### Module 2: Harness Engineering, the validation layer (55 min, the center of gravity)

- 0 to 15: Why loops fail without a harness. Context management, hallucination
  containment, the Maker and Checker pattern.
- 15 to 25: Spec-driven development and graph engineering. Turn intent into a
  testable contract the agent works against.
- 25 to 50: Hands-on. Build an evaluation harness for a real coding task. An AI
  workflow that plans, executes, verifies, and iterates reliably.
- 50 to 55: Reading harness output, and knowing when to stop the loop.

Artifact: a reusable evaluation harness.

### Break (15 min)

### Module 3: Research Loops and MCP, the execution model (40 min)

- 0 to 10: MCP tool contracts. What a safe tool boundary looks like.
- 10 to 35: Hands-on. Build one live research assistant end to end. Show how an
  agent uses external tools while controlling cost and staying reliable.
- 35 to 40: Retries, budgets, and failure modes.

Artifact: a working research assistant. One worked example, not a survey.

### Break (15 min)

### Module 4: Production Architecture, the capstone (35 min)

- 0 to 12: State, observability, and what changes when a loop runs unattended.
- 12 to 30: Hands-on. Deploy a production-ready automation.
- 30 to 35: Production loop patterns, and how to adapt this to their own team.

Artifact: a complete production-ready architecture they can take back to their
engineering org.

### Close and Q&A (10 min)

### Math check

10 + 45 + 15 + 55 + 15 + 40 + 15 + 35 + 10 = 240 minutes.

Eventbrite lists a 5-hour window (11:00 to 16:00 Eastern). The extra hour is
buffer, not a fifth module.

## Start here

```bash
task setup     # venv, dependencies, clone the target repo, verify
task test      # 129 checks
```

Full instructions: [SETUP.md](SETUP.md).

## What you build

| Module | Loop | Question it answers |
|---|---|---|
| 1 | Ticket Enhancer | Is this ticket a contract a machine can check? |
| 2 | Ticket Implementer | Did the work meet the contract, and is it actually done? |
| 3 | Research Assistant | Can every claim be traced to something retrieved? |
| 4 | Broken PR Fixer | What happens when nobody is watching? |

Run any of them now, with no model key:

```bash
task loop:enhancer    -- --repo work/northwind-field-crm --ticket T001 --incorporate
task loop:implementer -- --repo work/northwind-field-crm --ticket T001 --doer reference
task loop:research    -- --question "sqlalchemy nullable datetime column" --backend fixture
task loop:fixer       -- --repo work/northwind-field-crm --doer reference
```

## The idea

The loops are generic. They point at a repository, not at this one.

A target repository is valid when its `Taskfile.yml` exposes `setup`, `test`,
`e2e`, `lint`, and `format-check`, and when `task test` writes
`reports/junit.xml` and `reports/coverage.xml`. Those two formats are the whole
interface, and any language emits them.

`loops/tests/fixtures/node-target` is a JavaScript repository that satisfies the
same contract. It exists to prove the engine is repo-agnostic.

## Layout

```
loops/          the engine. Never imports the CRM.
labs/           four labs. cd into one and work there.
labs/takehome/  the same loops in the Claude Agent SDK and Deep Agents.
slides/         four Marp decks.
work/           gitignored. The target repository is cloned here.
```

The demo application lives in its own repository,
[northwind-field-crm](https://github.com/RichardHightower/northwind-field-crm).
It is the first target, not the only one.

## Reading

- [SETUP.md](SETUP.md), once before Saturday
- [labs/HOW-TO-RUN.md](labs/HOW-TO-RUN.md), pick your coding agent
- [MCP.md](MCP.md), the two servers and what they may not do
- [slides/FEATURE-MAP.md](slides/FEATURE-MAP.md), which module proves which idea
