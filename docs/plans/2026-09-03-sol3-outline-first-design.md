---
date: 2026-09-03
slug: sol3-outline-first-design
title: An outline-first white-paper pipeline for sol3, drawn from book-gen, book-gen2, and booksurf
git_base: "b93e8765"
branch: claude/sol3-research-agent-review-6tvdak
---

# Outline-first design for the sol3 research ports

Recommendation only. No code in this change. This continues
[the sol3 review](2026-09-02-sol3-white-paper-review.md), which compared
sol3 against articles v2, v3, and the harness engineering book. This doc
adds the three book pipelines and turns the findings into one proposed
shape.

The three repositories were read in a sibling session and recorded in the
"Book Pipelines Digest" artifact. Quotes and numbers below come from that
read at book-gen `d908b38`, book-gen2 `bc68769`, booksurf `c755ce5`.

## The proposed shape

Rick's proposal: start with an outline the way book-gen does, get the
outline approved, then move forward section by section. Opus 5 approves the
outline. Haiku summarizes, and the summarizer pulls out salient facts,
numbers, and decisions rather than paraphrasing.

That shape is right, and each of the three book pipelines has already paid
for one of its lessons. book-gen proved the two-level outline. booksurf
proved the human approval gate and then threw the approved outline away
before writing. book-gen2 proved that Python must own validation and
assembly, and that a summarizer that keeps the first ten sentences carries
no facts. The design below keeps what each one proved and avoids what each
one broke on.

## The three book pipelines in one table

| | book-gen | book-gen2 | booksurf |
| --- | --- | --- | --- |
| Status | working, about 30 books run, frozen Nov 2025 | partial, abandoned Dec 2025, no finished book | production, active, 506 commits |
| Runtime | Python, LiteLLM API calls | Python driving `claude -p` and `opencode run` subprocesses | Python, official SDKs, Postgres job queue on Cloud Run |
| Outline schema | title, objective, sections with topic bullets | adds prerequisites, estimated pages, estimated length, appendices | book-gen's plus include-exercises, bounded to three levels |
| Outline review | one model feedback pass and one recency pass, auto-applied, no gate | none | human gate with edit, reorder, delete, add; one feedback pass on request |
| Does the outline reach the writer | yes, whole TOC in every prompt | yes, agent reads `toc.yaml` | no, only title and summary survive `apply_toc` |
| Memory between chapters | none | first N sentences as bullets, depends on parallel timing | 4 to 8 sentence synopsis of the last two chapters, often truncated away |
| Sections | parallel, blind to siblings | sequential per call, blind to siblings | parallel, six threads, blind to siblings |
| Review loops | evaluate then rewrite, twice, then proofread, no score | weighted rubric 0 to 1, threshold 0.7, at most 3 iterations | book-gen's loops capped at 2 and 1, voice-first rubric |
| Research | "pretend you have access to the web search" | agent MCP tools inside the review loop, findings never applied | Perplexity recency rewrite after drafting |
| Figures | prose placeholder | Mermaid and PlantUML rendered and validated, keyword-planned | three-tag contract, spec to text-safe SVG, image model with judge |
| Data charts | none | none | none |
| Cost tracking | thread-local tokens, stale prices | none | per-job tokens and cents |
| Resume | `--start-chapter` only | history tree with md5 and phase detection | job retry and orphan recovery; section resume ineffective |
| Hard numbers | none | none | about $2.50 for a TOC plus one chapter on Sonnet 4.5; chapters of 4,511 to 6,801 words against a 5,000 cap |

## What each one paid for

**book-gen worked because of the two-level outline.** A book-level TOC a
human can read on one screen, then a per-chapter outline with key points and
exercises generated just before writing. The whole TOC goes into every
downstream prompt as the coherence anchor. Every artifact is versioned on
disk. Evaluate and rewrite are separate prompts. What did not work: no
approval gate, no memory between chapters, sibling sections drafted in
parallel and blind to each other, no research at all, and a lock-based
status manager that was ripped out and never replaced.

