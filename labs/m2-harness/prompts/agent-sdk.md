# Prompt for the Claude Agent Software Development Kit (SDK)

Create two sub-agents with scoped tools.

Maker tools: read CRM, write the five due-date files, run pytest.
Checker tools: read diff, read pytest output, read the ready ticket. No write tools.
Orchestrator tools: run the loop, hold the budget, read summaries.

Python, not the model, must own pass / retry / escalate.
Land the code in `labs/m2-harness/harness.py` so it still runs if the SDK is missing.
Forbidden: edit graders, merge, deploy, change ticket labels.
