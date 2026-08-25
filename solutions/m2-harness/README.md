# Module 2 solution: evaluation harness

Locked title: Harness Engineering. Center of gravity. Do not cut this.

Wraps the Module 1 implementer.

- Orchestrator holds the budget.
- Maker edits CRM files. Limited tools.
- Checker reads grader output. No write tools.
- Rubric loads success criteria from the ready ticket.
- Grader is hidden pytest.
- Quality gates: pass, retry, escalate.
- Traces write to local JSON. Same schema if Langfuse joins later.

## Docs

- [SETUP.md](SETUP.md)
- [INSTRUCTIONS.md](INSTRUCTIONS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
