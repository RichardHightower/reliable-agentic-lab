---
date: 2026-09-02
slug: sol3-white-paper-review
title: Why the sol3 research ports write thin papers, and what to change
git_base: "b93e8765"
branch: claude/sol3-research-agent-review-6tvdak
---

# Review: `sol3_research_agent_sdk` and `sol3_research_deep_agents`

Review and recommendation only. No code in this change.

## The question

Both sol3 ports are meant to turn a topic into an evidence-backed technical
white paper with figures. In practice they produce a short, correct, heavily
gated document of roughly one to two thousand words, with one or two
AI-rendered diagrams and no data charts. The SpillwaveSolutions `articles`
pipeline (v2 for prose, v3 for fact checking) and the
`harness_engineering_book` pipeline produce long, readable, illustrated
documents from the same kind of input. This review explains the gap and
recommends what to change so sol3 produces real white papers with graphs on
arbitrary technical topics.

The two Spillwave repositories are private and could not be read from this
session. The comparison below rests on what sol3 already ported from v3
(`checker/retry_loop.py`, `util/cost.py`, `util/verified_facts.py`,
`state.py`, and the grounding contract) and on Rick's description of v2 and
v3. sol3 ported v3's checking layer and none of v2's writing layer. That is
the one-line diagnosis: it fact-checks a paper it never lets itself write.

## What the ports do today

Both ports run the same phase list: prior art, plan, research, verify,
diagram, write, assemble, check, review, publish. Python owns the order, the
state file, the budget, and the three exits. The model is called only inside a
phase, through one named role, and each role holds only the tools it needs.
That structure is sound and should stay.

The numbers that shape the output, as of `b93e876`:

| Knob | Agent SDK port | Deep Agents port |
| --- | --- | --- |
| Questions per paper | 12 (`--max-questions`) | 8 (`stages.MAX_QUESTIONS`) |
| Claims verified | 24 (`--max-claims`) | 12 (`stages.MAX_VERIFY_CLAIMS`) |
| Money for the whole run | $5.00 | $5.00 |
| Retrieval per question | one Perplexity search, 10 hits, 1200 tokens per page | same, through the MCP server |
| Words per section | not stated | "90 to 180" or "180 to 300", in the prompt |
| Minimum paper length | none | 400 words |
| Writer output ceiling | SDK default | 4,096 tokens |
| Model | SDK default, not set per role | `claude-sonnet-5` for every role |
| Allowed source hosts | 14 fixed domains | 12 fixed domains |
| Figures | Mermaid or PlantUML, rendered by an image model | same |
| Data charts | none | none |

## Why the papers are short

### 1. The evidence is snippet-deep

Each research question makes one Perplexity search call and keeps the
snippets. Nothing fetches the page. The researcher then splits those snippets
into atomic claims, each one sentence with a short quote. A question typically
yields two to five claims. The writer is told to use only those claims. A
section written from three one-sentence claims is a hundred and fifty words
because there is nothing else to say.

This is the root cause. Every other limit below is a consequence of, or a
defense against, evidence that thin.

### 2. The Deep Agents port caps the prose on purpose

`paper.py` asks the writer for "90 to 180" or "180 to 300" words per section.
The writer skill says "do not pad", "omit unsupported background, framing,
forecasts, and generalizations", and "a concise section grounded in two claims
is better than a longer section". Then `stages.drop_uncited_prose` deletes
every paragraph that carries no citation marker before the gate runs. A
definition, a transition, or a paragraph of reasoning is exactly the prose a
white paper needs and exactly what gets deleted.

The Agent SDK port states no length at all, but its `cited` row fails any
non-abstract paragraph without a marker, so the writer learns the same lesson
by retry.

### 3. The source wall admits fourteen hosts

