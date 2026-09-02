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
documents. This review explains the gap and recommends what to change so sol3
produces real white papers with graphs on arbitrary technical topics.

The comparison rests on a read of both Spillwave repositories, done in a
sibling session and recorded in the "Spillwave Pipelines Digest" artifact.
Numbers quoted below for v2, v3, and the book come from that read: agent
files, stage code, and the word counts of checked-in finals.

## The one-line diagnosis

sol3 ported v3's checking layer (retry loop, cost cap, verified facts,
grounding contract) and none of the layers that produce prose. It fact-checks
a paper it never lets itself write.

The deeper finding from the comparison is that the Spillwave pipelines do not
win on retrieval depth. v2 and v3 never fetch a page either. They win on
three structural choices: prose exists before evidence is attached, flagging
is the rule and deletion is the exception, and length is set by structure and
a floor rather than by a per-paragraph citation tax. sol3 inverts all three.

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
| Uncited paragraph | fails the `cited` row, retry | deleted before the gate |
| Figures | Mermaid or PlantUML, rendered by an image model | same |
| Data charts | none | none |

## What the Spillwave pipelines do instead

| | articles v2 | articles v3 | harness_engineering_book | sol3 today |
| --- | --- | --- | --- | --- |
| Starting material | author's source files plus an overview with a fixed 5-part structure | same | human outline with an abstract for every one of 171 sections | a topic string |
| Where prose comes from | the author's draft, split into parts | same | a synthesizer writing 3 to 8 paragraphs per section from typed findings | a writer restating one-line claims |
| Research | enrichment pass over existing prose, up to 8 Perplexity queries per part, 4-tier credibility table, no allowlist | same, plus an adversarial pass over up to 40 sampled claims | 15,000 to 22,000 words of vendor deep research per chapter, at least 4 vendors, indexed and queried per outline leaf | one search per question, snippets only, 14-domain allowlist |
| Unverified claim | `NEEDS-SOURCE` flag, `[UNRESOLVED-*]` blockquote after 3 attempts | same, plus verdicts on sampled claims | `coverage_gap`, `<!-- GAP -->`, hedged prose | dropped, or deleted with its paragraph |
| Citation rule | uncited factual claim is a retry trigger, not a deletion | same | 3 to 5 links per chapter, more than 8 is flagged | every paragraph must cite |
| Length control | 5 parts, "within 30%", no article target | same; median of 55 finals is 5,913 words | blueprint per chapter, "5,000 hard floor, 10,000 hard ceiling"; median 8,300 | 90 to 300 words per section |
| Voice and craft | 215-line voice skill run as a whole pass | same | 536-line style guide, two style judges, dictated voice weave | prohibitions only |
| Models | Sonnet everywhere, Haiku for summaries, no `max_tokens` set | same | Sonnet everywhere, Opus only for A/B comparison | Sonnet, 4,096-token cap |
| Cost | not tracked; 58 to 142 agent calls | $25 to $58 per 5-part article, cap $50 | not tracked | $5 cap |
| Figures | imagen illustrations, Mermaid piped into imagen | same | validated Mermaid to SVG, PDF, and 300 dpi PNG, plus optional imagen with a vision judge | imagen only, fails closed without a key |
| Data charts | none | none | one Mermaid bar chart with hard-coded values | none |

Two things stand out. None of the three pipelines generates a data chart from
data, so the graph requirement is new work whichever way sol3 goes. And the
book pipeline, not the article pipeline, is the right model for sol3: it is
the only one that starts from an outline and a research corpus rather than
from an author's draft, which is sol3's situation exactly.

## Why the papers are short

### 1. The writer is fed claims, not evidence

Each research question makes one Perplexity search and keeps the snippets.
The researcher splits those into atomic claims, each one sentence with a short
quote. The writer is told to use only those claims. A question typically
yields two to five claims, so a section is written from three sentences of
material.

