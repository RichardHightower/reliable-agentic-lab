---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol3_research_deep_agents

The working filled Lab 3 loop. LangChain's own Deep Agents quickstart is a research agent. This folder points that shape at the tool boundary.


---

# Layout

```
loop.py          thin wrappers around researcher.plan_questions / brief.check
researcher.py    the iteration loop, gates.decide
research.py      Backend.search. Fixture, WebSearch, Perplexity
brief.py         four arithmetic rows
gates.py         pass / retry / escalate
fixtures/research.json
tests/test_research.py
```


---

# `researcher.run` (the loop)

For each iteration: `plan_questions` → `scholar.ask` each sub-question inside the budget → `write_brief` → `strip_em_dashes` → `brief.check` → `gates.decide`.

`choose()` order: Perplexity if key, else WebSearch inbox, else fixture. Nothing is never an option.

Researcher tools: `read_file` + `search`. No write.
Writer: scoped to `brief.md`, `work/research/**`. Refusal is a string.
Judge: `read_file` only.
Orchestrator is not a subagent. Python owns the loop.


---

# Commands

```bash
cd solutions/sol3_research_deep_agents
python3 -m pytest tests -q
python3 loop.py --table-only
python3 loop.py --question "sqlalchemy nullable datetime column" --backend fixture
```

Tests pin: plan questions are checkable, fixture cites, ungrounded `[9]` fails, hard cap raises, researcher has search not write, no `from loops`.


---

# Recap

Isolated researcher context. Orchestrator sees a summary, never the dump. Citations are arithmetic. Same exits as Module 2, pointed at a brief.
