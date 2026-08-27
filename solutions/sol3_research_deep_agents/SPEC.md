# Spec. Lab 3. Research assistant on LangChain Deep Agents

A question in, a cited brief out. LangChain's own Deep Agents quickstart is a
research agent. This folder is that shape pointed at our tool boundary.

## Cast

orchestrator, researcher, writer, judge.

Researcher: search only. Isolated context. Writer: `brief.md` only. Judge:
`check_brief` in Python. Citations are arithmetic.

## Tool boundary

One function. Three backends. The loop cannot tell which one answered.

- context7 / Perplexity when a key exists
- the agent's WebSearch
- `fixtures/research.json` when the room has no wifi

Cannot merge, deploy, or edit the CRM.

Three exits: brief grounded; search budget spent; no source found, escalate.

## Run

```bash
cd solutions/sol3_research_deep_agents
python3 -m pytest tests -q
python3 loop.py --table-only
python3 loop.py --question "sqlalchemy nullable datetime column" --backend fixture
```

Saturday still fills `plan_questions` and `check_brief` in the lab folder.
