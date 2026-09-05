# Spec. Lab 3. Deep research over MCP, on the Claude Agent SDK

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

A topic goes in. An evidence-backed technical white paper comes out, as one
markdown file and its rendered figures, with the research that produced it left
on disk as a knowledge bundle.

## The cast for this loop

- `orchestrator`
- `outliner`
- `outline_judge`
- `researcher`
- `verifier`
- `section_judge`
- `ledger`
- `diagrammer`
- `chartist`
- `writer`
- `judge`

`roleplan.py` is where that list lives. Read it there. Do not restate a scope in
this folder.

Eleven roles is more than the other three loops need, and each one is here
because it holds a tool set or a context no other role holds. The researcher
searches and cannot write, because a searcher that can write can edit the
evidence to fit the paper. The verifier searches again and is never shown the
researcher's answer, because a second opinion formed from the first opinion is
not a second opinion.

Exactly one role writes. The writer holds `Write`, scoped to `sections/**`,
because a section is long prose and returning it through a message invites
truncation. Everything else comes back as schema-checked structured output that
Python writes: the outline, the diagram source, the chart spec, the verdicts. Two of those roles
held `Write` in an earlier draft and never used it, which made the hook below
decorative.

No role holds `Bash`. The renderer is one subprocess with fixed arguments, and
Python runs it. Handing a model a shell to save that would widen the blast
radius from "a wrong paper" to "anything this machine can run".

## How this runtime enforces scope

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The researcher, the verifier, and the judge hold neither `Edit` nor
`Write`, so there is nothing left for a hook to guard.

One hook serves the whole cast. It reads `agent_type` off the tool call, which
the SDK populates whenever the call comes from inside a spawned subagent, and
looks up that role's scope. sol1 instead registers one hook per writing role,
which works because the enhancer has exactly one writer. It does not generalize:
register several hooks on `Write` and all of them run, an empty dict means "no
opinion", and the first role that shrugs lets another role's write through.

A write that arrives with no `agent_type` is denied, because the orchestrator
holds only `Agent` and has no business writing anything. So is a write from any
role but the writer, and so is a write from the writer to `paper.md`,
`claims.json`, or anywhere outside the work directory.

The role table is authoritative on tools. When an agent markdown file and the
table disagree, `options_for` raises. Drift in a tool list is how a reader
quietly becomes a writer.

### `allowed_tools` is not the parent's tool list

It is a session-wide permission allowlist, and it gates a subagent's calls as
well as the parent's. Reading it the other way is what broke the first live run
of this port. The options said `allowed_tools=["Agent"]` with
`permission_mode="dontAsk"`, the researcher's own list held Perplexity,
Context7, and `WebSearch`, and every one of those calls came back denied.

What the researcher then did is the part worth keeping. It did not answer from
memory. It reported "NO RESEARCH WAS PERFORMED", named each denied tool, and
returned an empty claim list, and the run escalated with "no source produced a
single claim" rather than shipping four fabricated sections. The grounding
contract held while the wiring was wrong, which is the order you want those two
to fail in.

`options_for` now allows the union of what the cast holds. Each role is still
narrowed by its own `tools` list, `Bash` is denied at the top because no role
here needs one, and the parent is kept from writing by the hook rather than by
the allowlist.

## How this runtime reaches the outside world

`roles.mcp_servers()` declares Context7 and Perplexity in Python, and
`strict_mcp_config=True` makes those the only servers in the run.

The obvious wiring is `setting_sources=["project"]` with a `.mcp.json` at the
repo root, and this port used that first. It is wrong for a folder that claims
to be standalone. `.mcp.json` holds an API key, so it is routinely gitignored,
and it is gitignored here: a fresh clone, a `git worktree`, or an attendee's
checkout has no such file. The researcher then loses both servers with no error
anywhere, and a topic it cannot search reads downstream as a topic nobody has
written about.

Perplexity is included only when `PERPLEXITY_API_KEY` is set. A server started
with an empty key answers every question with an auth error, which is the same
failure wearing a different hat. Context7 needs no key and is always there.

## Build it step by step

1. Install the runtime and the diagram renderer.

   ```bash
   task setup
   ```