**book-gen2 proved a negative.** Every model step ran as a coding-agent
subprocess, and the plan documents record what that produced: "7 empty
section files", "Just '## Content to be added'", one section saved as a
whole chapter, and "Only 3 of 15 chapters completed". The lesson written the
next day is the one sol3 already follows: "Agents generate artifacts, Python
validates and assembles." Its history tree with md5 hashes and
phase-detecting resume is the strongest state design of the three. Its
summarizer keeps the first ten sentences of a section and carries no facts.
Its recency researcher produced 65 real, dated findings that the pipeline
never fed back into the text.

**booksurf proved the human gate and tiered routing.** Users edit, reorder,
delete, and add outline rows, then approve with a timestamp. Tasks route to
fast, heavy, or research tiers with an escalated flag. A blind bakeoff
showed a 25 times cheaper model tying Sonnet 4.5 on a rubric. Structured
outputs with bounded schemas ended the prose-instead-of-JSON failures.
What broke: `apply_toc` keeps only title and summary per chapter and rebuilds
a placeholder outline with one "Overview" section, so the section tree the
human approved never reaches the writer. Context is assembled to 20,000
characters in one place and cut to 4,000 in another, and the prior-chapter
synopses appended last are what gets cut. Word budgets log overruns and
enforce nothing. The proofread pass changed zero words in all four
checked-in runs.

## The pipeline, phase by phase

sol3 keeps its ten-phase skeleton, Python-owned state, the three exits, the
role table, and the write scope. The change is what the phases carry. Two
phases are new (outline judge, ledger), two are reshaped (plan becomes
outline, research and write become per-section and forward-only), and one
gate is added (approval).

### Phase 1: outline

The planner becomes an outliner and returns a two-level outline through
structured output. This is book-gen's TOC schema plus the fields no book
pipeline had and a white paper needs. Per section:

```
OutlineSection {
  id, heading, objective,
  abstract,                     # two or three sentences
  key_questions[],              # what the research phase must answer
  claims_to_support[],          # what the section will assert
  required_evidence[],          # spec, benchmark, version table, incident
  word_target,
  figures[{name, kind: diagram | chart, shows, data_needed}],
  depends_on[]                  # earlier section ids
}
Outline { title, audience, thesis, sections[], word_target_total }
```

Schema in the prompt and native structured output on the call, bounded and
non-recursive. book-gen2 learned that a prompt saying "SECTIONS MUST BE
OBJECTS, NOT STRINGS" with a validation checklist cut schema failures;
booksurf learned that `output_format` on the SDK ends the rest. Both
ports already have `output_format` plumbing.

Python validates before anything else sees it: ids unique, `depends_on`
acyclic and backward-only, word targets sum to the profile's total within
ten percent, every chart figure names its `data_needed`, every section has
at least two key questions. The validator's exact error text is the retry
prompt, which is book-gen2's one mechanism that worked.

Model: Sonnet 5 (`claude-sonnet-5`) for the draft. Opus 5 for the judge
below, where the judgment lives.

### Phase 2: outline judge

An Opus 5 (`claude-opus-5`) judge with adaptive thinking scores the outline
and returns a verdict:

```
OutlineVerdict {
  passed, score,
  blocking_issues[{section, rule, description}],
  actionable_changes[]          # five to ten, each applicable to one field
}
```

The rubric starts from book-gen's `TOC_FEEDBACK`, which is the only outline
rubric any of the three repos has: logical flow, accuracy and recency,
completeness, redundancy, titles. Add the white-paper rows: every key
question is answerable from a primary source, every claim to support has a
matching required evidence entry, every figure is earned by the abstract
and no chart lacks a data source, word targets fit the audience, and the
limitations section exists.

