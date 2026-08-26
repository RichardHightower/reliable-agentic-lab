# Session 3 notes. Research Loops and MCP.

40 minutes. One research assistant, built end to end.
Artifact they keep: a working research assistant that cites what it retrieved.

This is a build, not a survey. Do not tour MCP servers. One tool, one boundary.

**Clock checkpoints.** Slide s3-07 at 10 minutes. Slide s3-08 at 35 minutes.

---

## s3-01. Title

Say what this hour is not: a tour of nine frameworks.

---

## s3-02. Same graph, new object

Point back at Module 1's three boxes. Nothing about them changes.

The only new thing is a tool that reaches outside the machine. That is the whole
delta, and it is why this module is only 40 minutes.

---

## s3-03. A safe tool boundary

Two lists: allowed and denied. Read both.

Then the schema point. `add_review_comment(issue_id, body)` is a tool. An HTTP
client holding your credentials is a liability. Narrow beats general.

---

## s3-04. ToolPrivBench

Three findings, and the third is the one that stings: prompt-based controls gave
only limited mitigation.

Say the practical version. You do not fix this with a stronger sentence. You fix
it by not shipping the sledgehammer.

Note if asked: transient failures made escalation more likely, not less. Retries
push agents toward bigger tools.

---

## s3-05. Tool output is untrusted input

AgentDojo. Content that comes back from a tool can carry instructions.

The sentence to land: your search results are a document the internet wrote, not
a system prompt.

If someone asks about MCP authorization specifically: validate the token audience
server side, never pass a token through. That is the confused-deputy fix.

---

## s3-06. Three backends

Read the table. Then say the point: the loop calls one function and never learns
which backend answered.

Say the practical promise out loud. Saturday does not depend on a signup form.
Anyone without a key uses `--backend fixture` and gets the same lesson.

**You should be at 10 minutes here.**

---

## s3-07. Lab 3

Read the command. Say that the question is boring on purpose.

`loop.py`. Two functions. The common stall is `check_brief`, because people reach
for a model. Remind the room that both checks are arithmetic.

25 minutes. Call time at 15 and at 5 remaining.

---

## s3-08. The judge output

Put the four rows on the screen and read them.

Grounded and cited are arithmetic. No model call. Then the line that matters: a
confident sentence nobody can trace is the failure that matters.

**You should be at 35 minutes here.**

---

## s3-09. Stopping an unbounded search

The setup: a code loop stops when the tests go green. A research loop has no
equivalent, because the search space has no end.

Four stops. The last one is the honest one: no source found escalates, and it
never ships an uncited brief.

---

## s3-10. Two numbers

15.7% one step repeated. 12.4% not knowing it was already done.

Then the cost point. A retry replays the whole context, so a 20% per-step failure
rate can roughly double the bill, not add a fifth to it.

Closing line: cost is an architecture problem, not a pricing problem.

---

## s3-11. Break

15 minutes. Next: the same stack with nobody at the keyboard.
