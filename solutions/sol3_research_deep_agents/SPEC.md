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
| `research.py` | One search boundary, four backends, a hard cost cap |
| `researcher.py` | The Lab 3 runner |
| `brief.py` | Citation arithmetic and the em dash sweep |
| `adapter.py` | Deep Agents results into a `DoerResult` |
| `mcp_tools.py` | `.mcp.json`, and the fallbacks under it |
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
researcher        no      nothing
verifier          yes     evidence/**   (denied: paper/**)
diagrammer        yes     diagrams/*.mmd, diagrams/*.puml   (denied: paper/**, evidence/**)
writer            yes     brief.md, paper/**, work/research/**   (denied: evidence/**)
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
| 1 | plan | yes | Three to eight questions, each with a check, at least one important |
| 2 | search | yes | Every claim names a source that resolves |
| 3 | verify | yes | Every important claim has a decided truth state, and anything past the cap says it was skipped |
| 4 | outline | yes | Every body section names claim ids that exist and may be used |
| 5 | diagram | yes | At most twelve nodes per figure, and every figure has alt text. No renderer on the machine skips the stage rather than retrying |
| 6 | write | yes | A section cites only the numbers its claims support |
| 7 | review | yes | Every rubric row passes |
| 8 | assemble | no | Every hard gate in `paper_check`, including that the paper has a body |
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

## A missing renderer is not a retry

`mmdc is not installed` is not something the diagrammer can fix. Asking it to
redraw is asking it to solve a problem it cannot see or reach, and three
attempts buy three times the bill and the same result.

The stage tells the two apart. A figure with too many nodes comes back as a
retry instruction, because a better attempt can fix it. A renderer that is not
on the machine raises `RendererMissing`, the stage records `renderer: missing`,
and the run continues. The paper ships without figures rather than not at all,
because nothing in `paper_check` requires one and blocking every attendee
without Java is a worse answer than saying so out loud.

## Verification is bounded

The verifier searches once per claim it is handed, so the length of that list is
the size of the work. `--max-verify` caps it at twelve, shakiest first: lowest
confidence, then fewest sources. A cap that took claims in whatever order the
dictionary held them would spend the budget confirming the facts nobody doubted.

Anything past the cap is written down as not cross-checked, and the gate refuses
a skip that says nothing, because silence reads exactly like a pass.

A claim records two separate facts. `truth_state` counts sources.
`cross_checked` says whether a verifier took a second, independent look. Two
URLs inside one search answer are two sources and one look, and a reader is
entitled to know which claims nobody went back and checked.

## One boundary, four backends

The loop never learns which one answered.

| Backend | When it is available |
| --- | --- |
| `perplexity` | `PERPLEXITY_API_KEY` is set. MCP first, then the REST API. The key may live in `.env`, `../.env`, `../../.env`, or `../../../.env` relative to this solution. |
| `context7` | `ctx7` is on PATH, or the MCP server answers. Verification only |
| `websearch` | No Perplexity key. The research tool queries the web; an optional inbox can provide a recorded response for a classroom demo |
| `fixture` | Explicit offline mode. A recording, for a room with no network |

## Build it step by step

1. Make a virtualenv and install pytest.

   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install pytest
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

4. Run the whole pipeline offline, against a recording.

   ```bash
   task paper
   ```

5. Read `work/paper/<slug>/`. The paper is one file. The evidence behind it is a
   directory of records you can grep, extend, or feed to the second brain.

6. Only for a live run, install the SDK.

   ```bash
   task setup
   ```

## Verify

```bash
task test      # 226 tests, no SDK, no key, no network, no renderer
task table     # the reviewer prints no in the writes column
task checks    # every module's own assertions
task brief -- --question "sqlalchemy nullable datetime column"
```

## Run the pipeline

```bash
# offline, from a recording
task paper

# live, needs ANTHROPIC_API_KEY. It uses Perplexity when its key is available,
# otherwise the research tool queries the web.
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
  figures/               rendered SVG, polished PNG, and a sidecar each
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

The check that runs without any of it is `task test`. No SDK, no key, no
network, and no diagram renderer. That last one is load bearing: the suite used
to shell out to mermaid-cli and plantuml, so it could not run in continuous
integration, and a cost-cap test passed only because the developer's machine
happened to have plantuml. With no renderer the run died at the diagram stage
and still returned the exit code the test asserted. A test that cannot fail is
not a test, so the suite is hermetic and `.github/workflows/tests.yml` runs it
on a bare runner with nothing but `pytest`.

If your reviewer ends up holding a write tool, the translation is wrong, and
`task test` says so.