What book-gen lacked is the part that matters: a verdict and an iteration
cap the code reads. book-gen's `max_iterations: 3` is dead config;
book-gen2 has no outline judge; booksurf runs one pass on request. Here the
loop is judge, then outliner re-emits with the actionable changes, at most
three times, and `gates.decide` handles a repeated signature as a stall the
way it already does for the writing cycle. `passed` from the judge wins over
the numeric score.

The judge holds read tools only and writes nothing, like the existing
research judge. Python writes `outline.json` and `outline-verdict.json`.

### Phase 2b: approval

Optional, and the real gate when it is on. booksurf's version is the model:
the outline is editable rows, approval is an explicit act with a timestamp,
and an edit after approval drops the state back so the judge runs again.

For a CLI this is `--approve`: write `outline.md` alongside the JSON, print
it, and stop with exit code 3 and a message naming the file. The operator
edits `outline.md` or `outline.json`, then re-runs with `--resume`. Python
diffs the edited outline against the judged one; a changed outline gets one
more judge pass before it is stamped `outline.approved.json` with the
timestamp and the hash. Without `--approve`, the judge's pass is the
approval and the same stamp is written with `approved_by: judge`.

The stamped outline is the single input to every later phase, unchanged.
That sentence is the whole lesson of booksurf's `apply_toc`. Per-section
word targets, figure plans, and key questions all come from this file, not
from a re-derivation.

### Phase 3: research, per section, forward order

For each approved section in order, an evidence pass keyed to its
`key_questions` and `required_evidence`. This is the existing researcher
and verifier, with three changes from the review doc: findings are typed
(claim, evidence quote, source, `evidence_strength`, `answers_question`,
`counterargument_to`), the corpus is the full retrieved text rather than
snippets, and a `kind: data` question returns a table of label, value,
unit, source, quote for every chart the outline planned.

book-gen2's recency JSON shape is worth keeping for the verifier's output,
because its 65 checked-in reports prove the shape works in practice:
`verified[{claim, status, source, confidence}]`, `outdated[{claim, current,
recommendation, source}]`, `unverified[{claim, reason}]`. What book-gen2
never did was feed those back. Here they are the writer's input.

Python writes `knowledge/<section>/findings.json` and `data/<name>.json`.
A section whose findings do not cover a key question gets one follow-up
research turn, bounded by the question budget, and then a `coverage_gap`
entry the judge can see.

### Phase 4: write, per section, forward order, sequential

One writer turn per section, in outline order, never in parallel. All three
book pipelines draft sibling sections in parallel and then lean on a
proofread pass to reconcile them; booksurf's checked-in chapter repeats a
sentence verbatim across two sections, and its proofread changed nothing.
Forward order costs wall-clock time and buys coherence. A white paper of
eight sections is eight sequential turns, which is fine.

The writer's context is assembled in one function with named slots in
priority order and a token budget per slot, with a log line for what was
cut. This is the fix for booksurf's two-place truncation that silently
dropped the synopses:

1. Style and register rules, plus the craft levers from the review doc.
2. The approved outline, whole. It is small.
3. The paper ledger so far, whole. Also small, see phase 5.
4. The previous section's full text.
5. This section's findings and the evidence excerpts they cite.
6. The retry instruction, if any.

The prompt states the section's `word_target` and booksurf's "how to stay
within budget" tactics, and the synthesizer contract from the book digest:
write three to eight paragraphs per subsection from these findings, weave
citations into the prose, hedge weak evidence, never invent a specific. A
deterministic validator runs before any judge: word count between 0.6 and
1.25 times the target, no stub markers, every key question addressed by a
paragraph that names it, every specific cited, every planned figure
referenced. Its error text is the retry prompt. Over budget gets "cut to N
words and keep every claim in the ledger"; under budget gets the list of
key questions not yet answered.

Model: Opus 5 for the writer by default. The bakeoff evidence says cheaper
models tie on a rubric, so the paper profile can route the writer to Sonnet
5 once a run has been measured. The ledger, not the model, is what carries
quality between sections.