`source_policy.SEED_ALLOWLIST` is the same short list in both ports:
LangChain, Anthropic, OpenAI, Microsoft Learn, Stripe, MCP, Google SRE, and
this workshop's own GitHub org. A scout pass may add a host whose name starts
with `docs.`, `reference.`, or `learn.`, and nothing else. A topic on
Kubernetes, Postgres, Kafka, Rust, WebAssembly, or any IETF or W3C standard
finds zero admissible sources, and the post-filter drops every hit. The paper
then escalates with "no source produced a single claim" or writes "No source
in this run addressed" under each heading.

This is the single biggest reason the ports cannot write a real paper on an
arbitrary tech topic. It was built for the loop-engineering E2E scenario and
never widened.

### 4. Every paper is forced to be about this repo's loop exits

Both ports bind the first research question to the literal string "What three
exits does this repo's paper loop check, and in what order?"
(`turns.bind_exit_doctrine`, `stages.plan_gate`). The deterministic check then
requires the body to say "done, then cost, then max turns" in that order and
requires Figure 1 to label those three exits (`checks.doctrine_failure`,
`paper_check.has_exit_doctrine`). In the Agent SDK port `loop.py` passes
`enforce_research_policy=True`, which turns the doctrine row on for every
`task run`, not only for `task e2e-live`.

A paper on "how MCP servers authenticate" cannot pass its own gate unless it
contains a paragraph and a figure about this repository's control loop. This
leaked from the acceptance scenario into the general path and should be
scoped back to the E2E lane.

### 5. Verification is capped low, and the overflow is discarded

Twenty-four verified claims in one port and twelve in the other. Everything
past the cap stays `unverified`, and the writer is told to state those
qualitatively or drop them, and to prefer dropping. A longer paper therefore
degrades into vaguer prose rather than into more evidence. The cap exists
because one live run produced a hundred and eleven claims from four
questions, which is the right instinct with the wrong fix: the fix is
prioritizing and batching verification, not shrinking the paper.

### 6. Five dollars does not buy a white paper

The SPEC itself records a run that spent its budget in verification and wrote
no sections. With plan, twelve research turns, twenty-four verify turns, up to
twelve diagram attempts, four to eight writer turns, and a judge, all times
three iterations, $5 is a demo budget. A four to six thousand word paper with
forty to sixty verified claims and four figures costs on the order of $15 to
$40 with a Sonnet and Opus mix. The default should say so.

### 7. Figures are diagrams only, and only through an image model

`diagrams.py` accepts Mermaid or PlantUML source and hands it to the
`imagen-diagrams` plugin, which renders through Imagen, Grok, or Codex and
then runs a fidelity judge. There is no chart phase at all: nothing collects
numeric data, nothing plots it, and the `figure_assets` row rejects any image
that is not a `*_imagen.png`, so a chart rendered by Python would fail the
gate. With no image backend key the renderer exits 2 and the run ends with no
figure, because SVG and plain PNG fallbacks are refused on purpose.

For a white paper with graphs, that is the wrong split. An architecture
diagram can go through an image model. A graph of data must be plotted by
code from a table whose every number traces to a source.

### 8. Smaller issues that compound

- The Agent SDK port deletes every section on each retry (`CYCLE_OUTPUT`)
  and rewrites all of them with the judge's notes. The Deep Agents port
  keeps sections that passed. Rewriting a passing section costs money and
  risks breaking it.
- `ungrounded_identifiers` catches arXiv ids, DOIs, and author-year cites.
  It does not catch percentages, version numbers, dates, or benchmark
  figures, which are what a tech white paper mostly prints and what readers
  check.
- No role is on Opus. The judge and the writer are the two roles where model
  quality shows most.
- The planner is told "four to eight sections" and nothing about
  subsections, an executive summary, comparison tables, recommendations, or a
  glossary. The judge rubric has no depth or length row, so a thin paper that
  is correct passes.

## What to change

Ordered by leverage. Each item is done twice, once per port, by copying, per
`CLAUDE.md`. Prototype in the Agent SDK port first: sections already live as
files, the writer already holds a scoped `Write`, and the plugin structure
makes new roles cheap. Then port to Deep Agents.

