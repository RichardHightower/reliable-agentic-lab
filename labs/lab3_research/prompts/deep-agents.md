# Prompt for LangChain Deep Agents

Take-home. Saturday is [prompts/claude-code.md](claude-code.md), which fills
`loop.py` in this folder.

Rebuild the research loop as a Python white-paper pipeline on LangChain Deep
Agents. The finished answer is `solutions/sol3_research_deep_agents/`. Read
its [SPEC.md](../../../solutions/sol3_research_deep_agents/SPEC.md) and
[DESIGN_DOC.md](../../../solutions/sol3_research_deep_agents/DESIGN_DOC.md).
This port has no `HOW_TO_RUN.md`. The Taskfile and the spec are the operator
docs.

Do not copy these harness fences into this lab folder.

Python is the harness. The model plans, searches, verifies, diagrams, and
writes sections. It does not assemble `paper.md` and it does not run the
checks.

Needs `deepagents>=0.7`.

```bash
cd solutions/sol3_research_deep_agents
claude
```

---

## Prompt 0: the things that will waste your hour

1. Three fences, all required. Turn the default `general-purpose` subagent
   off. Leaving it on is how a scoped agent writes `paper/**` from the
   reviewer.
2. Skills are mounted, not pasted: planner, researcher, verifier, diagrammer,
   writer, reviewer. Do not paste `SKILL.md` into a subagent prompt.
3. Nine stages, three exits. Stage gates live in `stages.py`. A model cannot
   skip a gate by sounding done.
4. Citations are arithmetic. Official-host allowlist in `source_policy.py`.
5. `task setup` creates `.venv`. Homebrew Python will refuse system pip.

---

## Prompt 1: the role table

```
Create roleplan.py. The paper cast:

orchestrator  no      nothing
planner       yes     plan.json
researcher    no      nothing
verifier      yes     evidence/**   (denied: paper/**)
diagrammer    yes     diagrams/*.mmd, diagrams/*.puml
writer        yes     brief.md, paper/**, work/research/**
reviewer      no      nothing

task table. If the reviewer prints yes, stop.
```

---

## Prompt 2: the three fences

```
Create roles.py. Tool list per subagent. Path check inside each write tool.
Harness profile hides write_file / edit_file / delete / execute on the
orchestrator and turns general-purpose off.

FilesystemBackend(virtual_mode=True). Resolve paths before a custom tool
touches disk. .. is an escape, not a glob.
```

---

## Prompt 3: the paper pipeline

```
Nine stages in paper.py. Each stage has a gate in stages.py.
Grounding, cost, and stopping are computed. The model does not get a vote
on those.

A claim without a source is a fail. An em dash is a fail.
```

---

## Verify

```bash
cd solutions/sol3_research_deep_agents
task setup
task table
task test
```

Live paper, with a key: `task run` and the paper targets in the Taskfile.
See SPEC.md.

## Prompt 4: compare against the answer

```
Diff what I built against solutions/sol3_research_deep_agents/, behavior
first, wording second. I will decide what to change.
```
