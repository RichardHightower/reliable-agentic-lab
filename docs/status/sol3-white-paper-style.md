# Sol 3. White paper house style

Epic: [#445](https://github.com/RichardHightower/reliable-agentic-lab/issues/445).
Plan / queue: [[Sol-3-White-Paper-Style-Plan]].
Repo copies: `docs/status/sol3-white-paper-style.md`, `docs/plans/2026-09-07-sol3-white-paper-style.md`.
Ship record: [[Sol-3-White-Paper-Loop]].

Tickets cite this page. Do not implement from chat.


Date: 7 September 2026.
Applies to both ports: `solutions/sol3_research_agent_sdk` and
`solutions/sol3_research_deep_agents`.
Ship record: [[Sol-3-White-Paper-Loop]].
Two shops: [[Sol-3-Two-Shops]].
Plan: `docs/plans/2026-09-07-sol3-white-paper-style.md`.

This page is the house style. Writer cards, reviewer cards, and
`paper_check` all cite it. It is not a brochure guide and not a journal
stylesheet. It is the contract for a cited engineering briefing.

Hold implementation until the epic under this page is scheduled.

## What this paper is

An authoritative, evidence-based briefing. It explains a problem and a
design. A colleague can use it. The Saturday lab already produces a
cited brief. Sol 3 produces the longer document.

It is not a blog post, a Medium article, a sales deck, or a product
one-pager.

About 90 percent of the page is education: problem, mechanism, evidence,
limits. The last prose section is a next-step call to action. That CTA
is not marketing.

## Language: STE-100 principles, not the aerospace dictionary

The seminar writes **Simplified Technical English** in the sense of
ASD-STE100 *principles*. The local skill pack is
`ste100` (`rules.md` STE-S1 to STE-S15). Sol 3 does **not** load the
official ASD dictionary and does **not** run the STE editor/adversary
loop on the paper. That loop is for procedures and runbooks.

The paper is descriptive prose with citations. Apply the subset a
briefing can keep without fighting bound claims:

| ID | Rule in this paper |
| --- | --- |
| STE-S1 | Description sentences: target 15–20 words, hard cap 25. |
| STE-S2 | One idea per sentence. |
| STE-S3 | Active voice. Name the actor. |
| STE-S5 | No noun stack longer than three. |
| STE-S6 | No contractions. Write `do not`, not `don't`. |
| STE-S7 | No Latin abbreviations. Write `for example`, not `e.g.` |
| STE-S8 | No vague fillers: very, quite, maybe, generally. |
| STE-S11 | No semicolons. Two sentences. |
| STE-S14 | One meaning, one word. After you name it, keep that name. |

Do **not** apply procedure-only rules to the whole paper:

- STE-S9 (no should / could / might / may in steps) does not ban a
  hedge on an unverified claim. An unverified claim stays qualitative.
  It is not upgraded into a procedure step.
- STE-S13 preferred substitutions must not rename a bound term. If the
  claim says "orchestrator", the paper says "orchestrator".
- The imperative procedure template is not the paper template.

Preferred substitutions that do not touch bound terms: use (not
utilize), start (not commence), stop (not terminate), to (not in order
to), before (not prior to), after (not subsequent to), show (not
indicate).

## Jargon

New technical terms are allowed. They are required when the claim uses
them.

A term is new when a busy colleague outside this seminar would not
already treat it as ordinary English. On first use:

1. Use the term.
2. Define it in that same sentence, or in the next sentence.
3. Put that same definition in the glossary.

`defines_terms` already fails a term used before it is defined. This
page adds the glossary half of the same rule.

## Voice

Third person. Active voice. Name the actor.

- Good: "The orchestrator charges the budget before the writer runs."
- Weak: "The budget is charged." / "You should charge the budget." /
  "We will now look at the budget."

No second person. Never "you", "your", or "if you implement it". Name
the actor instead: "an implementer", "the host", "a client". The SDK
writer card already says this. The Deep Agents card does not, and it
must.

No first-person tour: "we will", "our pipeline", "in this article we".
"We" meaning the cited authors of a source is allowed only when the
sentence is a paraphrase of that source and carries `[n]`.

American spelling. Serial comma. No em dashes.

## What does not belong

- A hook, a cold open, or a question to the reader
- "Let's dive in", "under the hood", "think of it as", "it's basically"
- An analogy or a metaphor in place of a mechanism
- A rhetorical question
- Marketing verbs: leverage, unlock, empower, revolutionize, seamless,
  robust
- A conclusion that only restates the introduction
- Narration of the run: research pass, verification pass, budget, tool,
  allowlist, "no study was hosted on arxiv.org"
- Search-host names in the body. The reference list is exempt.

The reader is reading about the subject. They are not reading how the
paper was made. That is #412.

## Evidence, not opinion

Every material claim is a bound claim. The writer may use only the claim
ids named for that section.

| Kind of claim | What the sentence must carry |
| --- | --- |
| Finding | The claim text, then `[n]` |
| Mechanism | Which component does the work, in what order, and what happens if it is missing |
| Tradeoff | The alternative and the cost of this choice |
| Limit | Single source, vendor documentation, or no production measurement. Say so. Do not upgrade it. |
| Disputed | Both sides, named. Never pick a winner. |
| Unverified | Qualitative, or omit. No number, version, or date. |

Cite with `[n]`. Never an inline markdown link, never a bare URL, never
a footnote, never APA or IEEE in the body. Assembly owns the reference
list and the global numbering. A paragraph that asserts something and
carries no marker fails a deterministic check.

Do not invent a specific to look sourced.

## Structure

Outline-first. The approved outline is the TOC. Headings are informative
statements, not pasted research questions.

- Bad H3: "What methodology, trace count, and failure-category percentages does the MAST taxonomy paper report?"
- Good H3: "MAST reports failure categories from 1,600 traces"

A white paper answers questions. It does not title subsections with
them. That is #385. Coverage scores whether the question is *answered*
in the body. It does not require the question string as a heading.

Recommended arc:

1. Title. Specific, active, topic-clear.
2. Abstract. Stand-alone. 120 to 180 words. Do not inflate this to a
   350-word brochure summary.
3. Context.
4. Problem, with evidence.
5. Approach or options. Framework first.
6. Evidence and figures.
7. Limits.
8. Next step. The CTA. Last prose section.
9. Glossary. Assembled. Every new term.
10. References. Assembled. The writer never writes this section.

Word targets stay as they are in the writer cards. Pipeline floor:
2,000 words on every profile. Do not invent facts to hit a count.

## Next step (non-marketing CTA)

The paper ends its prose with a next-step section. It tells a colleague
what to do with the findings. It does not sell.

Allowed shape:

- "Evaluate X on a live ticket."
- "Run the fixture with `--doer none`, then with `--doer reference`."
- "Compare the two ports on the same outline."
- "Measure Y before changing Z."

Forbidden in that section: buy, sign up, get started today, revolutionize,
unlock, only solution, contact sales, subscribe.

The CTA may use imperative verbs. That is the one place STE procedure
shape is welcome. Keep each step under 20 words.

## Glossary

Assembly owns the glossary, the same way it owns the reference list. The
writer does not write a Glossary heading. A second glossary from the
writer leaves the reader with two lists.

Every new term that was defined on first use appears once, alphabetically:

```
## Glossary

**orchestrator.** The process that sequences roles and does not write
the paper.
```

A term used and never defined fails `defines_terms`. A defined term
missing from the glossary fails `glossary_complete`. A glossary entry
for a term the body never uses fails `glossary_exact`.

Do not put citations, figures, or the CTA in the glossary.

## Figures

A figure earns its place when it shows something the adjacent prose does
not say in one line.

Each placed figure is three things:

1. The image line, with alt text that describes what the figure shows.
2. A caption line: `Figure N. <one sentence from the diagram record>`.
3. At least one in-text "Figure N" in the surrounding prose.

After the image, three to five sentences on what the figure makes
visible. Never paste diagram source into the paper.

A skipped figure is named in the owning section, with the reason already
in the log. Silence is the defect. That is #386 and #413.

## Who owns which rule

Python owns the belt. The model does not vote on these:

- `you` / `your` in the body
- `we will` / `in this article`
- banned marketing verbs
- contractions and `e.g.` / `i.e.` / `etc.`
- em dashes and semicolons
- dangling `[n]`
- paragraph with no citation marker
- question-string used as an H2/H3
- search-host / allowlist / "no study was hosted on" (`policy_leak`)
- image without a following `Figure N.` line (`captioned`)
- `Figure N` never mentioned in prose
- skipped figure with no note
- missing Glossary section, or a term defined in prose and absent there
  (`glossary_complete`)
- last prose heading is not the next-step / CTA section
- word-count floor and section word_target band

The reviewer / section judge owns judgment:

- `defines_terms` (definition is actually a definition, not a circular
  restatement)
- `states_mechanism`
- `names_tradeoff`
- `evidence_matches`
- `scope_honest`
- `no_filler`
- `depth`
- `voice` (hook, metaphor-as-mechanism, rhetorical question, leftover
  marketing the belt missed)
- `figure_earns_place`
- CTA is a next step, not a restated introduction

Do not report a mechanical failure from the judge.

## Ports

Same style. Different fence. Copy the writer card and the check rows.
Do not import.

Deep Agents currently omits the no-second-person rule and the "never
write about the run" rule. Neither port writes a glossary or a CTA
section today.

Saturday `labs/lab3_*` stays the short cited brief. Do not copy these
fences into it. Do not invent `loops/`.

## From each style guide

There is no single official white paper stylebook. These ports pick one
house style and stay consistent. Below is what this page takes from the
usual guides, and what it leaves because the loop already decided.

| Guide | Take | Leave | Why |
| --- | --- | --- | --- |
| Purdue OWL white papers | Authoritative tone, not promotional. Front-load problem and analysis. Informative headings. Evidence for every material claim. Recommendations in the last third. About 90 percent education. | Brochure voice. Product positioning in the front. | Matches the writer cards. A sales open fails `voice`. |
| George Mason White Paper Quick Guide | Problem–solution briefing. Policy-neutral analysis before a next step. | Public-policy memo layout. | The outline already is problem → approach → limits. The CTA is the next step. |
| Gordon Graham (That White Paper Guy) | One house style. Headings, lists, and a figure where the outline planned one. Do not dress the page like a sales deck. Consistent names. | B2B product paper. Print line length 45–75. Pull quotes. Multi-column layout. "Figure on most pages" as a quota. | The artifact is GitHub markdown. Assemble owns figures. A quota would invent charts. |
| IEEE citation practice | Numbered `[n]` in the body. Numbered reference list at the end. | Author–date. Footnotes. | Assemble already prints this. APA author–date would break the registry belt (#384). |
| APA 7e | Evidence honesty. Define a term on first use. Do not overclaim. | Author–date citations. Running head. 350–500 exec summary as a floor. | Abstract stays 120–180 on a 2,000-word paper. |
| AP Stylebook | American spelling. Consistency on names and acronyms. Gender-neutral wording. No competitor smears; facts only. | AP's no-serial-comma default. AP news lede. | These ports keep the serial comma. That is IEEE/Chicago, not AP. |
| GOV.UK style | Plain English. Short paragraphs. Say what the reader can do next. | UK spelling. Public-sector service voice. | STE-adapted English is the plain-English belt. CTA is the next step. |
| ASD-STE100 (local `ste100` skill) | Descriptive subset: ≤25 word sentences, one idea, active voice, no contractions, no `e.g.`, one word one meaning, noun cluster ≤3. | Official dictionary. Procedure template. Ban on `may`/`might`. Editor/adversary loop on every section. | A briefing must name uncertainty. Bound terms stay as the claim named them. |

### Skim test (Purdue + Graham)

A reader who only reads the abstract, the headings, the figures, the
glossary, and the next-step section should still know: the problem, the
approach, the limit, and what to do. If that skim fails, the headings
are labels, not claims, and story 5/8 / 2/6 applies.

### Bias (Purdue + AP)

No competitor smear. No "only solution". Comparisons are verifiable
facts with `[n]`. Vendor documentation is named as vendor documentation.

### Design that survives markdown (Graham, reduced)

- One column. GitHub already does this.
- Heading hierarchy: H1 title, H2 sections from the outline, H3 for
  answers inside a section. Not a question as a heading.
- Lists when the reader is scanning steps or limits.
- A figure only when the outline planned one, then caption + in-text
  `Figure N`.
- Do not add a cover, a pull quote, or a sales footer.

## Related tickets

- #385 coverage still turns key questions into published headings (SDK)
- #386 a skipped chart leaves no trace in the paper (SDK)
- #412 the writer narrates the source policy (Deep Agents)
- #413 figures have alt text but no caption and no in-text reference
  (Deep Agents)

Those four are related implementation stories. They are not re-filed.

## Out of scope

- #405 thick pack / scout relevance
- #409 provider connection retry
- #411 review stall / resume memory
- Official ASD-STE100 dictionary or a networked STE checker
- Running the `ste100` editor/adversary loop on every section
- Switching the body to APA or IEEE citations
- Print layout (line length, contrast, one-column PDF)
