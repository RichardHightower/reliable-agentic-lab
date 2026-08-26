# Extra credit troubleshooting

Workflow never fires: it is not on the instructor repo on purpose. Copy YAML to your fork.

404 on issues: collaborator access or wrong `GITHUB_REPO`.

Action loops: check `agent-in-progress` and `agent-attempts-N`. Lower `AGENT_MAX_ATTEMPTS`.

No model key: reference scripts do not need one. They reuse `solutions.loops`.
