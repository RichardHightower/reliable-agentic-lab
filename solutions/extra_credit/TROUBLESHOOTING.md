# Extra credit troubleshooting

Workflow never fires: it is not on the instructor repo on purpose. Copy YAML to your fork.

404 on issues: collaborator access or wrong `GITHUB_REPO`.

Action loops: check `agent-in-progress` and `agent-attempts-N`. Lower `AGENT_MAX_ATTEMPTS`.

No model key: reference scripts do not need one. They reuse `solutions.loops`.

Webhook 503: set `GITHUB_WEBHOOK_SECRET`.
Webhook 401: GitHub secret and `.env` do not match.
ngrok URL changed: free URLs die on restart. Update the GitHub webhook.
Droplet 502: uvicorn is not on 127.0.0.1:8000 or Nginx proxy_pass is wrong.