### Phase 1: unblock arbitrary topics (small changes, large effect)

1. **Scope the exit doctrine to the E2E lane.** Default `enforce_loop_doctrine`
   to off in `loop.py` and turn it on only from `e2e.py`. Remove the bound
   first question from `turns.plan` unless a brief asks for it. Same for
   `stages.plan_gate` and `paper_check`'s `exit_doctrine` row. A commissioning
   brief is the right place for scenario-specific requirements, and the
   brief mechanism already exists.
2. **Derive the allowlist from the topic.** Keep the wall, change what feeds
   it. Add a planner output `hosts`: the official documentation hosts,
   standards bodies, and project GitHub orgs for this topic. Python validates
   each against a policy (official prefixes, a fixed list of standards hosts
   such as `ietf.org`, `w3.org`, `arxiv.org`, `kubernetes.io`, `cncf.io`,
   `postgresql.org`, plus vendor `docs.` hosts) and a denylist. Send at most
   twenty per question. Record the admitted list in `plan.json` so a reader
   can audit it. The post-filter stays.
3. **Let charts through the gate.** Change `figure_assets` to accept
   `*_imagen.png` for diagrams and `charts/*.png` for Python-rendered charts.
4. **Give the writer a length contract.** Per section, a target such as 600 to
   1,200 words with named subsections, from the planner. Raise
   `WRITER_MAX_TOKENS` to at least 8,192 in the Deep Agents port.
5. **Fix the `cited` rule.** A paragraph must cite when it contains a
   specific: a number, a version, a date, a name, a quoted phrase. A
   definitional, transitional, or reasoning paragraph without specifics may
   stand uncited. Implement as a deterministic "has specifics" regex, and stop
   `drop_uncited_prose` from deleting paragraphs that pass it. This one rule
   is what separates a paper from a claim list.
6. **Raise the defaults and add a profile.** `--profile demo|brief|paper`:
   demo keeps today's numbers so `task demo` stays cheap; paper sets
   questions 20, verified claims 60, `--max-usd` 30, iterations 3. Print the
   estimate before the run starts.

After phase 1, a run on any tech topic should produce a three to four
thousand word paper that passes the gates. Nothing in this phase changes the
role table or the tool boundary.

### Phase 2: deeper evidence

7. **Read the page, not the snippet.** After the search, fetch the top three
   to five admitted URLs per question and store the text under
   `knowledge/sources/<slug>.md`. Extract claims from the full text. Options,
   in order of preference: Perplexity's `max_tokens_per_page` raised and
   `perplexity_research` for the researcher subagent, Context7 for library
   docs, and a plain fetch with HTML stripped as the fallback. The `sourced`
   corpus becomes the full text, so version numbers and figures printed in the
   paper are actually findable, and the check stops rejecting true specifics.
8. **Two-pass research.** After the first pass, Python counts claims per
   section. Sections under a threshold get two follow-up questions from the
   planner, bounded by the question budget. This is what v3's fact checking
   is good at feeding, and it fills the sections that otherwise come back as
   "no source addressed this".
9. **A data question type.** Let the planner mark a question `kind: data`.
   The researcher answers it with a table: rows of label, value, unit, source
   URL, verbatim quote. Python writes `data/<name>.json`. The verifier checks
   the rows like any other claim. This is the raw material for graphs.
10. **Verify by priority and in batches.** Keep the number-first ordering,
    raise the cap, and let one verifier turn check up to five related claims
    against one source when they share a URL. Verification cost then scales
    with sources, not claims.
11. **Extend `ungrounded_identifiers`** to percentages, version strings,
    four-digit years, and integers above 100. Every one printed in the body
    must appear in the corpus. This is cheap and catches the fabrications
    readers actually find.

### Phase 3: prose that reads like v2

