# Session 2 notes. Harness Engineering.

55 minutes. Center of gravity. If the day is dying, cut talk in other modules. Do not cut this.

Artifact they keep: a reusable evaluation harness.

They already have a loop from Session 1. This hour wraps it.

Images match `slides.md`.

---

## s2-01. Title

Say the Eventbrite name. Harness Engineering, the validation layer. Say the time. 55 minutes. Say do not cut it, because Denim already asked you to keep this the centerpiece.

---

## s2-02. The loop will lie. Image `loop-without-harness.png`

The five boxes from Session 1 are still right. They are not sufficient.

Without a harness the agent edits forever, declares victory on a red test, or dumps the repo into the next call. A better prompt does not fix that. A gate does.

---

## s2-03. Maker and Checker. Image `maker-checker.png`

This is the Loop Engineering Maker/Checker split, three ways, compressed to one picture.

Maker has a keyboard and five file cards. Checker has a red pen and no keyboard. A wall between them.

If one agent writes the code and scores the code, it will grade its own homework. False completeness. You have seen this in production. Name it. Then show the wall.

---

## s2-04. Graph nodes. Mermaid full width.

Orchestrator. Maker. Grader. Checker. Gate.

Python holds the retry. `for attempt in range`. The model does not interpret "please retry." That is the v3 lesson from the articles pipeline, applied to CRM.

The orchestrator sees summaries and scores. Research and long files stay in sub-agents. That sentence is also the setup for Session 3.

---

## s2-05. Tool scope. Image `tool-scope.png`

Read the badge board out loud.

Maker: read CRM, write five files, run grader.
Checker: read diff, read pytest, read ticket.
Forbidden: edit graders, change ticket state, merge, deploy.

Deep Agents is how you show scoped tools. Claude Agent SDK is the same shape. Pick one binary for the projector. Attendees may keep using Claude Code against the same ticket and the same grader. Do not make a product tour.

---

## s2-06. Section. Spec-driven development.

Intent becomes a contract. Not a paragraph of hope.

---

## s2-07. Ready ticket is the rubric. Image `ready-ticket-rubric.png`

Load `T001-due-dates.ready.md`. The `## Success criteria` bullets are the rubric rows.

If a row cannot fail a test, it is a wish. Wishes do not belong on a grader.

You are not scoring prose quality on this ticket. You are scoring an optional UTC field, an API shape, and two filters.

---

## s2-08. Edges with types. Mermaid on top.

Graph engineering in this workshop is not AGER as a product. It is typed edges.

Ticket to rubric. Rubric to grader. Grader to gate.

If someone asks about the 20 August graph runtime, point back, do not demo it.

---

## s2-09. Grader. Image `hidden-grader.png`

The tests are hidden from the Maker's authoring loop. They live in `solutions/m2-harness/graders`.

Proof: they fail on `starter_crm` and pass on `solutions/crm`. If both pass, the contract is too weak. If both fail, the known-good is not good.

---

## s2-10. Quality gates. Mermaid.

Three exits. Pass. Retry. Escalate.

Escalate on a repeated failure signature. Same `failed_node_ids` twice means the Maker made no progress. Spending another call is a cost incident, not optimism.

Escalate when the budget is spent. Default 3.

There is no fourth exit called "just once more."

---

## s2-11. Stop conditions. Image `stop-conditions.png`

Stop conditions are the invisible failure mode from the Loop Engineering series. Make them visible as three cards.

The model does not get a vote on whether to continue. Python does.

---

## s2-12. Traces. Image `trace-json.png`

Local JSON. `traces/last-loop.json`.

Inputs, tool calls, scores, gate. That is enough to teach.

Langfuse is a pane on the same schema. If cloud signup stalls, you do not skip the lab. You open the file.

Observability is not a fifth module. Do not let it become one.

---

## s2-13. Lab.

Known-good is green. `--maker none` should pass on iteration 1. That proves the harness can score Session 1's artifact.

If you need the drama of fail then pass, run against a broken tree with `--maker reference`. Module 1 already did that on `starter_crm`. Do not burn the 25 minutes re-implementing due dates by hand.

Unit tests on gates and rubric should already be green. Run them once on the projector.

---

## s2-14. Read the trace. Image `read-the-trace.png`

Open `last-loop.json`. Finger on `gate`. Finger on `failed_node_ids`.

Pass: stop. Retry: Maker may write scoped files. Escalate: human. The loop is not ashamed of escalate. That is a designed stop.

---

## s2-15. What you keep. Mermaid.

Session 1 loop into Session 2 harness into a score. That is the center of the paid outline. Say it.

---

## s2-16. Break.

Next hour is one research assistant. Same graph. New tools. Report instead of a PR. Not a survey of MCP servers.
