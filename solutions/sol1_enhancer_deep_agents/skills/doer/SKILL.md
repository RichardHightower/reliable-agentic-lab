---
name: doer
description: Rewrite a draft Northwind Field CRM ticket so it can pass the enhancer rubric. Use when delegated as the doer subagent.
---

# Ticket doer

You rewrite one draft ticket. You write only `tickets/<id>.enhancer-candidate.md`.
You never write `app/`, `tests/`, or the real ticket file.

## How to rewrite

1. Read the current ticket.
2. Read the smallest slice of `app/` you need to make the ticket concrete.
3. Keep the YAML front matter exactly as it is (`id`, `state`, `loop`, `github_issue`).
4. Fill the missing fields for the ticket kind. Do not invent a fourth kind.

Required fields:

- bug: title, steps, expected, actual, environment
- feature: problem, proposal, value, criteria
- ui: problem, proposal, value, criteria, wireframe

A field is present only if it has real content. A heading with no body is absent.

Use these exact headings: **Problem**, **Proposal**, **Value**, and
**Acceptance criteria**. Make every acceptance criterion a concrete,
numbered `(AC-n)` statement. For a `ui` ticket, also add a readable ASCII
**Wireframe**. Do not add a wireframe to a bug or ordinary feature ticket.

5. Write the full rewritten ticket to the candidate path you were given.
6. Write nothing else.

Do not claim the ticket is ready. The judge and `check_fields.py` decide that.
