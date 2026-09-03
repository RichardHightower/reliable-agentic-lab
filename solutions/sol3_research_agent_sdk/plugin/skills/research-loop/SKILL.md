---
name: research-loop
description: Produce an evidence-backed technical white paper from one topic. Plans the paper, researches each question from primary sources, verifies every claim against a second independent source, renders the figures, writes the sections, and checks the result before it ships.
---

# The research loop

This skill is the readable specification of what `paper.py` implements in
Python. Read it to understand the loop.

It is deliberately not loaded as a runnable skill in this port. `options_for`
passes `plugins=` so the agent markdown is visible and does not pass `skills=`,
so the parent cannot invoke this file even if it wants to. Two orchestrators
disagreeing about whose turn it is was the failure, and a sentence asking the
model not to do it was never the fix.

The table below is generated from nothing. It is checked instead:
`tests/test_docs.py` fails when it stops matching
`roleplan.plan(None, "research")`.

## What the loop produces

One markdown file and its figures:

```
work/<slug>/paper.md
work/<slug>/diagrams/*.png
```

Plus the research record that produced them, as an RKC knowledge bundle under
`work/<slug>/knowledge/research/`.

## The cast

| Role | Holds | Writes |
| --- | --- | --- |
| orchestrator | `Task` | nothing |
| outliner | read tools | nothing |
| outline_judge | read tools | nothing |
| researcher | read tools, `WebSearch`, filtered Perplexity, Context7 | nothing |
| verifier | `Read`, `WebSearch`, filtered Perplexity, Context7 | nothing |
| diagrammer | read tools | nothing |
| writer | read tools, `Write` | `sections/**` |
| judge | read tools | nothing |

One role writes. The writer holds `Write`, scoped to `sections/**`, because a
section is long prose and returning it through a message invites truncation.
It cannot reach `paper.md`: assembly is deterministic, in Python, and stitching
the parts is not the model's to do.

Everything else comes back as schema-checked structured output that Python
writes. The outliner returns an outline and Python writes `outline.json`.
The outline judge returns a verdict and Python writes `outline-verdict.json`.
The diagrammer returns diagram source and Python writes it, renders it, and
runs the fidelity judge.

No role holds `Bash`. The renderer is one subprocess with fixed arguments, and
Python runs it. Handing a model a shell to save that would widen the blast
radius from a wrong paper to anything this machine can run.

The researcher and the verifier both search and neither writes. A role that can
search and write can adjust the evidence to fit the paper.

## The phases

0. **Prior art.** Read the second brain for established terminology and earlier
   conclusions on this topic. Skip when it is not there. Never treat it as
   verified.
1. **Outline.** Turn the topic into a two-level outline: sections with
   objectives, abstracts, key questions, claims to support, required evidence,
   word targets, and planned figures. Python validates the outline, an Opus
   judge scores it, and a stamp writes `outline.approved.json`. Later phases
   read that file and nothing else.
2. **Research.** Answer each approved key question from primary sources, in
   outline order. Return atomic claims, each with a source URL and a verbatim
   quote.
3. **Verify.** Check each claim against a source found independently. The
   verifier never sees the researcher's answer.
4. **Diagram.** The diagrammer returns source for `kind: diagram` figures.
   Python renders it and runs the fidelity judge. `kind: chart` figures are
   logged and skipped in this phase.
5. **Write.** One section at a time, from verified claims only, handed the
   section's objective, abstract, claims to support, and word target. Unpack
   every bound claim: finding, mechanism, alternative and its cost, then the
   limit of the evidence. A section that restates its claims in two sentences
   is a brief.
6. **Assemble.** Stitch the sections and append the reference list.
7. **Check.** Run the deterministic rows: sources, hosts, doctrine, complete,
   outline_coverage, grounded, cited, sourced, images, style, and, on a paper
   run, has_body and length. Length is hard at 1800 words. Doctrine is
   scoped to the E2E lane. `outline_coverage` requires every approved section
   and every key question on the page. No model votes here.
8. **Review.** The judge scores what a script cannot.
9. **Publish.** Push the paper and its figures to a secret gist, on request,
   and only after the paper passes.

## The verdicts

A claim carries one of four states out of phase 3, and the state governs how the
writer may use it.

| State | When | The writer |
| --- | --- | --- |
| `verified` | both searches support it | states it directly |
| `contradicted` | both agree it is false | never sees it |
| `disputed` | the two disagree | names the disagreement |
| `unverified` | the verifier could not run | states it qualitatively or drops it |

There is no arbiter role. A disputed claim in a white paper is a claim you
soften, not one you adjudicate with a third model.

## The exits

The paper's control doctrine is distinct from the run's final outcomes. The
paper checks exits in this order: **done**, then **cost**, then **max turns**.
It does not teach a generic "whichever fires first" rule.

The run itself has three outcomes: pass, retry, escalate.

- **Pass.** The deterministic checks are green and the judge agrees.
- **Escalate on a stall.** This attempt failed in exactly the same way as the
  last one. The loop is not converging, and spending the rest of the budget
  watching it fail identically buys a bill, not a paper.
- **Escalate on budget.** The money or the iteration count is spent.

The check report produces the failure signature. Two equal signatures are a
stall. The signature is what failed, not how it was worded, so a model
rephrasing its own complaint does not read as progress.
