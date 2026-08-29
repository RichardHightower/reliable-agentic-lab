# Labs

Four labs, one per module. You fill one function or two in each. Everything
around them is written.

| Lab | Module | You build | You fill | Artifact |
|---|---|---|---|---|
| `lab1_enhancer` | 1 | Ticket Enhancer | a Claude Code plugin (`.claude/agents`, `.claude/skills`) | A working autonomous loop |
| `lab2_implementer` | 2 | The harness | `harness.py` | A reusable evaluation harness |
| `lab3_research` | 3 | Research assistant | `loop.py` | A cited research brief |
| `lab4_fixer` | 4 | Broken PR Fixer | `loop.py` | A production architecture |

Module 2 is the centre. If time runs short anywhere, it is not there.

## Work from the lab folder

```bash
cd labs/lab2_implementer
```

Your agent runs here, not at the repo root. Each lab folder is its own Claude
Code project: it has a `.claude/` with the tool scope for that lab, and a
`Taskfile.yml` that reaches the root spine, so `task test` works.

## Pick one tool

Claude Code, Codex, Grok Build, or OpenCode. You choose, and the lab does not
care. Every lab ships the same four Saturday prompts in `prompts/`. Lab 1 also
ships take-home prompts for Claude Agent SDK and LangChain Deep Agents. Labs
2 to 4 ship those two as well, pointed at the standalone solution folders,
not at the Saturday stub.

See [HOW-TO-RUN.md](HOW-TO-RUN.md).

## Take-home

`takehome/` holds a fill-`loop.py` stub of the Module 2 implementer in the
Claude Agent SDK and in LangChain Deep Agents, both with Langfuse. Nobody is
expected to finish these in five hours. Some will try.

Each lab also ships `prompts/agent-sdk.md` and `prompts/deep-agents.md` for
the full standalone port of that module. Those prompts point at
`solutions/sol*_agent_sdk/` and `solutions/sol*_deep_agents/`.

## If you fall behind

Stop typing and watch Rick. Save your attempt. Labs 2 to 4 have no drop-in
answer. Copy only Lab 1's `.claude/` tree. See each lab's `FALL-BEHIND.md`.
