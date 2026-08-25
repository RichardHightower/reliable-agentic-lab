# Setup

Do this once on a laptop before Saturday.

## Prereqs

- Python 3.11 or newer
- Git
- Docker Desktop if you want to boot the CRM in a container
- A GitHub account with Actions enabled
- Claude API key is optional for the reference loops. The graders run without it.

## Install

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r solutions/crm/requirements.txt
```

## Prove the machine

```bash
export PYTHONPATH="$PWD/solutions/crm"
pytest solutions/crm/tests solutions/m2-harness/graders solutions/m2-harness/tests solutions/m3-research/tests -q
```

All of those should pass on `main`.

## Optional keys

| Variable | Used by | Required to grade |
|---|---|---|
| `ANTHROPIC_API_KEY` | live Claude calls | No |
| `PERPLEXITY_API_KEY` | Module 3 live search | No. Fixture is the fallback. |
| `LANGFUSE_*` | cloud traces | No. Local JSON traces are the fallback. |

## Docs in every package

Each folder under `solutions/` has the same set:

- `README.md` what it is
- `SETUP.md` how to install just this piece
- `INSTRUCTIONS.md` how to run it and what pass looks like
- `ARCHITECTURE.md` the loop pieces
- `TROUBLESHOOTING.md` the failures we already hit
