# Prompt for the Claude Agent Software Development Kit (SDK)

Sub-agent: researcher. Tools: read CRM repo, read ticket, optional one external doc.
Sub-agent: editor. Tools: write a ticket comment. No label tool.
Orchestrator: may apply the ready label only after the editor produced a testable contract.

Budget: three loops. Cost each tool call. Stop on ready, repeat missing-fields, or budget.

Land a no-key fallback in `labs/m3-enhancer/loop.py` that uses the gold ready ticket.
