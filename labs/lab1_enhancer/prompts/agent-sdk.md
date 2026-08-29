# Prompt for Claude Agent SDK

Take-home. Saturday is [prompts/claude-code.md](claude-code.md).

Build the ticket enhancer as a Python loop on Claude Agent SDK. The finished
answer is `solutions/sol1_enhancer_agent_sdk/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_agent_sdk/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol1_enhancer_agent_sdk/HOW_TO_RUN.md), and
[DESIGN_DOC.md](../../../solutions/sol1_enhancer_agent_sdk/DESIGN_DOC.md)
before you type.

Python owns discovery, GitHub, the candidate file, and the exits. The model
drafts and grades. It does not write files. It does not run `/enhancer-loop`.

Work from the answer folder, or paste into `claude` from this lab folder.

```bash
cd solutions/sol1_enhancer_agent_sdk
# or: cd labs/lab1_enhancer && claude
```

Interactive: run `claude` and paste each prompt below in turn.

Do not copy these fences into `solutions/sol1_enhancer/`. That folder is the
Saturday Claude Code plugin.

---

## Prompt 0: the things that will waste your hour

Learn these before you build anything. Each one fails silently.

1. Homebrew Python will refuse `pip install` (PEP 668). `task setup` creates
   `.venv` in this folder and installs `claude-agent-sdk` there. Do not
   `pip install -r requirements-takehome.txt` on the system interpreter.
2. The Agent SDK scopes in two places and you need both. `tools=[...]`
   decides whether a role can write at all. A `PreToolUse` hook decides which
   paths it may write. Drop either one and the judge can grade itself, or a
   leaked Write can reach `app/`.
3. Returning `{}` from the hook means "no opinion", which lets the call
   through. A typo in the deny envelope fails **open**. Deny must be the full
   `hookSpecificOutput` shape with `permissionDecision: deny`.
4. The doer holds no `Write`. Python writes
   `tickets/<id>.enhancer-candidate.md`. Matching the Claude Code plugin.
5. The parent session may only spawn a subagent: `allowed_tools=["Agent"]`.
   If the parent can Write, the whole jail is decoration.

---

## Prompt 1: the role table

```
Create roleplan.py and loop.py --table-only.

The enhancer cast is orchestrator, doer, judge. That list lives in
roleplan.py. Do not restate a scope anywhere else.

The judge holds no write tool. The doer's fallback scope is tickets/**.
The orchestrator writes nothing.

loop.py --table-only must run with no SDK, no API key, and no clone.
Print the role table. The judge must print no in the writes column.
If it prints yes, stop. Nothing downstream is worth building on that.
```

Run it:

```bash
task table
```

---

## Prompt 2: the two fences

```
Create roles.py.

tools=[...] decides whether a role can write at all. Strip Edit, Write,
NotebookEdit, and Bash from the judge with a NO_WRITE list. Bash is how a
Read-only agent writes anyway.

A PreToolUse hook decides which paths a writer may touch. One hook for the
whole cast, not one per role. It reads agent_type off the tool call and looks
up that role's scope. A write with no agent_type came from the parent, and
the parent has no business writing.

Deny with this exact envelope, nothing less:

{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "<role> may write <allow>. <path> is outside that scope."
  }
}

Returning {} lets the call through. tests/test_roles.py must assert the deny
shape key by key, with no SDK installed.

The parent ClaudeAgentOptions uses allowed_tools=["Agent"] and loads the
plugin from plugin/ because cwd is the CRM, not this folder.
```

---

## Prompt 3: the deterministic half

```
Create check_fields.py and check_stop.py.

check_fields.py reads {"kind", "present_fields"} and prints
{"kind", "present_fields", "missing_fields", "ready"}. It computes
missing_fields from its own rubric table. It does not trust a model's
missing_fields.

Bug needs title, steps, expected, actual, environment.
Feature needs problem, proposal, value, criteria.
UI needs those four plus a wireframe.

check_stop.py reads {"round", "budget", "signature", "previous_signature"}
and prints {"stop", "reason"}. stop is true when the signature repeats
(not the first round), or when round + 1 reaches budget.

