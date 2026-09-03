# Spec. Lab 3. Research on LangChain Deep Agents

A question in, a cited brief out. A topic in, an evidence-backed white paper out.

LangChain's own Deep Agents quickstart is a research agent. This folder is that
shape, pointed at our tool boundary, then grown until it produces something you
would hand to a colleague.

The point is not that it runs. The point is that a role cannot do a job it was
not given a tool for, and that nothing about grounding, cost, or stopping is left
to a model's own judgment.

## Standalone

This folder imports no shared engine. Every module below is a copy, and
`tests/test_standalone.py` fails if that stops being true.

| File | What it holds |
| --- | --- |
| `loop.py` | Both entry points, and the role table |
| `roleplan.py` | The cast per loop, and the write scope per role |
| `roles.py` | Deep Agents subagents, and the three fencing layers |
| `write_scope.py` | `WriteScope`, `Doer`, `Judge`, `Orchestrator` |
| `gates.py` | Three exits, and stable failure detection |
| `research.py` | One filtered search boundary, paper-safe provider fallbacks, and a hard cost cap |
| `source_policy.py` | The explicit official-host allowlist and citation post-filter |
| `researcher.py` | The Lab 3 runner |
| `brief.py` | Citation arithmetic and the em dash sweep |
| `adapter.py` | Deep Agents results into a `DoerResult` |
| `mcp_tools.py` | `.mcp.json`, and the fallbacks under it |
| `corpus.py` | Second-brain search, pack, and opt-in ingest |
| `outline.py` | Outline validator, stamp, and plan lift |
| `sections.py` | Per-section check, judge, and ledger |
| `evidence.py` | `SourceDocument`, `Claim`, `Finding`, and corroboration |
| `paper.py` | The nine stage pipeline and the three exits |
| `stages.py` | Each stage's gate |
| `state.py` | The resumable checkpoint |
| `diagrams.py` | Mermaid and PlantUML into figures |
| `paper_check.py` | The hard gates on a finished paper |
| `publish.py` | The secret gist push |

## The cast for the paper loop

```
role              writes  scope
orchestrator      no      nothing
planner           yes     plan.json
outline_judge     no      nothing
researcher        no      nothing
verifier          yes     evidence/**   (denied: paper/**)
section_judge     no      nothing
ledger            no      nothing
diagrammer        yes     diagrams/*.mmd, diagrams/*.puml   (denied: paper/**, evidence/**)
writer            yes     brief.md, paper/**, work/research/**, sections/**   (denied: evidence/**)
reviewer          no      nothing
```

Run `task table` and read the writes column. If the reviewer prints `yes`, the
translation is wrong and the tests say so.

## How this runtime enforces scope

Deep Agents scopes three ways, and this folder uses all three.

1. **A tool list per subagent.** Deep Agents supplies backend-aware read tools
   from the mounted filesystem. The reviewer receives no custom write tool;
   the writer and verifier receive only their scoped custom write tools. "Do
   not edit the paper" is not an instruction it can reinterpret.
2. **A path check inside the write tool.** The writer may write `paper/**`, the
   verifier may write `evidence/**`, and neither can reach the other. The tool
   returns a refusal sentence rather than raising, because a raw traceback in an
   agent's context starts a retry loop and a sentence naming the scope changes
   the next action.
3. **A fence around the harness.** `build_agent` passes `permissions=`, hides the
   built-in write tools from the orchestrator, mounts the working directory as
   `FilesystemBackend(virtual_mode=True)` so `..` cannot walk out, and turns the
   general-purpose subagent off.

The custom tools must not reimplement `read_file`. Deep Agents' own reader is
what resolves `/skills/**` and `/memory/**`; a duplicate custom tool shadows
those mounts and quietly makes the mounted role skill unreachable.

Layer 3 is the one people skip. The default general-purpose subagent ships with
the harness filesystem tools, so leaving it enabled is how a carefully scoped
agent writes anywhere it likes.

## The nine stages

