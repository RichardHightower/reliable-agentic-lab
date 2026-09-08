# How to run this solution

Everything here runs from `solutions/sol3_research_agent_sdk/`, standalone.

You need `python3` and `task`. A live run also needs an `ANTHROPIC_API_KEY`.
`task publish` also needs `gh` with the `gist` scope.

Python is the harness. The model outlines, searches, verifies, and writes
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

Creates `.venv`, installs the Agent SDK plus the PDF dependencies,
`.cache/imagen-diagrams` at v0.2.0, and `.cache/image-gen` at
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
task test-live
```

`task demo` runs the recorded fixture. No key, no network. `task test-live`
runs the one live renderer test, skipped otherwise so `task test` stays
deterministic; set `SOL3_LIVE_TESTS=1` and a real image backend key first.
`task table`
prints the role table. The writer is the only role that prints `yes` in the
writes column. A paper run is supposed to produce a document a colleague can
use, not a cited brief: 2000 words, with each body section unpacked from its
claims. Saturday Lab 3 is still the short brief.

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
reserved for cover and non-diagram artwork. The diagram renderer uses its own
approved backend order: `imagen`, `grok`, then `codex`. `GEMINI_API_KEY` is
passed to the Imagen CLI under the `GOOGLE_API_KEY` name it expects. If a
backend exits without a PNG, the harness keeps that attempt's prompt and
metadata before trying the next backend. If all three fail, it writes the final
`<stem>_imagen.prompt.txt` and exits 2; it never substitutes SVG or a plain PNG.
Each accepted figure retains the plugin's render and judge sidecars. No model
key or research network access is needed for the recorded research corpus
itself.

```bash
LIVE_E2E_MAX_USD=10 task e2e-live
```

This is a manual or nightly acceptance test. It uses the Agent SDK and MCP
research tools, so it requires `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, the
renderer, and an approved image backend. It never publishes a gist. The live
lane passes `--profile paper` (4000 words, 20 questions, 60 claims) and does
not clamp those numbers; the fixture lane stays on demo. The outline judge
scores `flow`, `completeness`, `titles`, and `corpus_fit`, the same four
rows as the Deep Agents twin. The resulting figures must have no fidelity misses, be embedded in the paper,
and meet the resolution floor recorded in `e2e-report.json`.

The live lane also needs a corpus brain. It looks for one in this order:
`BRAIN`, then `RESEARCH_BRAINS`, then a `loop_eng_2nd_brain/knowledge` sibling
of this checkout. A brain is prior art in another repository, and a clone or a
worktree usually has no sibling. When it finds none, the preflight names every
path it tried and stops before the first paid query. An empty pack is a thinner
outline, not a failed `corpus_fit` row, but this lane is not the thin-corpus
lane.

```bash
BRAIN=/path/to/loop_eng_2nd_brain/knowledge LIVE_E2E_MAX_USD=10 task e2e-live
ALLOW_THIN_CORPUS=1 LIVE_E2E_MAX_USD=10 task e2e-live   # run anyway; thinner outline
```

Set `SOL3_QUERY_TIMEOUT_SECONDS` to change the per-query ceiling. The default
is 900 seconds.

Both E2E lanes render article figures with imagen-diagrams' built-in
`arctic-fox` theme. The acceptance report rejects a figure whose render sidecar
records another theme.

## House style and the evidence contract

The paper follows one house style, published once on the wiki as [Sol-3-White-Paper-Style](https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style). The check module grades third person and no marketing verb (`person`, `marketing`), no contraction and no Latin abbreviation (`ste_language`), and a heading that answers its own question (`question_heading`). The body names no search host (`policy_leak`) and states a caveat once (`caveat_once`). A first-use term earns a `TERM:` marker and a Glossary entry (`glossary_complete`, `glossary_exact`). A figure earns a caption and a mention in its own section (`captioned`, `figure_referenced`). The body carries Methods and, for a human study, a study table (`methods_present`, `study_table`), with front matter above the Abstract (`front_matter`). The last body section is a next step, never a sale (`next_step`, `cta_language`), and the abstract is written last, graded against the body (`abstract_matches_body`).

The evidence contract is arithmetic, not a promise from the model. `source_policy.py` seeds the allowlist by field (`seed_for_field`), bans a host outright (`DENYLIST`), and grades a source's tier (`tier_for`). A shaky numeric claim spends one follow turn, and a generalizing claim spends one counter turn before a lever is ruled out; the `counterweighed` row names a claim nobody checked. A safety claim needs a cited guideline (`guideline_cited`), and a question with stated evidence requirements needs `evidence_requirements_met`. A citation's title, authors, and year come from the fetched record, never the model's guess, and a claim earns attribution only when the fetched text supports it. A diagram is graded against the section's own claims before it is embedded.

The glossary, front-matter, next-step, and study-table rows (`glossary_complete`, `glossary_exact`, `methods_present`, `conclusion_present`, `study_table`, `front_matter`, `next_step`, `cta_language`) sit behind `enforce_structure`, off by default. Every `task demo` lane runs with it on, offline included; only a direct call to `check()` in a test leaves it off.

## Export and publish an existing report

Export the default live E2E report as a publication PDF:

```bash
REPORT_DIR=work/e2e-loop-engineering-live task pdf
```

The command writes `paper.pdf` and `paper.pdf.json` beside `paper.md`. The PDF
uses the same Arctic Fox white, deep-navy, royal-blue, and silver-grey visual
system as its article figures.

Publish the existing Markdown, PDF, and figures without rerunning research:

```bash
REPORT_DIR=work/e2e-loop-engineering-live task publish-report
```

The repo-local `$e2e-test-research-report` skill runs the live E2E lane by
default, exports and visually checks the PDF, then attempts this secret-Gist
publication step. Use its fixture lane when live credentials are unavailable.

## Live paper

```bash
task run --
TOPIC="your topic" task run --
task publish --
```

`task run` refuses if you skipped `task setup`. It defaults to `--profile demo`
(2000 words, 12 questions, 40 verified claims, $12). A paper run is supposed
to produce a document a colleague can use, not a cited brief. Saturday Lab 3
is still the short brief.

Raise the budget for a real white paper:

```bash
TOPIC="how MCP servers authenticate" PROFILE=paper task run --
```

`--profile paper` is 4000 words, 20 questions, 60 verified claims, $40.
`--profile whitepaper` is 6000 words, 32 questions, 100 verified claims, $80.

`--ingest-brain` is off by default. When you pass it a brain knowledge
directory that is a git worktree on a branch other than `main`, the run
copies the RKC bundle there and opens a PR. It refuses `main`.

```bash
TOPIC="loop engineering exit criteria" CLI_ARGS="--ingest-brain /path/to/brain/knowledge" task run --
```

Stop after the outline judge and read `outline.md` before any research spend:

```bash
TOPIC="how MCP servers authenticate" PROFILE=paper CLI_ARGS="--approve" task run --
```

That exits 3. Edit `outline.json` if needed, then continue:

```bash
TOPIC="how MCP servers authenticate" PROFILE=paper CLI_ARGS="--resume" task run --
```

Python stamps `outline.approved.json` (or re-judges if the outline changed)
and later phases read only that file.

Cap a live run while you are developing:

```bash
timeout 420 task run --
```

## Reset

```bash
task clean
```

Deletes `work/`. Both pinned plugin clones in `.cache/` stay.
