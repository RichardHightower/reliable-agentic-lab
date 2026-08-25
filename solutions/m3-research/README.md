# Module 3 solution: research report loop

Mimic of Spillwave articles v3. Output is a short report, not a Medium article.

1. Research via Perplexity MCP, or a local fixture if the key is missing.
2. Draft the report. Research stays in a sub-agent. Orchestrator sees a summary.
3. Fact-check loop against a rubric. Checker has no write tools.
4. Style-guide enforcer loop. Deterministic em-dash strip, then rubric.
5. Exit on passing grade, max loops, or max budget.

```bash
python -m solutions.m3_research  # hyphen path, use:
python solutions/m3-research/loop.py
pytest solutions/m3-research/tests -q
```