| # | Stage | Model? | Its gate |
| --- | --- | --- | --- |
| 1 | plan | yes | Three to twelve questions, each with a check, at most six important |
| 2 | search | yes | Every claim names a source that resolves |
| 3 | verify | yes | Every important claim has a decided truth state, and anything past the cap says it was skipped |
| 4 | outline | yes | Every body section names claim ids that exist and may be used |
| 5 | diagram | yes | At most twelve nodes, alt text present, and the pinned plugin judge accepts a `*_imagen.png` |
| 6 | write | yes | A section cites only the numbers its claims support, and carries real prose rather than a restated claim list |
| 7 | review | yes | Every rubric row passes, including `depth` |
| 8 | assemble | no | Every hard gate in `paper_check`, including that the paper has a body and clears 2000 words |
| 9 | publish | no | The gates passed. Opt-in only |

## Three exits, and no fourth

Checked before every stage, in this order:

| Exit | When |
| --- | --- |
| `done` | Stage 8 finished and every hard gate is green |
| `cost` | The money budget is spent |
| `max turns` | A stage exhausted its retries |

Done beats a spent budget. A run that finished and then noticed it was over its
cap did finish, and reporting that as a cost failure discards the paper.

The cost cap is checked before every model call, not between stages. Checking
only at the stage boundary is not a cap: a stage that loops over six sections
makes six calls with nothing between them, so the run learns it is over budget
once the money is gone. The check needs headroom too, or the last call starts
with a cent left and finishes two dollars over, so the loop remembers what a
call of each kind cost and refuses to start one it cannot afford. The cap is
therefore exact to within the first call of each role, which is the first time
the loop has any basis for an estimate.

A spent budget is never a retry. A gate failure might be fixed by another
attempt. A budget will not be, and retrying on it turns a cost cap into a cost
multiplier.

Inside a stage, `gates.decide` returns pass, retry, or escalate. It short
circuits the one case worth catching early: the same rows failing twice, which
means the loop is not converging. Spending the rest of the budget to watch it
fail identically buys a bill, not a fix.

## Publication figures fail closed

Mermaid and PlantUML are source languages here, not publication formats. The
diagrammer writes `.mmd` or `.puml`; local Python inventories the labels and
rejects more than twelve nodes before spending an image call. The pinned
`imagen-diagrams` v0.2.0 plugin then renders `*_imagen.png`, and its own fidelity
judge checks the PNG against the source. A judge miss can trigger a bounded
redraw because the diagrammer can simplify or restore a missing label.

`task setup` clones `imagen-diagrams` v0.2.0 and `image-gen` v2.1.0 into this
folder's disposable `.cache/`. Only `imagen-diagrams` handles `.mmd` and
`.puml`. `image-gen` is reserved for cover and non-diagram art. Deep Agents no
longer shells out to mermaid-cli or the PlantUML JAR, and neither an SVG nor a
plain PNG can enter the assembled paper, PDF, or publication gate.

A missing plugin or image backend is not a redraw. The renderer keeps
`<stem>_imagen.prompt.txt`, raises `ImageBackendUnavailable`, and the command
exits 2. The paper does not substitute a lower-fidelity artifact. An accepted
figure keeps the renderer sidecar, judge sidecar, and local audit record.

## Verification is bounded

The verifier searches once per claim it is handed, so the length of that list is
the size of the work. `--max-verify` caps it at twenty-four, shakiest first: lowest
confidence, then fewest sources. A cap that took claims in whatever order the
dictionary held them would spend the budget confirming the facts nobody doubted.

Anything past the cap is written down as not cross-checked, and the gate refuses
a skip that says nothing, because silence reads exactly like a pass.

A claim records two separate facts. `truth_state` counts sources.
`cross_checked` says whether a verifier took a second, independent look. Two
URLs inside one search answer are two sources and one look, and a reader is
entitled to know which claims nobody went back and checked.

## One filtered boundary, with no Bing paper fallback

The model never chooses who is reputable. Python sends each provider an explicit
allowlist and drops every returned URL that does not pass the same policy. The
paper gate repeats that check against the rendered references.

For each planned question, Perplexity runs Scout then Retrieve within the one
researcher tool invocation. Scout may add only `docs.`, `reference.`, or
`learn.` hosts, approved vendor GitHub organizations, or this repository; the
merged list caps at 20 entries. A filtered Search bundle with hits but no usable
quote may use one filtered `perplexity_ask` repair. It never makes an Ask call
after a usable Search result.

