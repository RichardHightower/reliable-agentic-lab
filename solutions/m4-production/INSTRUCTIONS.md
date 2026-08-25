# Module 4 instructions

Teach what changes when no human is at the keyboard.

```bash
python solutions/m4-production/run_unattended.py --target m2
cat solutions/m4-production/state.json
```

State holds ticket, branch, last score, and `human: false`.

## Talking points

- Unattended state.
- Observability. Traces must exist or you cannot debug at 2am.
- Budget still applies. A hung agent is a cost incident.
- How to swap CRM tasks for their own backlog.

## Do not

- Do not start a second product.
- Do not require Langfuse cloud. Local JSON is enough to ship.
