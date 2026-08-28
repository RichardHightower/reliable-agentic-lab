# Architecture. Lab 2

A ready ticket in, a green rubric out. This is the centre of the workshop.

## The shape

Every loop in this workshop is the same three parts. Only the object changes.

```
orchestrator  owns the budget and the exits. Writes nothing.
     |
     +-- doer    writes files inside a declared scope
     |
     +-- judge   scores the result. Holds no write path.
```

For this lab: an orchestrator writes nothing, a test implementer owns tests/ only, a code implementer owns app/ and is denied tests/, and a judge holds no write path at all.

## Why write scope matters

Scope is declared in `.loop.yml` in the target repo and enforced at the tool
boundary. It is not an instruction in a prompt, because an agent can talk its
way past an instruction and cannot talk its way past a missing tool.

The judge has no `write` method to call. That is why it cannot grade its own
homework.

## The exits

Three, and no fourth: pass, retry, escalate. Python holds the loop, so the model
never counts its own retries.

The exit people forget is stable failure. When this round fails in exactly the
same way as the last one, the loop is not converging, and spending the rest of
the budget to watch it fail identically buys a surprise bill rather than a fix.

## Where the code lives

The answer for this lab is `solutions/sol2_implementer/`.

Worth reading:

- `solutions/sol2_implementer/rubric.py`
- `solutions/sol2_implementer/gates.py`
- `solutions/sol2_implementer/roles.py`
- `solutions/sol2_implementer/steps.py`
