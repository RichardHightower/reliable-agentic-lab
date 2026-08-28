# Extra credit architecture

Trigger (Actions, ngrok, or a Droplet) starts one run. The loop decides when
to stop.

Assignment 2: GitHub -> ngrok -> `s_ext_2_ngrok/bin/webhook_trigger.py` ->
copied Lab 1 plugin (`task run -- --ticket Txxx`) -> comment or label -> exit.

A webhook may also land on FastAPI `/github-webhook` for the other extra
credit paths. `AGENT_BACKEND` picks python, claude, opencode, codex, grok,
agent-sdk, or langgraph when that receiver is in play.

Guardrails live on labels so concurrent workflows can see them.
The local board is the fallback when no token is set.