The book synthesizer is handed a `ResearchResult` per outline leaf: a list of
findings, each with a claim, an evidence quote, a source, an
`evidence_strength` from 0 to 1, and the key question it answers. It is told
to write "3-8 paragraph synthesis" per section and to hedge weak evidence
rather than omit it. Same shape as sol3's claim list, but the corpus behind
it is a hundred times larger and the writer is asked to synthesize, not to
restate.

### 2. Uncited prose is deleted or fails the gate

The Deep Agents port runs `stages.drop_uncited_prose` before the gate, which
removes every paragraph without a citation marker. The Agent SDK port fails
the `cited` row instead. Either way, a definition, a transition, or a
paragraph of reasoning cannot survive.

In v2 and v3 the research assistant is told "Do NOT remove content, even if
you think it's wrong. Flag it instead." An uncited factual claim is a retry
trigger for the fact checker, and after three attempts becomes an
`[UNRESOLVED-FACT-MAJOR]` blockquote. Opinion, analogy, and author-derived
concepts are explicitly allowed. The book caps external links at roughly
three to five per chapter. No Spillwave pipeline has a citation-per-paragraph
rule.

### 3. The Deep Agents port caps prose on purpose

`paper.py` asks for "90 to 180" or "180 to 300" words per section, and the
writer skill says "do not pad" and "a concise section grounded in two claims
is better than a longer section". The book blueprint says the opposite:
"5,000 is a hard floor; 10,000 is a hard ceiling", and its pedagogy judge
treats a chapter under 1,000 words as a stub.

### 4. The source wall admits fourteen hosts

`source_policy.SEED_ALLOWLIST` is the same short list in both ports:
LangChain, Anthropic, OpenAI, Microsoft Learn, Stripe, MCP, Google SRE, and
this workshop's own GitHub org. A scout pass may add a host whose name starts
with `docs.`, `reference.`, or `learn.`, and nothing else. A topic on
Kubernetes, Postgres, Kafka, Rust, or any IETF standard finds zero admissible
sources and the run escalates.

No Spillwave pipeline has a domain allowlist in code. v2 and v3 use a
four-tier credibility table in the prompt (official docs and papers, then
reputable journalism, then expert blogs, then forums as corroboration only)
and a denylist for gist hosts. The book forbids the live web entirely and
reads a corpus that a human assembled.

### 5. Every paper is forced to be about this repo's loop exits

Both ports bind the first research question to the literal string "What three
exits does this repo's paper loop check, and in what order?"
(`turns.bind_exit_doctrine`, `stages.plan_gate`). The deterministic check then
requires the body to say "done, then cost, then max turns" in that order and
requires Figure 1 to label those exits (`checks.doctrine_failure`,
`paper_check.has_exit_doctrine`). In the Agent SDK port `loop.py` passes
`enforce_research_policy=True`, which turns that row on for every
`task run`, not only for `task e2e-live`.

A paper on "how MCP servers authenticate" cannot pass its own gate unless it
contains a paragraph and a figure about this repository's control loop. This
leaked from the acceptance scenario into the general path.

### 6. Verification is capped low, and the overflow is discarded

Twenty-four verified claims in one port and twelve in the other. Past the
cap, claims stay `unverified` and the writer is told to drop them. v3's
adversarial pass also samples, at 40 claims by priority, but an unsampled
claim keeps its sentence. In v3 only `incorrect` and `misleading` verdicts
delete anything, and the researcher is told not to over-correct historically
accurate claims. Pinned facts from the author protect version strings from a
red-team that never found the primary source.

### 7. Five dollars is one v3 part

v3 records $25 to $58 for a five-part article, with the research stage
taking roughly half. The sol3 SPEC records a run that spent its $5 in
verification and wrote no sections. The default is a demo budget presented as
a paper budget.

### 8. Figures are illustrations, not charts, and fail closed

