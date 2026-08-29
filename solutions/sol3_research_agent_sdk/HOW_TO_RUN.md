# How to run this solution

Everything here runs from `solutions/sol3_research_agent_sdk/`, standalone.

You need `python3` and `task`. A live run also needs an `ANTHROPIC_API_KEY`.
`task publish` also needs `gh` with the `gist` scope.

Python is the harness. The model plans, searches, verifies, and writes
sections. It does not assemble `paper.md` and it does not run the checks.

Saturday Lab 3 is `labs/lab3_research`. That lab fills `loop.py` and checks
with `task test`. This folder is the take-home white-paper port.

## One-time setup

Create the folder-local Python virtual environment, install the Claude Agent
SDK, and install the pinned image plugins. This does not modify Homebrew's
system Python or `~/.claude`.

```bash
task setup
```

Creates `.venv`, `.cache/imagen-diagrams` at v0.2.0, and `.cache/image-gen` at
v2.1.0 in this folder. `ClaudeAgentOptions.plugins` loads both local manifests,
and its exact skill allowlist exposes only `imagen-diagrams:imagen-diagrams`
and `image-gen:image-gen`. It does not discover user or parent-project skills.
Homebrew Python will not let `pip` write to the system interpreter (PEP 668).
`task run` uses this venv. You do not activate it.

Put the API key in `.env`, `../.env`, `../../.env`, or `../../../.env`, or
export it in this shell. The closest dotenv file wins. Direct `python loop.py`
runs use the same nearest-first lookup for `PERPLEXITY_API_KEY`.

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
```

Perplexity is optional. Set `PERPLEXITY_API_KEY` the same way if you want
that server. This port launches Perplexity's official MCP package locally; its
researcher starts with filtered `perplexity_search`, and may use one filtered
`perplexity_ask` fallback only when search results contain no usable excerpt.
The Python source wall admits the documented official-host allowlist only.
When Perplexity is unavailable the Agent SDK researcher may use Anthropic
`WebSearch` and the same post-filter; with no live provider, select the
recorded fixture. This port has no OpenAI or Bing fallback. Context7 is
declared in this folder. A missing root `.mcp.json` must not change the tool
boundary.

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

## White-paper acceptance runs

The two E2E lanes both build an illustrated paper on loop-engineering best
practices and leave `paper.md` plus `e2e-report.json` under `work/`.

```bash
task e2e-fixture
```

This uses a recorded primary-source corpus but the installed
[`imagen-diagrams`](https://github.com/SpillwaveSolutions/imagen-diagrams)
v0.2.0 renderer and fidelity judge. That plugin alone turns `.mmd` or `.puml`
source into the paper's `*_imagen.png` diagrams. The separately installed
[`image-gen`](https://github.com/SpillwaveSolutions/image_gen) v2.1.0 plugin is
reserved for cover and non-diagram artwork. If the diagram renderer has no
image backend, it writes `<stem>_imagen.prompt.txt` and exits 2; it never
substitutes SVG or a plain PNG. Each accepted figure retains the plugin's
render and judge sidecars. No model key or research network access is needed
for the recorded research corpus itself.

```bash
LIVE_E2E_MAX_USD=10 task e2e-live
```

This is a manual or nightly acceptance test. It uses the Agent SDK and MCP
research tools, so it requires `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, the
renderer, and an approved image backend. It never publishes a gist. The resulting figures must
have no fidelity misses, be embedded in the paper, and meet the resolution
floor recorded in `e2e-report.json`.

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

Deletes `work/`. Both pinned plugin clones in `.cache/` stay.