| Backend | When it is available |
| --- | --- |
| `perplexity` | `PERPLEXITY_API_KEY` is set. Filtered `perplexity_search` uses MCP first, then the Search REST API. The key may live in `.env`, `../.env`, `../../.env`, or `../../../.env` relative to this solution. |
| `anthropic` | Perplexity is unavailable and `ANTHROPIC_API_KEY` is set. One `web_search_20260209` call with the same allowlist. |
| `openai` | Perplexity and Anthropic are unavailable and `OPENAI_API_KEY` is set. One Responses web search with the same allowlist. |
| `context7` | `ctx7` is on PATH, or the MCP server answers. Verification only |
| `fixture` | Explicit offline mode. A recording, for a room with no network |

The live paper chain is Perplexity, then Anthropic, then OpenAI, then fixture.
It has no Bing fallback. `WebSearchBackend` remains only for an explicit
`researcher.py --backend websearch` classroom recording or demo; auto paper
runs do not select it.

The paper gate also requires the body to name the local three exits in order:
`done`, then `cost`, then `max turns`. The planner's first question asks that
exactly and must be grounded in this repository.

## Build it step by step

1. Install the runtime and both pinned image plugins.

   ```bash
   task setup
   ```

2. Print the cast with nothing else installed.

   ```bash
   task table
   ```

3. Run the deterministic checks. Every one of them is a claim this folder makes
   about itself.

   ```bash
   task checks
   ```

4. Run the whole pipeline against recorded research and a configured image
   backend.

   ```bash
   task paper
   ```

5. Read `work/paper/<slug>/`. The paper is one file. The evidence behind it is a
   directory of records you can grep, extend, or feed to the second brain.

6. Use `--backend auto` only when live research is intentional.

## Verify

```bash
task test      # no SDK, key, network, or plugin clone; image calls are stubbed
task table     # the reviewer prints no in the writes column
task checks    # every module's own assertions
task brief -- --question "sqlalchemy nullable datetime column"
```

## Run the pipeline

```bash
# recorded research; publication figures still require an image backend
task paper

# live, needs a model key. Research falls through filtered Perplexity,
# Anthropic, OpenAI, then the recorded fixture; it never uses Bing.
task setup
task live TOPIC="context management in multi-agent research loops"

# a resumed run skips every finished stage and carries the cost forward
task live TOPIC="context management in multi-agent research loops"

# push the finished paper to its own secret gist
task publish -- --slug context-management-in-multi-agent-research-loops --dry-run --out /tmp/staged
task publish -- --slug context-management-in-multi-agent-research-loops
```

## Debug one live paper run

Normal runs use `.invoke()` and stay quiet. Add `--debug` to stream the parent
graph's debug events and each delegated subgraph namespace while preserving the
final parent state as the stage reply:

```bash
task live TOPIC="loop engineering best practices" -- --debug
```

The switch is deliberately on the parent graph. Deep Agents accepts
`debug=True` in `create_deep_agent`, but a dict subagent specification has no
per-role `debug` field. The printed `namespace=` tells which subgraph spoke:
`parent` is the orchestrator, and a non-empty namespace is the delegated role.
The trace can include prompts, tool arguments, and source excerpts, so use it
for a short probe and do not paste it into a ticket or commit it to the paper.

This does not enable `langchain.globals.set_debug(True)`. That is process-wide
and floods a paper run with unrelated model and tool events.

## What one run leaves behind

```
work/paper/<slug>/
  whitepaper.md          the paper
  plan.json              the questions, and what would answer each one
  outline.json           each section bound to the claims it may use
  evidence/              SourceDocument, Claim, and Finding records
  diagrams/              the mermaid and plantuml sources
  figures/               judged *_imagen.png plus render, judge, and audit sidecars
  gates.json             which hard gates passed
  .paper-state.json      the checkpoint a resume reads
```

The evidence directory uses the same record shape as
`loop_eng_2nd_brain/knowledge/research/`, so a run can be ingested into the
second brain later without a conversion step. The claims outlive the paper, which
is the point of writing them down separately.

## What this folder is not

It is not a shared library. Nothing here is imported by another solution folder,
and nothing here imports one. It is not a generic research engine. Copy this
folder somewhere else and it runs.

The check that runs without any of it is `task test`: no SDK, key, network, or
plugin clone. Tests stub the one `imagen-diagrams` subprocess boundary and
assert that missing backends retain their prompt and exit 2. A test also scans
the implementation for the removed mmdc and PlantUML renderer arguments, while
the paper and PDF gates reject SVG and plain-PNG diagram links.

If your reviewer ends up holding a write tool, the translation is wrong, and
`task test` says so.
