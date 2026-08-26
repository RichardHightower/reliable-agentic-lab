# Extra credit. Event-driven agents

Not Saturday. Polling stays the class default.

Working wrappers around the Ticket Enhancer and PR Fixer.
GitHub Actions is the trigger. Same loop, same exit criteria.

- `groom_ticket.py` issue opened or labeled
- `fix_pr.py` failed check suite
- Guardrails: `agent-in-progress`, `agent-attempts-N`, `AGENT_MAX_ATTEMPTS`
