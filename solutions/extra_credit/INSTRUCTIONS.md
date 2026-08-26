# Extra credit instructions

Pass:

- Local groom with `--incorporate` exits ready.
- Local fixer with `--maker reference` restores the hidden grader.
- `python solutions/extra_credit/webhook.py` serves `/health` and `/github-webhook`.
- Unsigned webhook posts return 401. Missing secret returns 503.
- GitHub mode comments or labels, never loops past `AGENT_MAX_ATTEMPTS`.
- `agent-in-progress` is removed even when the run fails.

Do not force-push student branches from Actions in this lab.