2. Read the cast before you configure anything.

   ```bash
   task table
   ```

   The judge, the researcher, and the verifier must print `no` in the writes
   column. If any prints `yes`, stop. Nothing downstream is worth building on
   that.

3. Run the deterministic layers against their own assertions.

   ```bash
   task checks
   ```

4. Run the whole pipeline with no key and no network.

   ```bash
   task demo
   ```

5. Research something real.

   ```bash
   task run TOPIC="how MCP servers authenticate"
   ```

## Verify

```bash
task test
```

Those checks need no SDK, no API key, and no network. They assert:

- The cast is eleven roles, and the judge writes nothing in every loop.
- Every tool the cast holds appears in `allowed_tools`, so no role is denied a
  tool its own list grants.
- One writer, one hook, and no reader can write through it.
- The writer cannot reach `paper.md` or `claims.json`.
- A write with no `agent_type` is denied, and so is a path outside the work
  directory.
- `options_for` loads the plugin, declares both MCP servers, and uses `maxTurns`
  rather than `max_turns`, which raises `TypeError` on the real SDK.
- The MCP tool names the roles hold match the servers the folder declares.
- The verifier is never handed the researcher's source.
- A claim the two disagree on is disputed, and one the verifier cannot reach is
  unverified, never silently dropped.
- A citation whose identifier is absent from the retrieved evidence is reported.
- The diagram loop stops after three attempts and records what the image lost.
- Deleting one phase output re-runs that phase and no other.
- A paper that did not pass is never published.

## Run the loop

The live operator path is [HOW_TO_RUN.md](HOW_TO_RUN.md). `task setup` creates
`.venv` in this folder. Saturday Lab 3 is `labs/lab3_research`.

```bash
task demo                                   # offline, over the fixture
task run TOPIC="..."                        # needs PERPLEXITY_API_KEY
task run TOPIC="..." -- --backend perplexity  # real search, templated prose
task publish TOPIC="..."                    # also pushes to a private gist
task e2e-fixture                             # illustrated offline acceptance test
LIVE_E2E_MAX_USD=10 task e2e-live            # bounded live Agent SDK acceptance test
REPORT_DIR=work/e2e-loop-engineering-live task pdf
REPORT_DIR=work/e2e-loop-engineering-live task publish-report
```

Output lands in `work/<slug>/`:

```
corpus/brain-pack.md     what the brains already said (not verified)
corpus/brain-pack.json   the same data, for Python
outline.json             the outliner's last draft
outline.approved.json    the stamped contract every later phase reads
sections/<id>.md         one file per approved section
paper_ledger.json        facts, numbers, terms, and forward refs per section
knowledge/<id>/          findings, evidence, verdicts for that section
paper.md                 the deliverable
paper.pdf                Arctic Fox publication export
paper.pdf.json           PDF theme, page, figure, and byte receipt
diagrams/*.png           the figures, and the source that produced them
knowledge/research/      the RKC bundle: sources, claims, evidence, findings
.harness/state.json      per-phase status and cost
```

"Secret" on a gist means unlisted, not access controlled. Anyone holding the
URL can read the paper and fetch every figure. Treat the URL as the credential.

## What one run does

1. **Corpus pack.** Read the configured brains (`--brain`, `RESEARCH_BRAINS`,
   or the sibling `loop_eng_2nd_brain/knowledge`) for terminology and earlier
   conclusions. Write `corpus/brain-pack.md` and `corpus/brain-pack.json`.
   Skip when no brain is there. Never treat the pack as verified. A topic
   with fewer than ten hits is `corpus_thin`.
2. **Outline.** Turn the topic into a two-level outline: sections with
   objectives, abstracts, key questions, claims to support, required evidence,
   word targets, and planned figures. Python validates it, an outline judge
   scores it, and a stamp writes `outline.approved.json`. Later phases read
   that file and nothing else. `--profile demo` commissions 2000 words,
   `--profile paper` 4000, and `--profile whitepaper` 6000. A profile sets the
   outline target, never the check floor: the floor is one number, 2000 words,
   for every profile. `--approve` stops after the outline
   judge (exit 3) with a readable `outline.md`. `--resume` continues from the
   stamped `outline.approved.json`, and re-judges if `outline.json` changed.

   Both halves of the budget matter. Every key question is a research turn and
   a verification turn, so an uncapped outline is an uncapped bill. Enforcing
   the cap without telling the outliner is worse than it sounds: asked to plan
   a paper on MCP authorization it returned seven good sections and twenty-eight
   questions, and truncating that to four questions left a paper with two
   sections and five orphaned headings. An outliner that knows the ceiling
   writes a whole paper under it.
