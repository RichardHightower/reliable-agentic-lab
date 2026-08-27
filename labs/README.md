# Labs

Four labs, one per module. You fill one function or two in each. Everything
around them is written.

| Lab | Module | You build | You fill | Artifact |
|---|---|---|---|---|
| `lab1_enhancer` | 1 | Ticket Enhancer | `loop.py` | A working autonomous loop |
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
care. Every lab ships the same prompt for all four in `prompts/`.

See [HOW-TO-RUN.md](HOW-TO-RUN.md).

## Take-home

`takehome/` holds the same loops in the Claude Agent SDK and in LangChain Deep
Agents, both with Langfuse. Nobody is expected to finish these in five hours.
Some will try.

## If you fall behind

Stop typing and watch. Then copy the answer out of `solutions/sol<n>_<name>/`
into the lab folder and carry on with a working artifact. Every lab has a
`FALL-BEHIND.md` with the exact command.