12. **Ship a style file.** Put the v2 writing guidance in
    `plugin/skills/style/STYLE.md` (SDK) and `skills/writer/style.md` (Deep
    Agents) and load it into the writer and editor prompts. The current writer
    prompts are mostly prohibitions. Prohibitions produce short prose. The
    style file should say what good looks like: lead with the finding, define
    on first use, one mechanism per paragraph, a worked example per section,
    a comparison table where two things are contrasted, a limitations section
    that names what the evidence does not cover.
13. **Add an editor role.** One pass over the assembled paper with `Read`,
    `Write` scoped to `sections/**`, and no search. It improves flow, adds
    transitions and definitions, removes repetition, and may not add a
    specific. Then re-run every deterministic check. The checks are what make
    an editor safe: any number or name the editor invents fails `sourced`.
    Writer then editor is the v2 shape, and it is the piece sol3 never ported.
14. **Put Opus on the writer, editor, and judge.** Set `model` per
    `AgentDefinition` in the SDK port and per subagent in the Deep Agents
    port. Researcher and verifier stay on Sonnet.
15. **Structure the paper like a white paper.** Planner target: executive
    summary, background and definitions, four to eight body sections with
    subsections, at least one comparison table, recommendations, limitations,
    glossary, references. Add a soft `length` row per section and a `depth`
    row to the judge rubric.
16. **Retry only the failed section** in the Agent SDK port. Map judge issues
    to sections and delete only those files before the next attempt, as the
    Deep Agents port already does.

### Phase 4: real graphs

17. **A chart phase between diagram and write.** Input: `data/*.json` from
    item 9. A `chartist` role with read tools only returns a chart spec: type
    (bar, line, grouped bar, scatter), which columns, axis labels, caption.
    Python renders it with matplotlib in the Arctic Fox palette to
    `charts/<name>.png`, and writes a sidecar naming every data row and its
    source. No model touches the pixels. A deterministic `charted` row checks
    that every value in the chart data is in the corpus and that the caption
    cites the sources. This is the only way a graph in the paper can carry the
    same guarantee as a sentence in it.
18. **A deterministic diagram fallback.** Keep `imagen-diagrams` as the
    publication renderer, and add a Mermaid CLI render as the fallback when no
    image backend is available, marked in the sidecar as `fallback`. A run
    with no Gemini or Grok key should still produce a paper with figures. The
    E2E lane can keep requiring the imagen render.
19. **PDF.** `pdf_report.py` already embeds figures. Add the charts and a
    figure list. No other change.

## What not to change

- The role table, the write scope, and the no-shell rule. They are the lesson
  and they are not what makes the paper short.
- Python-owned assembly, the reference list, and the three exits.
- The independent verifier that never sees the researcher's answer.
- The `sourced` and `grounded` rows. Extend them; do not loosen them.
- The standalone-folder rule. Every item above is copied into each port.

## Cost and time to expect after these changes

| Profile | Words | Verified claims | Figures | Cost | Wall clock |
| --- | --- | --- | --- | --- | --- |
| demo (today) | 800 to 1,500 | 12 to 24 | 1 to 2 | under $5 | 5 to 10 min |
| paper | 3,000 to 4,000 | 30 to 40 | 2 to 3 diagrams | $10 to $20 | 15 to 25 min |
| white paper | 5,000 to 8,000 | 50 to 80 | 3 diagrams, 2 to 4 charts | $25 to $50 | 30 to 60 min |

These are estimates from turn counts, not measurements. The first live run
under the paper profile should record actuals in `.harness/state.json` and
the SPEC should quote them.

## Suggested order of work

1. Phase 1 items 1 through 6 in the Agent SDK port. One day. Run one live
   paper on a non-loop topic and keep the output as the new fixture.
2. Copy phase 1 to the Deep Agents port.
3. Phase 2 items 7, 9, and 11, then phase 4 item 17, in the SDK port. That
   is the first run with a real graph in it.
4. Phase 3 items 12 through 14. Compare the same topic before and after the
   editor pass.
5. Copy to the Deep Agents port, then the rest.
