---
name: research-loop
description: Produce an evidence-backed technical white paper from one topic. Plans the paper, researches each question from primary sources, verifies every claim against a second independent source, renders the figures, writes the sections, and checks the result before it ships.
---

# The research loop

This skill is the readable specification of what `paper.py` implements in
Python. Read it to understand the loop. Do not run it from the Agent SDK port,
because in that port Python owns the phases and running this skill would give
you two orchestrators disagreeing about whose turn it is.

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
| planner | read tools, `Write` | `plan.json` |
| researcher | read tools, `WebSearch`, Perplexity, Context7 | nothing |
| verifier | `Read`, Perplexity, Context7 | nothing |
| diagrammer | read tools, `Write`, `Bash` | `diagrams/**` |
| writer | read tools, `Write` | `sections/**`, `paper.md` |
| judge | read tools | nothing |

The researcher and the verifier both search and neither writes. A role that can
search and write can adjust the evidence to fit the paper. The diagrammer is the
only role with a shell, because it is the only role that runs the renderer.

## The phases

0. **Prior art.** Read the second brain for established terminology and earlier
   conclusions on this topic. Skip when it is not there. Never treat it as
   verified.
1. **Plan.** Turn the topic into sections, questions, and figures.
2. **Research.** Answer each question from primary sources. Return atomic
   claims, each with a source URL and a verbatim quote.
3. **Verify.** Check each claim against a source found independently. The
   verifier never sees the researcher's answer.
4. **Diagram.** Draw each figure, render it, judge the render, simplify and
   re-render on a miss.
5. **Write.** One section at a time, from verified claims only.
6. **Assemble.** Stitch the sections and append the reference list.
7. **Check.** Run the deterministic checks. No model votes here.
8. **Review.** The judge scores what a script cannot.
9. **Publish.** Push the paper and its figures to a private gist, on request.

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

Three, and no fourth: pass, retry, escalate.

- **Pass.** The deterministic checks are green and the judge agrees.
- **Escalate on a stall.** This attempt failed in exactly the same way as the
  last one. The loop is not converging, and spending the rest of the budget
  watching it fail identically buys a bill, not a paper.
- **Escalate on budget.** The money or the iteration count is spent.

The check report produces the failure signature. Two equal signatures are a
stall. The signature is what failed, not how it was worded, so a model
rephrasing its own complaint does not read as progress.
