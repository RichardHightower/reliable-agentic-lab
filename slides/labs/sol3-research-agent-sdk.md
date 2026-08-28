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

If judge prints `yes`, stop.

Pair with `sol3_research_deep_agents` when you want a brief on disk.


---

# Learning objectives

- Read `LOOPS["research"] = (orchestrator, researcher, writer, judge)`
- Give researcher `WebSearch`, not Write
- Give writer `brief.md` and `work/research/**`
- Use `permission_mode="dontAsk"` (research is not unattended)


---

# Starting architecture

```
python loop.py --table-only
  └── four RolePlans

python loop.py
  └── ClaudeAgentOptions
         researcher: Read, Glob, Grep, WebSearch
         writer:     Edit, Write, Bash plus reads
         judge:      Read, Glob, Grep, Bash
         PreToolUse on writer
```


---

# Scope

`tools=[...]` decides whether a role can write.

`scope_hook` decides which paths. Full deny envelope. A typo fails open.

`setting_sources=["project"]` so subagents inherit MCP servers. `max_turns=12` per subagent.


---

# Commands

```bash
cd solutions/sol3_research_agent_sdk
python loop.py --table-only
python loop.py
task test
```

No SDK, no key, no clone for `--table-only`.


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Expected a brief.md | config port | Deep Agents folder runs the loop |
| Judge writes `yes` | tools leaked | strip Edit/Write |
| MCP missing on subagent | forgot setting_sources | `["project"]` |


---

# Validation

- [ ] table: writer yes, everyone else no
- [ ] researcher tools include WebSearch
- [ ] judge tools exclude Edit and Write
- [ ] you can name the folder that writes `brief.md`


---

# Recap

Same table as the Deep Agents research port. Enforcement is `tools=` plus PreToolUse. This folder does not produce a brief.

---

# Prerequisites

```bash
cd solutions/sol3_research_agent_sdk
python loop.py --table-only
```

`DEFAULT_LOOP` in this copy of `roleplan.py` is `"implementer"`. `loop.py` overrides with `LOOP = "research"`. If you call `plan(contract)` without that override you get the wrong cast.

---

# Files in this folder

```
SPEC.md  Taskfile.yml
adapter.py  loop.py
roleplan.py  roles.py  write_scope.py
```

Missing on purpose: `brief.py`, `researcher.py`, `research.py`, `gates.py`, `fixtures/`, `tests/`.

---

# Writer scope vs researcher scope

Researcher is in `READERS`. Tools: Read, Glob, Grep, WebSearch. Writes nothing.

Writer fallback: `brief.md`, `work/research/**`. That is `FALLBACK_SCOPE` because a CRM `.loop.yml` has never heard of a writer.

Judge: Read, Glob, Grep, Bash. No Edit. No Write.

---

# Final checklist

- [ ] table: writer yes, researcher no, judge no
- [ ] `LOOP = "research"` in `loop.py`
- [ ] `permission_mode` is `dontAsk`, not `acceptEdits`
- [ ] live brief comes from `sol3_research_deep_agents`
