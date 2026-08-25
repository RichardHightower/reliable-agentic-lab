# Session 3 notes. Research Loops and MCP.

40 minutes. Hands-on. Denim kept this a build, not a demo. Do not compress it unless Saturday forces you. If you must cut, cut talk, not the run.

Artifact they keep: one working research assistant.

This is not Ticket Enhancer as the live lab. Ticket Enhancer stays in the architecture story. The sold module is a research assistant that searches, verifies, and synthesizes. We mimic v3. We emit a report.

Images match `slides.md`.

---

## s3-01. Title

Eventbrite name. Research Loops and MCP, the execution model.

One worked example. Not a survey of servers. Say that twice. People will ask for a catalog. The catalog is how you blow the clock.

---

## s3-02. Same graph, new object. Image `same-graph-new-object.png`

They already own orchestrator, Maker, Checker, rubric, gate, budget.

The object in the middle changes. Pull request becomes a short report.

The real v3 pipeline in `SpillwaveSolutions/articles` has SEO, images, voice, Notion, related-article footers, parallel parts. Those stay home. If you run full v3 live, Module 3 eats the day.

---

## s3-03. Safe MCP boundary. Image `mcp-boundary.png`

Model Context Protocol (MCP) is a tool contract, not a personality.

One plug in the wall. Perplexity. Research.

Caps on the other sockets: merge, deploy, seven other servers.

Allowed tools for the researcher: search, write notes to disk. The orchestrator does not get those tools. That is the same wall as Maker and Checker.

---

## s3-04. Research in a sub-agent. Mermaid.

Cost control is structural.

The researcher may pull a long thread. It writes `work/research_notes.json`. The orchestrator receives a summary paragraph.

"Please don't paste the dump" is a prompt. A summary edge is architecture.

---

## s3-05. Fixture fallback. Image `fixture-fallback.png`

Same move as Langfuse versus local traces.

If `PERPLEXITY_API_KEY` is missing, `fixtures/research.json` still drives the fact-check. Saturday does not depend on signup.

If the key is present, you may show a live call, then still ground claims on the fixture so the grader is deterministic.

---

## s3-06. Section. Two domains.

Fact, then style. Sequential. That is v3 editor/checker, two times, not twelve stages.

---

## s3-07. Fact-check loop. Mermaid.

Checker reads. Editor writes.

Must-include: optional, UTC, ISO 8601, overdue. Forbidden: required due date, local time.

Pass is no critical and no major. Minors do not block. That matches the v3 verdict rule.

If the editor cannot fix a contradiction, the loop escalates. It does not invent a pass.

---

## s3-08. Style enforcer. Image `style-enforcer.png`

Deterministic first. Strip em dashes in code. The house rule is not a suggestion.

Then a tiny rubric. One idea per sentence. Expand MCP on first use. Expand CRM on first use.

Not the full article style guide. Not engagement. Not SEO. Those are how v3 grew a factory. We are teaching a loop.

---

## s3-09. Three exits again. Image `budget-calls.png`

They saw pass, retry, escalate on pytest. Now the same exits on a report.

Each call costs 1. Cap is 8. Loops per domain default to 3.

Repeat failure still matters. Two identical issue signatures and you stop.

Unresolved tags on a dirty report beat a green lie. A human can read tags. A human cannot un-see a fake pass.

---

## s3-10. Lab.

Unit tests first. Then a clean run. Then `--dirty`.

The dirty run is the teaching run. First fact check fails. Editor repairs. Style runs. Trace shows the retries.

If someone finishes early, they read `work/last-loop.json` and say which gate fired. They do not start a second MCP server.

---

## s3-11. The pipeline figure. Mermaid on top.

Topic is boring. "Should CRM sales tasks store optional UTC ISO due dates?"

Boring is a feature. A sexy topic turns this into a writing workshop. We are not packing a Substack.

---

## s3-12. Failure modes. Last five minutes.

Four cards. Signup stall. Context dump. Fake pass. Ignored budget.

Each has a green fix that is already in the code. Point at the code, not at a new slide of theory.

---

## s3-13. Break.

Session 4 is this stack with no human at the keyboard.
