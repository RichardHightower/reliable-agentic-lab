---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol3_research_deep_agents

The working filled Lab 3 loop.

LangChain's own Deep Agents quickstart is a research agent. This folder points that shape at the tool boundary.


---

# Layout

```
loop.py          wrappers around plan_questions / brief.check
researcher.py    the iteration loop, gates.decide
research.py      Backend.search. Fixture, WebSearch, Perplexity
brief.py         four arithmetic rows
gates.py         pass / retry / escalate
fixtures/research.json
tests/test_research.py
```


---

# Learning objectives

- Walk `researcher.run`
- Plug three backends behind one `search(question)`
- Enforce researcher has search, not write
- Fail ungrounded `[9]`
- Raise on the hard call cap


---

# Starting architecture

```
plan_questions → scholar.ask each sub-question
              → write_brief with [n]
              → strip_em_dashes
              → brief.check
              → gates.decide
```

`choose()` order: Perplexity if key, else WebSearch inbox, else fixture. Nothing is never an option.


---

# `plan_questions` and `write_brief`

```python
def plan_questions(question: str) -> list[str]:
    return [question, f"{question} common mistake", f"{question} how to verify"]
```

`write_brief` numbers unique citations, tags each finding paragraph `[n]`. Empty findings produce no body claims, so `has_sources` fails.


---

# `brief.check` four rows

```python
checks.append(BriefCheck("has_sources", bool(sources), ...))
checks.append(BriefCheck("grounded", not ungrounded, ...))
checks.append(BriefCheck("cited", not loose, ...))
checks.append(BriefCheck("style", dashes == 0, f"{dashes} em dashes"))
```

No model call. `signature()` is the sorted names of failed checks. That is the stable-failure key.


---

# Roles

Researcher: `read_file` + `search`. No write.
Writer: scoped to `brief.md`, `work/research/**`. Refusal is a string.
Judge: `read_file` only.
Orchestrator is not a subagent. Python owns the loop.


---

# Budget

```python
Budget(max_usd=0.20, max_calls=8, soft_usd=0.10)
```

Ninth call raises `BudgetExceeded`. Money over `max_usd` raises. Soft target only warns.

Live Perplexity: `cost_per_call=0.006`, available only if `PERPLEXITY_API_KEY`.


---

# Commands

```bash
cd solutions/sol3_research_deep_agents
python3 -m pytest tests -q
python3 loop.py --table-only
python3 loop.py --question "sqlalchemy nullable datetime column" --backend fixture
```


---

# Expected fixture output

```
PASS  has_sources    3 sources retrieved
PASS  grounded       every citation resolves
PASS  cited          every paragraph cites a source
PASS  style          0 em dashes
gate:    pass
reason:  the rubric is green
```

Exit: `0` if pass else `1`. Trace: `work/research/last-research.json` plus `brief.md`.


---

# Tests that pin the lesson

| Test | Asserts |
|---|---|
| `test_plan_questions_are_checkable` | first q is the question; some q contains `verify` |
| `test_ungrounded_citation_fails` | `[9]` fails |
| `test_budget_hard_cap` | second charge raises |
| `test_researcher_has_search_not_write` | judge tools `== ["read_file"]` |
| `test_no_loops_import` | no `from loops` |


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Shipped uncited brief | skipped empty-findings path | `has_sources` must fail |
| Researcher has write | tool list leaked | researcher tools: read + search |
| `task loop:research` missing | engine deleted | this `loop.py` |


---

# Recap

Isolated researcher context. Orchestrator sees a summary. Citations are arithmetic. Same exits as Module 2, pointed at a brief.
