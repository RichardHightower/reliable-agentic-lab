# Setup

Do this once before Saturday. The goal is a laptop that can clone, grade, and call a model.
Loop design comes after this page. Do not fight the environment during the first hour.

Repo: https://github.com/RichardHightower/reliable-agentic-lab
The repo is private. Rick adds attendees as collaborators. Fork it onto your account if you want a personal copy of issues and pull requests.

## Prerequisites

- A GitHub account
- Git
- Python 3.10 or newer. The Eventbrite page lists 3.11. Use 3.11 if you have it.
- A personal access token with access to this repository
- An API key for the model provider you will use (Anthropic, OpenAI, or equivalent)

Docker Desktop is optional. It boots the CRM in a container. Graders do not need it.

Claude, Codex, Cursor, or Gemini as a coding tool is the Saturday default.
The Agent Software Development Kit and LangGraph are optional tracks.

## 1. Clone or fork

Collaborator clone:

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab
```

Fork first on GitHub, then:

```bash
git clone https://github.com/<your-user>/reliable-agentic-lab.git
cd reliable-agentic-lab
```

If clone fails with 404, you do not have access yet. Ping Rick.

## 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

## 3. Install dependencies

Core (graders, CRM, local loops):

```bash
pip install -r requirements.txt
```

Optional SDKs if you fill a lab with Claude, OpenAI, or LangGraph:

```bash
pip install -r requirements-agents.txt
```

## 4. Configure secrets

`.env` is gitignored. Copy the example. Never commit keys.

```bash
cp .env.example .env
```

Edit `.env`:

```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=RichardHightower/reliable-agentic-lab
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

Fill the provider you actually use. Leave the others blank.
`scripts/verify_setup.py` loads `.env` without printing values.

If you forked, set `GITHUB_REPO` to `your-user/reliable-agentic-lab`.

## 5. GitHub token

1. GitHub, Settings, Developer settings, Personal access tokens.
2. Create a fine-grained token for `RichardHightower/reliable-agentic-lab`, or for your fork.
3. Grant repository permissions: Contents read and write, Issues read and write, Pull requests read and write.
4. Classic tokens may use the `repo` scope instead.
5. Paste the token into `.env` as `GITHUB_TOKEN`.

The class default is polling. Webhooks stay pinned for later.

## 6. Verify the setup

```bash
python scripts/verify_setup.py
```

The script checks:

- Python version
- Git on PATH
- Local CRM tickets on disk
- `.venv` and `.env` present
- GitHub token can list issues (if `GITHUB_TOKEN` is set)
- Anthropic or OpenAI can make one tiny call (if that key is set)

PASS on python, git, and tickets is enough for the hidden grader and the reference loops.
GitHub and model keys are required when you fill the live agent stubs.

Then prove the graders:

```bash
export PYTHONPATH="$PWD:$PWD/solutions/crm:$PWD/solutions/m2-harness"
pytest solutions/crm/tests solutions/m2-harness/graders solutions/m2-harness/tests solutions/m3-research/tests solutions/loops/tests -q
```

Those should pass on `main`.

## 7. Run the agents

Working examples (no model key):

```bash
python -m solutions.loops enhancer --ticket T001 --incorporate
python -m solutions.loops implementer --maker reference
python -m solutions.loops fixer --maker reference
```

Saturday labs are stubs. Open one folder under `labs/`. Paste one file from that folder's `prompts/` into Claude Code, the Agent SDK, or LangGraph.

| Lab | Stub | Working example |
|---|---|---|
| Module 1 implementer | `labs/m1-implementer` | `solutions/m1-implementer` |
| Module 2 harness | `labs/m2-harness` | `solutions/m2-harness` |
| Module 3 enhancer | `labs/m3-enhancer` | `solutions/loops/enhancer.py` |
| Module 4 fixer | `labs/m4-fixer` | `solutions/loops/fixer.py` |

If you stall: stop typing, watch Rick, copy from `solutions/`.

## Optional keys

| Variable | Used by | Required to grade |
|---|---|---|
| `GITHUB_TOKEN` | live GitHub polling | No. Local board is the fallback. |
| `ANTHROPIC_API_KEY` | Claude calls | No |
| `OPENAI_API_KEY` | OpenAI calls | No |
| `PERPLEXITY_API_KEY` | Module 3 live search | No. Fixture is the fallback. |
| `LANGFUSE_*` | cloud traces | No. Local JSON traces are the fallback. |

## Docs in every package

Each folder under `solutions/` and `labs/` has:

- `README.md` what it is
- `SETUP.md` how to install just this piece
- `INSTRUCTIONS.md` how to run it and what pass looks like
- `ARCHITECTURE.md` the loop pieces
- `TROUBLESHOOTING.md` the failures we already hit
