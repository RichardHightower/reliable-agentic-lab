# How to run this solution

Everything here runs from `solutions/sol3_research_agent_sdk/`, standalone.

You need `python3` and `task`. A live run also needs an `ANTHROPIC_API_KEY`.
`task publish` also needs `gh` with the `gist` scope.

Python is the harness. The model plans, searches, verifies, and writes
sections. It does not assemble `paper.md` and it does not run the checks.

Saturday Lab 3 is `labs/lab3_research`. That lab fills `loop.py` and checks
with `task test`. This folder is the take-home white-paper port.

## One-time setup

Create the folder-local Python virtual environment, install the Claude
Agent SDK, and clone the diagram renderer. This does not modify Homebrew's
system Python.

```bash
task setup
```

Creates `.venv` in this folder. Homebrew Python will not let `pip` write to
the system interpreter (PEP 668). `task run` uses this venv. You do not
activate it.

Put the API key in the repo root `.env`, or export it in this shell.
Task loads `../../.env` first, then this folder's `.env`.

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
```

Perplexity is optional. Set `PERPLEXITY_API_KEY` the same way if you want
that server. Context7 is declared in this folder. A missing root `.mcp.json`
must not change the tool boundary.

## Scripts you can run without a model

```bash
task table
task checks
task test
task demo
```

`task demo` runs the recorded fixture. No key, no network. `task table`
prints the role table. The writer is the only role that prints `yes` in the
writes column.

## Live paper

```bash
task run --
TOPIC="your topic" task run --
task publish --
```

`task run` refuses if you skipped `task setup`. Cap it while you are
developing:

```bash
timeout 420 task run --
```

## Reset

```bash
task clean
```

Deletes `work/`. The renderer clone in `.cache/` stays.