`diagrams.py` accepts Mermaid or PlantUML and hands it to `imagen-diagrams`,
which renders through an image model and judges fidelity. With no image key
the renderer exits 2 and the run ends with no figure. The `figure_assets` row
rejects any image that is not a `*_imagen.png`.

The book renders tagged Mermaid deterministically with `mmdc`, validates the
SVG against a print spec (node budgets, minimum text size, greyscale
survival), and writes SVG, PDF, and 300 dpi PNG. The imagen raster is an
optional second file, judged by a vision model and embedded only when it
passes. That is the right order: a deterministic render always exists, and
the generative one is a bonus.

Nothing in any of the four pipelines plots data. The book's one bar chart is
a Mermaid `xychart-beta` with hard-coded values and no provenance check.

### 9. Smaller issues that compound

- The Agent SDK port deletes every section on each retry (`CYCLE_OUTPUT`)
  and rewrites all of them. v3 sends only the latest verdict and tells the
  editor to "fix ONLY these issues". The Deep Agents port keeps passing
  sections; the SDK port should too.
- `ungrounded_identifiers` catches arXiv ids, DOIs, and author-year cites.
  It does not catch percentages, version numbers, dates, or benchmark
  figures. v3's pinned-facts guard extracts version-like tokens and backtick
  spans; that regex is worth copying.
- The Deep Agents `WRITER_MAX_TOKENS` of 4,096 is self-imposed. No Spillwave
  pipeline sets `max_tokens` anywhere.
- The judge rubric has no depth or length row, so a thin correct paper
  passes. The book's pedagogy judge and style-fit judge both score depth.
- Model choice is not the lever. All three Spillwave pipelines run Sonnet for
  nearly every role.

## What sol3 already does better

These should not be traded away while fixing the above.

- The verifier never sees the researcher's answer. v2's independence check
  is presence-only: the orchestrator confirms `queries_used` is non-empty and
  never compares queries.
- `sourced` checks every identifier against the retrieved corpus. v3 checks
  citation keys against `facts.md` and source material, and only deletes
  under `--grounded`.
- The gate blocks publish. In v3, `requires_human_review` sets a state flag
  and nothing blocks; every fact-check HTML comment is stripped at publish
  while the flagged sentence ships.
- Python assembles the paper and writes the reference list. v3 concatenates
  part files around model-written bridges, which is how `# Part N:` headers
  leak into finals.
- The cost cap is checked inside phases. v3's S05, S10.6, and S10.7 report
  zero cost, so its totals undercount.

## What to change

Ordered by leverage. Each item is done twice, once per port, by copying, per
`CLAUDE.md`. Prototype in the Agent SDK port first: sections already live as
files, the writer already holds a scoped `Write`, and the plugin structure
makes new roles cheap. Then port to Deep Agents.

### Phase 1: unblock arbitrary topics

1. **Scope the exit doctrine to the E2E lane.** Default `enforce_loop_doctrine`
   to off in `loop.py` and turn it on only from `e2e.py`. Remove the bound
   first question from `turns.plan` unless a brief asks for it. Same for
   `stages.plan_gate` and `paper_check`'s `exit_doctrine` row. The
   commissioning brief is the right place for scenario requirements, and it
   already exists.
