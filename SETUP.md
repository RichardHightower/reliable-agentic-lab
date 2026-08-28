# Setup

Do this once before Saturday. The class stays on loop design, not environment
fights. Budget 15 minutes.

## Prerequisites

| Thing | Why | Check |
|---|---|---|
| Python 3.10 or newer | Labs 2-4 and the demo app | `python3 --version` |
| Git | Everything | `git --version` |
| Task | The command spine | `task --version` |
| `jq` | Module 1's plugin clone and `gh` scripting | `jq --version` |
| A GitHub account | Module 1's plugin polls a real issue; Module 4 needs one too | |
| A coding agent | Your labs. Any one of four. | |

Optional, and nothing is blocked without them: Docker, an API key for a model
provider, a Perplexity key, and a Langfuse account.

### Install task

```bash
brew install go-task            # macOS
npm install -g @go-task/cli     # any platform with Node
scoop install task              # Windows
```

Anything else: <https://taskfile.dev/installation/>

### Pick a coding agent

Claude Code, Codex, Grok Build, or OpenCode. One is enough, and the labs do not
care which. You can also fill labs 2-4 by hand.

## 1. clone

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab
```

A 404 means you are not a collaborator yet. Ping Rick.

## 2. Run setup

```bash
task setup
```

That creates `.venv`, installs dependencies, clones the demo target repository
into `work/`, and runs the verifier.

Windows without `make`-style tooling: the same steps run by hand are in
`Taskfile.yml`, one command per line.

## 3. verify

```bash
task test
```

That is extra credit plus a guard that the old shared `loops/` library stays
gone. If it fails on a fresh clone, tell Rick.

Then, if you want to see Module 2's answer run with no model key:

```bash
cd solutions/sol2_implementer
python implementer.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
```

You should see ten rubric rows, all passing, and `gate: pass`.

## 4. Secrets, all optional

`.env` is gitignored. Copy the example and fill only what you have.

```bash
cp .env.example .env
```

| Variable | Needed for | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Driving a live model | Labs 2-4 still run with `--doer reference`. Lab 1 needs an LLM. |
| `PERPLEXITY_API_KEY` | Module 3 research | Use `--backend websearch` or `--backend fixture`. You choose. |
| `GITHUB_TOKEN` | Module 4 pull requests | Modules 1 to 3 are fully offline. |
| `LANGFUSE_*` | Take-home observability | Local JSON traces are the fallback. |

Never commit a key. If you fork this repository, that includes your fork.

### The GitHub token, for Module 4 only

GitHub, **Settings**, **Developer settings**, **Personal access tokens**. Grant
**Contents**, **Issues**, and **Pull requests**. Paste it into `.env`.

## 5. On the day

Work from a lab folder, not the repo root:

```bash
cd labs/lab1_enhancer
```

See [labs/HOW-TO-RUN.md](labs/HOW-TO-RUN.md).

## Troubleshooting

**`task: command not found`.** Task is not installed. See above.

**`python: command not found`.** Use `python3`. Every command in this repo goes
through `task`, which already knows.

**`task test` fails on a fresh clone.** Tell Rick. That is a real bug and it
should not happen.

**The clone in `work/` is missing.** Run `task clone`.

**Your agent refuses to push.** That is the gate, working. Run `task test`, get
it green, and push again.
