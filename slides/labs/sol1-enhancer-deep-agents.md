---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol1_enhancer_deep_agents

Take-home. Deep Agents. Python is the harness. The model drafts and grades.

Saturday live path is `solutions/sol1_enhancer`. Do not copy these fences into that folder.

Read `HOW_TO_RUN.md` and `DESIGN_DOC.md`. Skills are mounted, not pasted.


---

# Setup

```bash
cd solutions/sol1_enhancer_deep_agents
cp config.json.example config.json
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup          # .venv + deepagents>=0.7
task clone
task create-test-tickets
```


---

# Scripts with no model

```bash
task table          # judge writes must print no
task checks
task test
```

If judge prints `yes`, stop.


---

# Three fences

![h:340](images/da-three-fences.jpg)

Layer 3 is the one people skip. Leaving the default subagent on is how a scoped agent writes anywhere.

See `docs/diagrams/architecture.svg`.


---

# One poll

```bash
timeout 420 task run --
task run -- --ticket T001
task run -- --ticket T001 --simulate-comment LGTM
task poll-forever --
```

`--simulate-comment` needs `--ticket`. First poll is three model calls.

`task run` is `python3 loop.py --once --repo <target>`. Extra flags after `--` go to `loop.py`.


---

# Skills, not a stuffed prompt

```
skills/doer/SKILL.md
skills/judge/SKILL.md
```

Deep Agents loads the body when the role is invoked. Do not paste `SKILL.md` into a subagent prompt.


---

# Testing skill

`.agents/skills/test-sol1-ticket-enhancer/`

```bash
task reset-test-tickets
task create-test-tickets
task run --
```

Same GitHub + `LGTM` ritual as the Claude Code answer.


---

# Troubleshooting

| Symptom | Fix |
|---|---|
| Judge writes `yes` | no write tool on the judge |
| Agent writes anywhere | turn the general-purpose subagent off |
| Skill not loading | do not shadow `read_file` with a custom tool |
| No key | `task table` and `task test` still run |


---

# Recap

Three fences. Skills mounted. Python holds the loop.

Saturday still lives in `solutions/sol1_enhancer`.