### Phase 5: ledger, per section, Haiku

After each section passes its validator, a Haiku 4.5 (`claude-haiku-4-5`)
summarizer extracts a structured ledger entry through structured output:

```
SectionLedger {
  section_id, heading,
  claims[{claim, evidence_ref, confidence}],
  numbers[{value, unit, measures, source_ref}],
  decisions[{decision, rationale}],
  terms_defined[{term, definition}],
  open_questions[],
  forward_refs[]                # things promised for later sections
}
```

This is booksurf's `CHAPTER_SUMMARY` goals ("key concepts, methods, or
techniques introduced; important examples, results, or case outcomes;
dependencies and assumptions; definitions that must carry forward; open
questions") with the output changed from four to eight sentences of prose
to a record the next writer and the final judge can check against. It is
the opposite of book-gen2's first-ten-sentences summarizer.

Python appends it to `paper_ledger.json`. The next section's writer is told
"do not re-define a term in the ledger, do not restate a claim in the
ledger, resolve any forward reference that names this section". The final
judge uses the ledger to check cross-section consistency: a number that
appears with two values, a term defined twice, a forward reference never
resolved. The chart phase reads `numbers[]` as one of its data sources.

The summarizer is routed to Haiku explicitly. booksurf's synopsis path
resolved to Sonnet at 64,000 max tokens because it used the provider
default; this pipeline names the model per role in `roleplan.py`.

### Phase 6: figures

Diagrams first through a deterministic Mermaid render, validated, with the
imagen raster as an optional second file judged by the existing fidelity
judge. Charts rendered by Python with matplotlib from `data/*.json` and the
ledger's `numbers[]`, from a spec a read-only role returns: chart type,
columns, axis labels, caption. A `charted` row proves every plotted value is
in the corpus. booksurf's decision rule belongs in the outliner's prompt:
"if the visual would look wrong with garbled or misspelled labels, it is a
diagram, not an illustration", and for this pipeline, if it plots a series,
it is a chart and needs a data table.

### Phase 7: assemble, check, review, edit

