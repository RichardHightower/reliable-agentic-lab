# Extra credit architecture

Trigger (Actions, ngrok, or a Droplet) -> one FastAPI `/github-webhook` -> same PRD loop -> log JSON -> comment or label -> exit.

`AGENT_BACKEND` picks python, claude, opencode, codex, grok, agent-sdk, or langgraph.
The entry point does not change.

Guardrails live on labels so concurrent workflows can see them.
The local board is the fallback when no token is set.
