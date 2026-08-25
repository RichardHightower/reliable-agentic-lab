# Instructions

Work from the repo root. Activate `.venv` first. See `SETUP.md`.

Solutions are the instructor reference. Labs stay empty until these stay green.
Talk track lives in `slides/`. Marp decks plus narrative notes. Same images.

## Order

1. `solutions/crm` boots and the hidden grader is green.
2. `solutions/m1-implementer` turns a starter CRM into a passing due-date change.
3. `solutions/m2-harness` wraps that loop with Maker, Checker, rubric, and gates.
4. `solutions/m3-research` writes a report, fact-checks it, and enforces style.
5. `solutions/m4-production` runs the same stack unattended.

## Sessions

| Session | Deck | Notes |
|---|---|---|
| 1 System Architecture | [slides.md](slides/session-1-system-architecture/slides.md) | [notes.md](slides/session-1-system-architecture/notes.md) |
| 2 Harness Engineering | [slides.md](slides/session-2-harness-engineering/slides.md) | [notes.md](slides/session-2-harness-engineering/notes.md) |
| 3 Research Loops and MCP | [slides.md](slides/session-3-research-loops-mcp/slides.md) | [notes.md](slides/session-3-research-loops-mcp/notes.md) |
| 4 Production Architecture | [slides.md](slides/session-4-production-architecture/slides.md) | [notes.md](slides/session-4-production-architecture/notes.md) |

Feature order: [slides/FEATURE-MAP.md](slides/FEATURE-MAP.md).

## One-liners

```bash
# CRM
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/crm/tests solutions/m2-harness/graders -q
cd solutions/crm && docker compose up --build

# Module 1
python solutions/m1-implementer/loop.py

# Module 2
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker none
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker reference

# Module 3
python solutions/m3-research/loop.py
python solutions/m3-research/loop.py --dirty

# Module 4
python solutions/m4-production/run_unattended.py --target m2
python solutions/m4-production/run_unattended.py --target m3
```

Open the package `INSTRUCTIONS.md` for the talking points and stop rules.
