# reliable-agentic-lab

Working solutions for **Engineering Reliable Agentic AI Systems**.
Packt workshop. Saturday 29 August 2026. 10:00 to 15:00 Central.

Instructor: Rick Hightower.

Do not invent a new outline. This repo maps onto the locked four modules.

## Layout

```
solutions/crm              known-good CRM with due dates
solutions/tickets          markdown tickets, including the ready T001 contract
solutions/m1-implementer   one autonomous loop. Ready ticket to a graded change and a PR body.
solutions/m2-harness       Maker, Checker, rubric, hidden grader, quality gates, local traces.
solutions/m3-research      v3-shaped report loop. Perplexity or fixture. Fact-check. Style enforcer.
solutions/m4-production    unattended runner plus GitHub Actions
labs/                      exercises later. Empty until solutions pass.
```

No per-module branches. Solutions live in folders. Labs come after.

## Prove it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r solutions/crm/requirements.txt

# CRM + hidden grader
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/crm/tests solutions/m2-harness/graders -q

# Module 1 loop
python solutions/m1-implementer/loop.py

# Module 2 harness (already green on the known-good CRM)
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker none
pytest solutions/m2-harness/tests -q

# Module 3 report loop
python solutions/m3-research/loop.py
python solutions/m3-research/loop.py --dirty
pytest solutions/m3-research/tests -q

# Module 4 unattended
python solutions/m4-production/run_unattended.py --target m2
python solutions/m4-production/run_unattended.py --target m3
```

Boot the CRM:

```bash
cd solutions/crm
docker compose up --build
```

## What they take home

1. A running loop.
2. A reusable harness.
3. One MCP research assistant that writes a report, fact-checks it, and enforces style.
4. A production-ready Actions architecture.

Claude Agent SDK and LangChain Deep Agents are equivalent shapes for sub-agent scope.
This reference loop is Python-owned retries, rubrics, and stop rules so Saturday does not depend on a product tour.
