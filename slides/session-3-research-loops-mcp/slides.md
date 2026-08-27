---
marp: true
paginate: true
title: Session 3. Research Loops and MCP
description: Engineering Reliable Agentic AI Systems. Packt. 29 August 2026.
style: |
  /* Marp has no `center` image keyword. Diagrams are block images, so this
     centers every one of them without touching the bg images. */
  img { display: block; margin-left: auto; margin-right: auto; }
---

<!--
id: s3-01
layout: title
minutes: 1
beat: talk
-->

# Research Loops and MCP, the execution model

Session 3. 40 minutes. One research assistant, built end to end.
Not a survey of nine frameworks.

---

<!--
id: s3-02
layout: split-right
minutes: 2
beat: talk
image: images/same-graph-new-object.png
image_prompt: >
  16:9. The Module 2 graph silhouette, unchanged in outline. The object at the
  center swaps from a source file to a short cited report. One plug labeled
  RESEARCH enters the doer box and nothing else. Paper and green ink. No logos.
-->

# Same graph. New object.

- Orchestrator, doer, judge. The exact three parts from Module 1.
- The object is a question. The artifact is a cited brief.
- The judge still holds no write path.
- The only new thing is a tool that reaches outside the machine.

![bg right:42%](images/same-graph-new-object.png)

---

<!--
id: s3-02a
layout: figure-bottom
minutes: 2
beat: talk
-->

# Research is a subagent so the window stays clean

LangChain Deep Agents ships this as the default example.

- Researcher: search tools only. Isolated context.
- Writer: `briefs/` only.
- Judge: `check_brief` in Python. Citations are arithmetic.
- MCP: context7, optional Perplexity, fixture when the room has no wifi.

Raw search never returns to the orchestrator. A summary does.
`langchain-mcp-adapters` loads the servers. The loop still cannot merge.

Saturday lab stays two functions in `loop.py`.
The Deep Agents port is the takehome: `solutions/sol3_research_deep_agents/`. Issue #119.

---

<!--
id: s3-03
layout: split-left
minutes: 2
beat: talk
image: images/mcp-boundary.png
image_prompt: >
  16:9. A wall of sockets. Exactly one socket has a plug in it, labeled
  SEARCH. Every other socket is capped with a fitted red cover and no
  handle: merge, deploy, delete, billing. Workshop poster style. No logos.
-->

# A safe tool boundary is narrow, and it is read-only.

Model Context Protocol (MCP) is how the agent reaches outside itself.

- **Allowed**: search, and write into this loop's own output folder.
- **Denied**: merge, deploy, ticket state, anything in production.

A narrow schema beats a broad one. `add_review_comment(issue_id, body)` is a
tool. An HTTP client holding your credentials is a liability.

![bg left:40%](images/mcp-boundary.png)

---

<!--
id: s3-04
layout: split-right
minutes: 2
beat: talk
image: images/toolprivbench.png
image_prompt: >
  16:9. Two tools on a pegboard: a small precise screwdriver and an enormous
  sledgehammer. A mechanical arm reaches past the screwdriver for the
  sledgehammer. A sign on the sledgehammer reads sufficient was smaller.
  Graphite and green. No logos.
-->

# Agents reach for the bigger tool. This is measured.

ToolPrivBench, 2026:

- Mainstream agents **often chose a higher-privilege tool** when a lower one
  was enough.
- Transient failures made that escalation **more likely**, not less.
- Prompt-based controls gave **only limited** mitigation.

You do not fix this with a stronger sentence. You fix it by not shipping the
sledgehammer.

![bg right:42%](images/toolprivbench.png)

---

<!--
id: s3-05
layout: figure-bottom
minutes: 1
beat: talk
-->

# What comes back from a tool is untrusted input.

AgentDojo showed that content returned by a tool can carry instructions, and
that those instructions can redirect the agent.

Your search results are a **document the internet wrote**, not a system prompt.

> Authorization is a property of the tool boundary, not a sentence in the
> system prompt.

The MCP authorization spec makes the same call: validate the token audience
server side, and never pass a token through.

---

<!--
id: s3-06
layout: split-left
minutes: 2
beat: talk
image: images/three-backends.png
image_prompt: >
  16:9. Three roads merging into one gate. Road one carries a key. Road two
  carries a plain compass. Road three carries a sealed envelope. The gate is
  a single doorway labeled search(question). No brand marks. No logos.
-->

# One boundary. Three backends. You pick.

| Backend | When |
|---|---|
| Perplexity over MCP | You set `PERPLEXITY_API_KEY` |
| Your agent's own WebSearch | No key, but the tool is there |
| A recorded fixture | Offline, or the wifi in this room |

The loop calls one function. It never learns which one answered.

Saturday does not depend on a signup form.

![bg left:40%](images/three-backends.png)

---

<!--
id: s3-07
layout: lab
minutes: 25
beat: lab
-->

# Lab 3. The research assistant. 25 minutes.

```bash
cd labs/lab3_research
claude -p "$(cat prompts/claude-code.md)"     # or codex, grok, opencode

task loop:research -- --question "sqlalchemy nullable datetime column" \
  --backend fixture
```

Fill `loop.py`. Two functions: `plan_questions` and `check_brief`.

The question is boring on purpose. This is not "write my next post."

Falling behind is fine: copy `loop.py` from `solutions/sol3_research/`.

---

<!--
id: s3-08
layout: figure-bottom
minutes: 1
beat: lab
-->

# The judge reads the brief. It does not read it *thoughtfully*.

```
PASS  has_sources    2 sources retrieved
PASS  grounded       every citation resolves
PASS  cited          every paragraph cites a source
PASS  style          0 em dashes

backend: fixture   budget: $0.00 / $0.20 (soft $0.10), 3/8 calls
gate:    pass
```

Grounded and cited are **arithmetic**. No model call.

A confident sentence nobody can trace is the failure that matters.

---

<!--
id: s3-09
layout: split-right
minutes: 2
beat: lab
image: images/unbounded-search.png
image_prompt: >
  16:9. A library corridor that recedes without end, shelves blurring into
  the vanishing point. In the foreground, a small brass counter reading a
  fixed number of steps, and a closed gate. Calm, not ominous. No logos.
-->

# A research loop needs a harder stop than code does.

"Keep searching until confident" is not a stop condition. The search space has
no end, so the loop has to be told where the end is.

- **Call budget.** Eight searches. The ninth raises.
- **Dollar budget.** A soft warning, then a hard cap.
- **Stable failure.** The same gaps twice means stop.
- **No source found** escalates. It never ships an uncited brief.

![bg right:42%](images/unbounded-search.png)

---

<!--
id: s3-10
layout: figure-bottom
minutes: 1
beat: bridge
-->

# Two numbers worth remembering.

| Number | What it says |
|---|---|
| **15.7%** | Share of recorded agent failures that are one step, repeated |
| **12.4%** | Share where the agent did not know it was already done |

And retries are not linear. A retry usually replays the whole context, so a 20%
per-step failure rate can roughly **double** the bill, not add a fifth to it.

Cost is an architecture problem, not a pricing problem.

---

<!--
id: s3-11
layout: title
minutes: 1
beat: bridge
-->

# Break. 15 minutes.

Next: the same stack, with nobody at the keyboard.