Assembly stays in Python. The check rows gain `outline_coverage` (every
approved section present and every key question addressed), `length` per
section (soft) and per paper (hard, the profile's floor), `charted`, and
`ledger_consistency`. The judge gains depth and repetition rows and reads
the ledger. The editor pass from the review doc runs once over the
assembled paper with "do not add new facts" and the checks re-run after it.
Retry rewrites only the sections named in the verdict.

### Phase 8: publish

Unchanged.

## Model routing

Named per role in `roleplan.py`, which both ports already treat as
authoritative, so a summarizer cannot drift onto the heavy tier by default.
Prices are Anthropic first-party per million tokens.

| Role | Model | Why | Input / output |
| --- | --- | --- | --- |
| outliner | `claude-sonnet-5` | structured draft, judged by a stronger model | $2 / $10 |
| outline judge | `claude-opus-5` | the one judgment the whole paper depends on | $5 / $25 |
| researcher, verifier | `claude-sonnet-5` | many turns, tool-heavy, checked deterministically | $2 / $10 |
| writer | `claude-opus-5` by default, `claude-sonnet-5` in the paper profile after measurement | prose quality shows most here | $5 / $25 |
| ledger summarizer | `claude-haiku-4-5` | extraction from a section it has just read, structured output | $1 / $5 |
| chartist, diagrammer | `claude-sonnet-5` | returns a spec, Python renders | $2 / $10 |
| editor | `claude-opus-5` | flow and definitions, no new facts | $5 / $25 |
| final judge | `claude-opus-5` | depth, repetition, ledger consistency | $5 / $25 |

The Deep Agents port names models with the `anthropic:` prefix and the
Agent SDK port sets `model` on each `AgentDefinition`; the table is the
same in both.

Every Opus 5 call runs with adaptive thinking, which is the default when
the `thinking` parameter is omitted. The judge and editor run at effort
`high`. The summarizer runs at effort `low`.

## Cost and time, estimated

A run with eight sections, a profile floor of 5,000 words, three charts,
and two diagrams, with input tokens dominated by the evidence excerpts and
the ledger, is on the order of:

| Phase | Turns | Estimate |
| --- | --- | --- |
| outline, judge, up to 3 rounds | 6 | $2 to $4 |
| research and verify, 8 sections | 40 to 60 | $8 to $15 |
| write, Opus 5, 8 sections plus retries | 10 to 12 | $8 to $14 |
| ledger, Haiku | 8 | under $1 |
| figures and charts | 8 to 12 | $1 to $2 |
| check, judge, editor, one retry cycle | 6 | $4 to $8 |
| total | | $25 to $45, 30 to 60 minutes |

For calibration, booksurf measured about $2.50 for a TOC plus one 6,800
word chapter on Sonnet 4.5 with no research and no verification; v3 spends
$25 to $58 on a 6,000 word article. These are estimates from turn counts.
The first live run records actuals in `.harness/state.json` and the SPEC
quotes them.

## What to avoid, named

Each of these is a failure one of the three repos shipped.

- Discarding the approved outline before writing (booksurf `apply_toc`).
- Assembling context in one place and truncating in another
  (booksurf, 20,000 then 4,000 characters, synopses cut first).
- Parallel sibling sections plus a proofread to reconcile them
  (all three; booksurf's proofread changed zero words).
- A summarizer that keeps the first N sentences (book-gen2 watcher).
- A summarizer on the heavy model by provider default (booksurf).
- Research as a post-draft rewrite (booksurf recency pass) or research
  findings never applied (book-gen2's 65 reports).
- Agents running procedures: validation, assembly, file naming, state
  (book-gen2's empty files and misnamed sections).
- Length limits that log and never enforce (booksurf, 36 percent over).
- Hard-coded budgets duplicated across prompts (booksurf, three
  inconsistent chapter budgets).
- LLM-rewritten prompt template cascades (booksurf, eight derivation calls
  per book and a long tail of fixes).
- `except: pass` around anything that decides pipeline state (booksurf's
  dead cross-chapter review, unreachable recency refinement).
- Timeouts as the only budget (book-gen2 at 100-minute per-call timeouts).
- An outline judge whose iteration cap is dead config (book-gen).

## What sol3 keeps

- The role table and write scope. New roles: outliner (writes nothing,
  Python writes `outline.json`), outline judge (writes nothing), ledger
  summarizer (writes nothing, Python appends the ledger), chartist (writes
  nothing, Python renders). The writer stays the only role with `Write`,
  scoped to `sections/**`.
- Python-owned assembly, the reference list, `gates.decide`, and the three
  exits. Stall detection now also covers the outline loop.
- The independent verifier, the `sourced` and `grounded` rows, and the
  publish gate.
- One state store per port, `.harness/state.json`, with a phase file per
  artifact. book-gen2's md5 per section at assembly is worth adding so an
  edited section forces reassembly.
- The standalone-folder rule. Every phase above is copied into each port.

## Order of work

1. Outline schema, outliner, outline judge, and the approval stamp in the
   Agent SDK port, with the validator and the retry-on-error loop. Run it
   on three topics and read the outlines. This is a day and it is the part
   a human can evaluate without a paper.
2. Forward-only per-section research and write, the context assembler with
   named slots, the length validator, and the Haiku ledger. Run one paper.
3. Charts from data tables and the `charted` row. Run the same paper.
4. Editor pass, judge rows, section-only retry.
5. Copy to the Deep Agents port. Then the phase 1 unblocking items from the
   review doc that are not already covered here: the credibility tier in
   place of the fixed allowlist, and scoping the exit doctrine to the E2E
   lane.
