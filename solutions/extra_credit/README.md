# Extra credit. Event-driven agents

Not Saturday. Polling stays the class default.

Working wrappers around the Ticket Enhancer and PR Fixer.
GitHub Actions is the trigger. Same loop, same exit criteria.

- `groom_ticket.py` issue opened or labeled
- `fix_pr.py` failed check suite
- `webhook.py` one FastAPI entry point for ngrok or a Droplet
- Guardrails: `agent-in-progress`, `agent-attempts-N`, lock files, `AGENT_MAX_ATTEMPTS`
