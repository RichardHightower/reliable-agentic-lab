# Prompt for the Claude Agent Software Development Kit (SDK)

Build a one-shot Ticket Implementer with the Agent SDK.

Tools the agent may have:

- read the ready ticket
- read and write files under the work CRM copy only
- run pytest on `solutions/m2-harness/graders/test_due_date_contract.py`

Tools the agent must not have:

- edit graders
- change ticket state
- merge
- deploy

Stop after one passing pytest run or a max of three attempts.
Land the orchestration in `labs/m1-implementer/loop.py` so the class can run it without the SDK if the key is missing.

Reference working loop: `solutions/m1-implementer/loop.py`.
