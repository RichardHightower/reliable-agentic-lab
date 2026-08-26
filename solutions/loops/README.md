# Three loops (working examples)

These are the Product Requirements Document (PRD) loops.

They run against a local board that mimics GitHub issues and pull requests (PRs).
Polling is the default. Webhooks stay documented, not required.

| Loop | Goal | Exit |
|---|---|---|
| Ticket Enhancer | Vague ticket becomes a ready contract | `ready` label, or budget |
| Ticket Implementer | Ready ticket becomes a reviewed PR | hidden grader green, or budget |
| Broken PR Fixer | Failing PR becomes mergeable | grader green, or abandon comment |

No Application Programming Interface (API) key is required.
Claude, the Agent Software Development Kit (SDK), and LangGraph are attendee choices in `labs/`.

```bash
python -m solutions.loops.enhancer --ticket T001 --incorporate
python -m solutions.loops.implementer --maker reference
python -m solutions.loops.fixer --maker reference
```

Saturday still maps onto four modules. Do not build all three loops live.
