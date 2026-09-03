---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol2_implementer_agent_sdk

The Lab 2 take-home driver on Claude Agent SDK. A ready ticket in. A green rubric out.

Python holds Pass, Retry, and Escalate. The Agent SDK is the maker. The red gate is `junit.xml`.

Saturday fills three stubs in `labs/lab2_implementer`. Demo T001 from here with `--doer reference` or `--doer sdk`.

Read `HOW_TO_RUN.md` and `DESIGN_DOC.md`. Skills are listed on `AgentDefinition`, not pasted.


---

# Two drivers, two fences

![h:420](images/driver-versus-cast.jpg)

Same eight-step loop as the Deep Agents twin. Enforcement here is one PreToolUse hook keyed by `agent_type`.


---

# What this folder is

| File | Role |
|---|---|
| `harness.py` | CLI, table, `--doer reference\|sdk\|none` |
| `implementer.py` | eight-step loop |
| `doers.py` | `none` / `reference` / Agent SDK |
| `rubric.py` / `gates.py` / `contract.py` | copies, not a library |
| `roles.py` | `ClaudeAgentOptions`, `skills=`, one hook |
| `plugin/skills/` | listed per writing role |

`task loop:implementer` is gone from the root Taskfile. Run `task run` here.


---

# Setup. Folder-local venv

```bash
cd solutions/sol2_implementer_agent_sdk
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup          # .venv + claude-agent-sdk. PEP 668.
task clone
```

Do not `pip install` into Homebrew Python. Do not activate the venv. Task uses it.


---

# Scripts with no model

```bash
task table          # judge writes must print no
task test           # pytest. No key, no SDK, no clone.
task e2e            # offline loop against a disposable fixture
```

If judge prints `yes`, stop. The port is wrong.


---

# Architecture

![h:360](images/sdk-two-fences.jpg)

`tools=[...]` decides whether a role can write. One PreToolUse hook decides which paths. Python still owns `implementer.run`.


---

# Scope. Two places, both required

`tools=[...]` decides whether a role can write at all.

One `PreToolUse` hook reads `agent_type` and looks up that role's scope.

A write with no agent is denied. The parent has no business writing anything.

Deny envelope:

```
hookSpecificOutput.hookEventName = PreToolUse
hookSpecificOutput.permissionDecision = deny
```

A typo fails **open**. The field is `maxTurns`, camelCase.


---

# Eight steps in `implementer.run`

1. Read the ticket. Refuse if it is still a draft.
2. `plan_for`: one test step and one code step per criterion. Derived, not generated.
3. `test_implementer` writes under `tests/**`.
4. Red gate. Empty new-ids → escalate. Stop. Do not write app code.
5. `code_implementer` writes `app/**` until green. Denied `tests/**`.
6. Ten-row rubric. No model.
7. Final judge. JSON `{done, summary, issues}`. Unparseable is `done=False`.
8. `gates.decide`. A retry carries the failed rows and the failing test ids. Receipt to `.harness/receipt.json`.

`query()` does not count retries.


---

# Three doers

| Spec | Needs | Behavior |
|---|---|---|
| `none` | nothing | writes nothing. Honesty check. |
| `reference` | clone | copies `known-good` inside WriteScope |
| `sdk` | `task setup` + key | Agent SDK makers |

```bash
task run -- --ticket T001 --doer none
task run -- --ticket T001 --doer reference
task run -- --ticket T001 --doer sdk
```

`task run` is `harness.py --repo <target>`. Extra flags after `--` go to `harness.py`.


---

# Live T001

`e2e_t001.py` is the operator path for `--doer sdk`. It builds
`AgentSdkPhaseBackend` in this folder and calls this folder's
`implementer.run`. `E2E_MAX_TURNS` is 12.

Do not invent a shared `loops/` package. Do not import the Deep Agents folder.

Read `E2E_PLAN.md` before spending a token.


---

# Plugin files vs Python

```
plugin/agents/...
plugin/skills/<role>/SKILL.md
```

The plugin is the readable specification. Python owns the options.
`AgentDefinition.skills` lists the role when the skill directory exists.
When an agent markdown file and the role table disagree, `options_for` raises.


---

# Troubleshooting

| Symptom | Fix |
|---|---|
| Judge writes `yes` | strip Write from judge tools |
| Fail-open writes | full `hookSpecificOutput` deny |
| `externally-managed-environment` | `task setup`, not system pip |
| `--doer sdk` refuses | `task setup` first |
| Copied into lab2 stub | Saturday wants three functions |
| `from loops` in a file | standalone test fails the build |


---

# Recap

Python owns the red gate and the three exits. The Agent SDK writes tests, then code.

Same table as Saturday. Enforcement is a tool list, plus one hook, plus Python on the outside.

If a port imports `loops`, the design leaked.
