# Instructions

Work one module at a time. Each lab stands on its own, and a `done-*` branch
means falling behind on one never costs you the next.

## Before Saturday

Follow [SETUP.md](../SETUP.md) once. `task setup` does the rest.

```bash
task setup
task test
```

## The order

1. `labs/lab1_enhancer` grooms a vague ticket into a contract a machine can check.
2. `labs/lab2_implementer` wraps that with a harness that can score it. This is
   the centre.
3. `labs/lab3_research` runs the same graph over a question instead of a ticket.
4. `labs/lab4_fixer` runs it with nobody watching.

## The four goals

1. **Name the roles.** Orchestrator, planner, test implementer, code
   implementer, judge. Write scope is what separates them, not instructions.
2. **Make the contract machine-checkable.** A criterion that cannot fail a test
   is a wish. A plan step with no validation statement is a wish.
3. **Put the gate at a tool boundary.** A rule in a prompt can be talked past. A
   hook cannot.
4. **Know when to stop.** Pass, retry, escalate. There is no fourth exit, and
   the one people miss is stopping when two rounds fail identically.

## What you keep

Four artifacts, and the architecture that connects them. Point the same loops at
your own repo on Monday: any repo with a conforming `Taskfile.yml` is a valid
target.
