# Extra credit instructions

Pass:

- `GET /health` names the backend and the `sol1_enhancer` path.
- Unsigned webhook posts return 401. Missing secret returns 503.
- `issues` opened with title `[T001]` runs
  `cd solutions/sol1_enhancer && task run -- --ticket T001`.
- That call is a subprocess. This package does not import `sol1_enhancer`.
- GitHub mode comments or labels, never loops past `AGENT_MAX_ATTEMPTS`.
- `agent-in-progress` is removed even when the run fails.
- `ngrok` exposes a public URL GitHub can POST to.
- A Droplet runs the same receiver behind Nginx.

Do not force-push student branches from Actions in this lab.