3. **Sources.** One turn names this topic's search domains, and Python admits
   them. The provider takes twenty domains for the whole run, and the seed is
   vendor documentation, which is right for a paper about those vendors and
   close to useless for one about oncology or monetary policy. The
   `source_librarian` holds no search tool, because searching to decide where
   to search lets its own first results pick the allowlist, and no write tool,
   because Python owns the admission. `source_policy.admit` drops an invented
   `org_type`, anything on the denylist, every top level domain but `.gov`,
   `.edu`, and `.int`, and everything past twenty. Writes
   `corpus/source_allowlist.json` with what was proposed, dropped, and
   admitted. A failed or thin proposal keeps the seed, so the offline lane and
   a dead model still run.
4. **Sections.** For each approved section, in outline order: ask the
   section's key questions, search the corpus first, fill unanswered
   questions once, verify independently, write the section, run the
   section check, grade it, and append a ledger entry. Writes
   `knowledge/<id>/findings.json`, `sections/<id>.md`, and
   `paper_ledger.json`. A finished section is skipped on resume.
   Research for a section runs once; only that section's write retries.
5. **Diagram.** The diagrammer returns the source, Python renders it and runs
   the fidelity judge, and a miss goes back to the diagrammer as a list of what
   the image lost. Three attempts, then keep the closest image and record the
   miss.
6. **Assemble.** Stitch the sections and append the reference list, in Python.
   Asking a model to re-emit the whole paper to join it is how a paper loses a
   section between two calls.
7. **Check.** Deterministic rows: sources, complete, outline_coverage, grounded,
   cited, sourced, images, style, and, on a paper run, has_body and length.
   Length is hard at 2000 words, whatever the profile commissioned. No model
   votes here.
8. **Review.** The judge scores the rows a script cannot, including `depth`,
   and its verdict is a row in the failure signature rather than a separate veto.
9. **Publish.** On request, and only after the paper passes.

Then the knowledge bundle is written, whatever the gate said. A run that
escalated still found sources and checked claims, and throwing that away means
the next attempt pays for it again. `--ingest-brain` is opt-in. It copies the
bundle into a brain git worktree and opens a PR. It refuses `main`.

### Where the money is checked

`--max-usd` is checked inside the research phase, inside the verification
phase, and at the gate. Checking only at the gate is a bug this port had: the
gate runs once per attempt, and a twenty-four question research phase can spend
the whole budget several times over before the gate ever sees it.

Running out mid-verification leaves the remaining claims `unverified`, which
the writer states qualitatively. Marking them verified because the money ran out
is the lie.

### The exits

Three, and no fourth: pass, retry, escalate. `gates.py` owns them.

The one most people miss is the stall. When an attempt fails in exactly the same
way as the last one, the loop is not converging, and spending the rest of the
budget watching it fail identically buys a surprise bill, not a paper. The
signature is what failed, not how it was worded, so a model rephrasing its own
complaint does not read as progress.

### What retries, and at what size

The unit retries, never the phase. Re-running the whole research phase because
the fourth question came back without JSON makes you pay again for the three
that worked.

| Unit | Attempts | On giving up |
| --- | --- | --- |
| the outline | 2 | the run escalates, nothing downstream has input |
| one research question | 2 | recorded in `sources.json` under `failed`, the run goes on |
| one claim | 1 | falls back to `unverified` |
| one figure | 3 | keeps the closest image and records what it lost |
| the writing | `--max-iterations` | the write cycle's own gate |

`gates.decide` owns all of it, including the linear phases, which had no retry
at all until one malformed answer killed a run that had already paid for its
research. The signature is the failure kind, not its wording, so two identical
failures read as a stall and escalate with "not converging" rather than
spending the last attempt watching it happen again.

A runtime ceiling passes through untouched. It is not a turn to retry, and
retrying it spends the rest of the budget rediscovering it. A retry also checks
`--max-usd` before it spends, so a run that is out of money does not buy a
second attempt it cannot afford.

