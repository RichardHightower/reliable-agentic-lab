# Prompt for Claude Agent SDK

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`loop.py` in this folder.

Rebuild the research loop as a Python white-paper pipeline on Claude Agent
SDK. The finished answer is `solutions/sol3_research_agent_sdk/`. Read its
[SPEC.md](../../../solutions/sol3_research_agent_sdk/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol3_research_agent_sdk/HOW_TO_RUN.md),
and [DESIGN_DOC.md](../../../solutions/sol3_research_agent_sdk/DESIGN_DOC.md).

Saturday Lab 3 fills two functions and checks with `task test`. This folder
is the take-home paper port. Do not copy these fences into this lab folder.

Python is the harness. The model plans, searches, verifies, and writes
sections. It does not assemble `paper.md` and it does not run the checks.

```bash
cd solutions/sol3_research_agent_sdk
claude
```

---

## Prompt 0: the things that will waste your hour

1. `task setup` creates `.venv`, installs the Agent SDK, and pins the local
   image plugins under `.cache/`. Do not `pip install` on Homebrew Python.
   `ClaudeAgentOptions.plugins` loads only `imagen-diagrams:imagen-diagrams`
   and `image-gen:image-gen`. It does not discover user or parent-project
   skills.
2. One PreToolUse hook for the whole cast. `{}` fails open. Deny needs the
   full `hookSpecificOutput` envelope.
3. Citations are arithmetic. A model that says "this is grounded" is not a
   check. `check_brief` counts.
4. `PERPLEXITY_API_KEY` is optional. Official-host allowlist still applies.

---

## Prompt 1: the role table

```
Create roleplan.py. Read the writes column. The judge and the researcher
write nothing. The writer owns brief.md and work/research/**.

task table. If the judge prints yes, stop.
```

---

## Prompt 2: the two fences and the paper pipeline

```
Translate the cast into ClaudeAgentOptions, one role at a time.

The paper pipeline is Python. Phases live in loop.py / paper.py. The model
fills a section. Python concatenates, cites, and gates.

Grounding, cost, and stopping are not left to a model's own judgment.
```

---

## Prompt 3: the brief check

```
Fill check_brief(body, sources). Citations are counts, not vibes.
A claim without a source is a fail. An em dash is a fail.
```

---

## Verify

```bash
cd solutions/sol3_research_agent_sdk
task setup
task table
task test
```

Live paper, with a key:

```bash
task run
task paper
```

See HOW_TO_RUN.md for `task brief`, `task publish`, and the gist scope.

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol3_research_agent_sdk/, behavior
first, wording second. I will decide what to change.
```
