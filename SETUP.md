# Setup

Do this once before Saturday. The class stays on loop design, not environment
fights. Budget 15 minutes.

## Prerequisites

| Thing | Why | Check |
|---|---|---|
| Python 3.10 or newer | The loops and the demo app | `python3 --version` |
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
care which. You can also do every lab by hand, because the loops run with no
model key at all.

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

129 checks. All of them should pass. If they do not, you have found something
worth telling Rick about before Saturday.

Then confirm the loops run with no key:

```bash
task loop:implementer -- --repo work/northwind-field-crm --ticket T001 --doer reference
```

You should see ten rubric rows, all passing, and `gate: pass`.

## 4. Secrets, all optional

`.env` is gitignored. Copy the example and fill only what you have.

```bash
cp .env.example .env
```

| Variable | Needed for | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Driving a loop with a model | Use `--doer reference`. Everything still runs. |
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