Both take a CLI argument or stdin. Both have --demo with asserts.
A stop condition written as prose is a stop condition a model can talk
itself past.
```

Run them: `task checks`

---

## Prompt 4: the Python orchestrator

This is the real design work. `enhancer.py` is Python, not a skill.

```
Create enhancer.py. It is the orchestrator: the only role that writes the
real ticket file or talks to GitHub. It runs one poll-and-act step and
exits. Repeated polling is task poll-forever, external to this module.

The model is called only as judge and doer. Python writes the candidate,
runs the checks, and applies labels.

Read config.json for {fork_owner, repo_name}. Every gh call targets that
repo.

Without --ticket, list open GitHub issues. A UI-created issue is a ticket.
Write a local draft if one is missing. Keep every tickets/*.md with
state: draft and loop: enhancer. Skip *.ready.md and
*.enhancer-candidate.md.

Persist state per ticket in .harness/last-enhancer-<id>.json:
{github_issue, last_comment_id, round, previous_signature}.

The step, per ticket:
1. Find the ticket's GitHub issue. Never create one. Creating tickets is
   task create-test-tickets. Lookup order: state file, then ticket
   frontmatter, then a title search across all states. Do not search
   --state open. If the issue is closed, stop and say so. If none of the
   three found anything, stop and say to run task create-test-tickets.
2. Look at the newest human comment only for exact LGTM. Comments never
   start an enhance round. Add the enhanced label the first time this
   loop touches the ticket.
3. Issue already carries needs-human: stop, wait for a person.
4. Judge the current ticket, then check_fields.py, to get this round's
   kind, missing_fields, and ready. LGTM must never skip this.
5. Comment is exactly LGTM and the ticket is already ready: set
   state: ready, swap enhanced for ready, delete the state file, done.
   LGTM on a ticket that is not yet ready finalizes nothing.
6. Ticket is already ready but the comment was not LGTM: post a comment
   saying it looks ready and is waiting for LGTM, stop, do not call the
   doer.
7. Otherwise: call the doer. Python writes the candidate file. Judge that
   file the same way. Only if the candidate's missing_fields is a strict
   improvement, replace the real ticket. Post one issue comment either way.
8. Run check_stop.py. Do not compare signatures yourself. stop is true:
   add needs-human, stop. stop is false: persist the updated state,
   including the comment id this poll used.
```

---

## Prompt 5: the plugin agents

```
Create plugin/agents/enhancer-judge.md and plugin/agents/enhancer-doer.md.
Same files as the Claude Code plugin. The SDK loads them with plugins=
because cwd is the CRM.

The judge: Read, Grep, Glob only. Final message is one JSON object:
{"kind": "...", "present_fields": [...]}. No ready. No missing_fields.

The doer: draft a full replacement ticket body as text. No write tool.
Python writes the candidate after.

Do not paste SKILL.md into a subagent prompt. The skill is not invoked.
Python is the harness.
```

---

## Prompt 6: Taskfile and tests

```
Give the folder task setup, task table, task checks, task test,
task clone, task create-test-tickets, task reset-test-tickets,
task run, and task poll-forever.

task setup creates .venv and installs claude-agent-sdk plus pytest.
task table, task checks, and task test need no SDK, no key, and no clone.
The tests stub claude_agent_sdk in sys.modules.

Pin: judge holds no write tool; cast() returns the shared table; the
PreToolUse deny envelope is complete; a path outside the target repo is
denied; a missing SDK reports a failed result, never a write it did not
make.
```

---

## Verify

```bash
cp config.json.example config.json   # fill in your GitHub username
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup
task table          # judge writes must print no
task checks
task test
task clone
task create-test-tickets
timeout 420 task run --
```

A first poll is three model calls: judge, doer, judge again. Cap it while
you develop.

Hung queries dump to `.harness/last-doer-T<id>.md`.

---

## Prompt 7: compare against the answer

```
Diff what I built against solutions/sol1_enhancer_agent_sdk/, field by
field and step by step, not just the raw text. Tell me where they differ
in behavior, not just wording, and for each difference, whether it is a
real gap or a legitimate different choice. I will decide what to change.
```

## If you fall behind

[FALL-BEHIND.md](../FALL-BEHIND.md) has the run commands for this runtime.
The answer is the folder. Reading it costs you nothing.