### Three budgets, not one

`--max-questions`, `--max-claims`, and `--max-usd`, and each one exists because
a live run needed it.

| Flag | Default | What it caps |
| --- | --- | --- |
| `--max-questions` | 12 | research turns, and therefore the paper's width |
| `--max-diagrams` | 4 | figures |
| `--max-claims` | 40 | how many claims get a second opinion |
| `--max-usd` | 12.00 | the whole run, checked inside phases and at the gate |

Four questions produced a hundred and eleven claims on one live run. Every claim
is a verification turn, so without `--max-claims` the verify phase spent the
entire budget and left a hundred and three claims unchecked anyway. With the
cap, claims carrying a number, a version, or a date are checked first, because
those are the ones that go stale and the ones a reader can find wrong.

Claims past the cap stay `unverified`. The writer states them qualitatively and
the knowledge bundle records that nobody checked them.

### The row that looks redundant

`complete` asserts that every section the plan named is in the paper. It reads
like a check that cannot fail, and it was added because it did.

A run that spent its budget in verification wrote no sections at all. The
assembled paper was a title, an abstract, and a twenty-five entry reference
list, and it passed every other row: the abstract is exempt from `cited`, the
references were intact, there were no figures to break, and there was no prose
left to hold an em dash. The rubric called it green.

The judge caught it, and the publish phase refused it. Two backstops held. The
row is there so the first one does not have to.

### The check that matters most

`sourced` is the least obvious row and the most important one. A web search
cannot refute a citation that was never published, and asking a model whether a
reference is real gets you a confident yes. The only thing that catches a
fabricated arXiv id or DOI is looking for it in the text that was actually
retrieved. That is what `checks.ungrounded_identifiers` does, ported from the
grounding guard in the articles v3 pipeline.

## What this folder is not

This folder is standalone. Copy it somewhere else and it runs. Do not import a
shared engine.

It is not a general research framework. It produces one artifact, a technical
white paper, and every phase is shaped by that.

It is not the Saturday hour. This folder is the take-home report generator.
Saturday Lab 3 is `labs/lab3_research`, where attendees fill `plan_questions`
and `check_brief` and keep a cited brief. Nobody should run ten phases to learn
that citations are arithmetic.

`.cache/` holds a clone of the diagram renderer and any gist clones. It is
disposable, `task setup` rebuilds it, and nothing in it is edited by hand.

`plugin/skills/research-loop/SKILL.md` is not a runnable skill here. It is the
readable specification of what `paper.py` implements. `options_for` enables
only the two qualified image skills, so the parent cannot invoke the research
loop as a second orchestrator. A sentence is not a fence.

### Publication figures

`task setup` pins and clones
[`SpillwaveSolutions/imagen-diagrams`](https://github.com/SpillwaveSolutions/imagen-diagrams)
v0.2.0. `task setup` also installs
[`SpillwaveSolutions/image_gen`](https://github.com/SpillwaveSolutions/image_gen)
v2.1.0 under this folder's `.cache/`; the Agent SDK loads both local plugin
manifests and exposes only their two plugin-qualified image skills, without
depending on `~/.claude` or project-level skill discovery.
`diagrams.py` invokes the plugin's `render.py` and `judge.py` directly. The
`imagen-diagrams` plugin alone turns `.mmd` and `.puml` into the paper's
`*_imagen.png` diagrams. `image-gen` is reserved for cover and non-diagram art.
The renderer writes a themed prompt sidecar before it fails closed with exit 2
when no image backend is installed; it never substitutes SVG or a plain PNG.

An accepted E2E figure must retain the plugin render sidecar and judge sidecar,
be rendered at article density, and pass the plugin's source-inventory check.
The harness then keeps the retry cap and validates document embedding and
resolution. A future vision pass can strengthen label readability without
replacing this source-of-truth renderer.
The publication theme is the plugin's built-in `arctic-fox` theme. Figure
render sidecars must record `theme: arctic-fox` and `density: article`; the E2E
gate rejects drift. `pdf_report.py` applies the same palette and restrained
print system to `paper.pdf`, embeds the accepted figures, then reopens the PDF
and writes `paper.pdf.json` as its receipt.
