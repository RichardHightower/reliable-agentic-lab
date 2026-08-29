---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_agent_sdk

Take-home. Python owns the loop. The model drafts and grades. It does not write files. It does not run `/enhancer-loop`.

Saturday live path is `solutions/sol1_enhancer`. Do not copy these fences into that folder.

Read `HOW_TO_RUN.md` and `DESIGN_DOC.md`.


---

# Setup. Folder-local venv

```bash
cd solutions/sol1_enhancer_agent_sdk
cp config.json.example config.json
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup          # .venv + claude-agent-sdk. PEP 668.
task clone
task create-test-tickets
```

Do not `pip install -r ../../requirements-takehome.txt`. Homebrew Python will refuse.


---

# Scripts with no model

```bash
task table          # judge writes must print no
task checks
task test           # pytest. No key, no clone, no SDK.
```

If judge prints `yes`, stop. The port is wrong.


---

# Architecture

![h:340](images/sdk-two-fences.jpg)

Python writes the candidate and runs the checks. A typo in the deny envelope fails **open**.

See `docs/diagrams/architecture.svg`.


---

# One poll

```bash
timeout 420 task run --
task run -- --quiet
task poll-forever --
```

A first poll is three model calls: judge, doer, judge again. Cap it while you develop.

Hung queries dump to `.harness/last-doer-T<id>.md`. Cap is 180 seconds.


---

# Scope. Two places, both required

1. `tools=[...]`. `NO_WRITE` strips Edit, Write, Bash.
2. `PreToolUse` hook `roles.scope_hook`. Empty `{}` = allow. Deny must be `hookSpecificOutput` with `permissionDecision: deny`.

Parent session: `allowed_tools=["Agent"]`. `permission_mode` is not chatting. Python already owns the loop.


---

# Testing skill. Same ritual as Claude Code

`.agents/skills/test-sol1-ticket-enhancer/`

```bash
task reset-test-tickets
task create-test-tickets
task run --
```

Review live issues. Post exact `LGTM`. Next poll: `state: ready`, `loop: implementer`.


---

# Troubleshooting

| Symptom | Fix |
|---|---|
| Judge writes `yes` | strip Write with `NO_WRITE` |
| `externally-managed-environment` | `task setup`, not system pip |
| Hang, no output | read `.harness/last-doer-T<id>.md` |
| Closed issue | `task reset-test-tickets` |


---

# Recap

Python holds the loop. The model only drafts and grades.

`task setup`, `task table`, `task test`, `task run`. Read `HOW_TO_RUN.md`.
