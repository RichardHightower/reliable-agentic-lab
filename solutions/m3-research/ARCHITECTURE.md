# Module 3 architecture

v3 shape. Smaller surface.

```
topic
  -> researcher (MCP or fixture)     cost += 1
  -> writer draft                    cost += 1
  -> FACT editor/checker loop        stop: pass, max loops, budget, repeat
  -> strip em dashes (deterministic)
  -> STYLE editor/checker loop       same stop rules
  -> work/last-loop.json
```

Checker never writes the report.
Editor never marks the loop passed.

Claude Agent SDK and LangChain Deep Agents are equivalent runtimes
for this graph. The reference loop is Python so the retry count is real.