2. **Replace the allowlist with a credibility tier.** Keep the post-filter
   wall, change its rule. Copy v2's four-tier table into `source_policy.py`
   as code: tier 1 is official docs, specifications, standards bodies,
   papers, and vendor repositories, matched by host patterns (`docs.*`,
   `*.readthedocs.io`, `ietf.org`, `w3.org`, `arxiv.org`, `github.com/<org>`
   where the org is the project's); tier 2 is a fixed list of engineering
   publications; tier 3 and 4 are admitted only as corroboration and never
   as a sole reference. Keep the denylist. Record every admitted host in
   `plan.json` so a reader can audit the run. Send the per-question tier 1
   hosts to Perplexity, at most twenty.
3. **Fix the `cited` rule.** A paragraph must cite when it contains a
   specific: a number, a version, a date, a name, a quoted phrase. A
   definitional, transitional, or reasoning paragraph without specifics may
   stand uncited. Implement as a deterministic "has specifics" regex.
   Delete `drop_uncited_prose`. This is the single rule that separates a
   paper from a claim list, and no Spillwave pipeline has the current one.
4. **Flag, do not delete.** An unverified claim past the verification cap
   keeps its sentence and gets a `<!-- NEEDS-SOURCE -->` flag, as in v2.
   Only `contradicted` removes a sentence. The `unresolved.json` sidecar
   already exists in the SDK port; make the flags visible in the review
   phase instead of stripping them.
5. **Let charts through the gate.** `figure_assets` accepts `*_imagen.png`
   for diagrams and `charts/*.png` for Python-rendered charts.
6. **Set a length floor, not a ceiling.** The planner emits a blueprint per
   section: purpose, subsections, target words. The whole-paper floor is
   3,000 words for the paper profile. Raise `WRITER_MAX_TOKENS` to 16,384 in
   the Deep Agents port. Add a soft `length` row per section and a hard stub
   row for the paper, copying the book's "under 1,000 words is a stub".
7. **Add a profile.** `--profile demo|paper`: demo keeps today's numbers so
   `task demo` stays cheap; paper sets questions 20, verified claims 60,
   `--max-usd` 40, iterations 3. Print the estimate before the run starts.

After phase 1, a run on any tech topic should produce a three to four
thousand word paper that passes the gates. Nothing in this phase changes the
role table or the tool boundary.

### Phase 2: build the corpus before the paper

This is the book's structure, which is the right one for a topic-in,
paper-out pipeline.

8. **A corpus phase between plan and research.** For each planned section,
   run a deep-research turn that returns an evidence pack of roughly 1,500
   to 3,000 words: sources, verbatim quotes, and the questions each quote
   answers. Perplexity's deep-research model or three to five ordinary
   searches per section both work; the book uses external vendors because a
   human is in that loop, and sol3 should automate it. Store the packs under
   `knowledge/corpus/<section>.md`. The `sourced` corpus becomes these
   packs, so a version number the paper prints is actually findable.
9. **Extract typed findings, not one-line claims.** Copy the book's
   `ResearchResult` shape: claim, evidence quote, source, `evidence_strength`
   from 0 to 1, `answers_question`, `counterargument_to`, plus a
   `coverage_gap` list. The verifier still checks findings independently;
   `evidence_strength` tells the writer how hard to lean on each one.
10. **A gap pass.** After extraction, Python counts findings per section.
    Sections under a threshold get two follow-up questions from the planner,
    bounded by the question budget. Unanswered questions become
    `<!-- GAP -->` comments the judge can see.
11. **A data question type.** The planner marks a question `kind: data`. The
    researcher answers with a table: label, value, unit, source URL, verbatim
    quote. Python writes `data/<name>.json`. The verifier checks the rows
    like any other finding. This is the raw material for graphs and it does
    not exist in any of the four pipelines.
12. **Extend `ungrounded_identifiers`** to percentages, version strings,
    four-digit years, and integers above 100, using v3's version-token regex.
    Every one printed in the body must appear in the corpus.

### Phase 3: prose that reads like v2

13. **A synthesizer contract for the writer.** Replace "use only these
    claims" with the book's instruction: write a 3 to 8 paragraph synthesis
    of these findings, weave citations into the prose, hedge weak evidence,
    do not invent a specific. Hand the writer the section's evidence pack as
    reading material and the numbered findings as the citation set.
14. **Ship a craft file, not a voice file.** v2's voice skill is Rick's
    article voice: rhetorical questions, analogies, humor. A white paper
    should not adopt those. It should adopt the seven craft levers from the
    same skill: show a specific instead of asserting an adjective, marry
    compression to concreteness, lead with stakes then earn the mechanics,
    one memorable spine per paper, vary sentence length on purpose, cut
    throat-clearing, verify every load-bearing specific. Put them in
    `plugin/skills/style/STYLE.md` and load them into the writer and editor.
    Keep sol3's register rules (no second person, no metaphor) as the white
    paper's own voice profile.
15. **Add an editor role.** One pass over the assembled paper with `Read`,
    `Write` scoped to `sections/**`, and no search. It improves flow, adds
    transitions and definitions, removes repetition, and carries v3's
    engagement-editor constraint verbatim: "Do not add new facts." Then
    re-run every deterministic check. The checks are what make an editor
    safe: any number or name it invents fails `sourced`. Writer then editor
    is the v2 shape, and it is the piece sol3 never ported.
16. **Add depth rows to the judge.** Copy two from the book: every section
    opens with the reader's problem, not a definition, and every section
    closes on a line a reader could quote. Add `depth`: a section that
    restates its findings without explaining a mechanism fails.
17. **Retry only the failed section** in the Agent SDK port, sending only the
    latest verdict, as v3's retry loop does.

### Phase 4: real graphs

18. **A chart phase between diagram and write.** Input: `data/*.json` from
    item 11. A `chartist` role with read tools only returns a chart spec:
    type (bar, line, grouped bar, scatter), which columns, axis labels,
    caption. Python renders it with matplotlib in the Arctic Fox palette to
    `charts/<name>.png` and writes a sidecar naming every data row and its
    source. No model touches the pixels. A deterministic `charted` row checks
    that every plotted value is in the corpus and that the caption cites the
    sources. This gives a graph the same guarantee as a sentence, which no
    Spillwave pipeline has.
19. **A deterministic diagram render first.** Copy the book's order: render
    tagged Mermaid with `mmdc`, validate node count and text size, and keep
    that PNG as the figure. Run `imagen-diagrams` as the optional
    publication raster, judged by the existing fidelity judge, and embed it
    only when it passes. A run with no image key still ships figures. The
    E2E lane can keep requiring the imagen render.
20. **PDF.** `pdf_report.py` already embeds figures. Add the charts and a
    list of figures.

## What not to change

- The role table, the write scope, and the no-shell rule. They are the lesson
  and they are not what makes the paper short.
- Python-owned assembly, the reference list, and the three exits.
- The independent verifier that never sees the researcher's answer.
- The `sourced` and `grounded` rows and the publish gate. Extend them; do
  not loosen them toward v3's flag-then-strip behavior.
- The standalone-folder rule. Every item above is copied into each port.

## Cost and time to expect

| Profile | Words | Verified findings | Figures | Cost | Wall clock |
| --- | --- | --- | --- | --- | --- |
| demo (today) | 800 to 1,500 | 12 to 24 | 1 to 2 | under $5 | 5 to 10 min |
| paper, after phase 1 | 3,000 to 4,000 | 30 to 40 | 2 to 3 diagrams | $10 to $20 | 15 to 25 min |
| white paper, after phase 4 | 5,000 to 8,000 | 50 to 80 | 3 diagrams, 2 to 4 charts | $25 to $50 | 30 to 60 min |

For calibration, v3 spends $25 to $58 and 90 to 160 minutes on a 6,000 word
article, most of it in research enrichment and four editor loops per part.
sol3 with Python-owned assembly and one editor pass should land under that.
These are estimates from turn counts, not measurements. The first live run
under the paper profile should record actuals in `.harness/state.json` and
the SPEC should quote them.

## Suggested order of work

1. Phase 1 items 1 through 7 in the Agent SDK port. One day. Run one live
   paper on a non-loop topic and keep the output as the new fixture.
2. Copy phase 1 to the Deep Agents port.
3. Phase 2 items 8, 9, 11, and 12, then phase 4 item 18, in the SDK port.
   That is the first run with a real graph in it.
4. Phase 3 items 13 through 15. Compare the same topic before and after the
   editor pass.
5. Copy to the Deep Agents port, then the rest.
