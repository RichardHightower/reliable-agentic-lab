---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol3_research_agent_sdk

Configuration port. Issue 119 twin. It does **not** run research.

No `brief.py`, `researcher.py`, `gates.py`, or tests. `task test` is `--table-only`.


---

# What it proves

```
role              writes  scope
orchestrator      no      nothing
researcher        no      nothing
writer            yes     brief.md, work/research/**
judge             no      nothing
```

```bash
cd solutions/sol3_research_agent_sdk
python loop.py --table-only
```

If judge prints `yes`, stop.

Researcher tools: Read, Glob, Grep, WebSearch.
Writer tools: Read, Glob, Grep, Edit, Write, Bash.
Judge tools: Read, Glob, Grep, Bash. No Edit, no Write.

`permission_mode="dontAsk"` (research is not unattended). `setting_sources=["project"]` so subagents inherit MCP servers.


---

# Recap

Same table as the Deep Agents research port. Enforcement is `tools=` plus PreToolUse. Pair with `sol3_research_deep_agents` when you want a brief on disk.
