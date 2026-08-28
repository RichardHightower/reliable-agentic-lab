# Session 3 notes. Research Loops and MCP.

40 minutes. One research assistant, built end to end.
Artifact they keep: a working research assistant that cites what it retrieved.

This is a build, not a survey. Do not tour MCP servers. One tool, one boundary.

Talk is 10 minutes. Lab is 25. Retries and budgets are 5. Then the break.

**Clock checkpoints.** Slide s3-18 at 10 minutes. Slide s3-32 at 35 minutes.
Slide s3-43 at 40 minutes.

Expanded from the original 11-slide outline to 43 slides. Same narrative.
Same lab. More architecture, more evidence, more failure modes.

Diagram coverage, Session 3: 20 Imagine diagrams on 38 substantive slides (53%).
Mermaid source lives in `slides/diagrams/mermaid/` as `s3-*.mmd`.
The audience sees the Imagine JPEG, never the diagram syntax.

- `s3-mcp-trust-boundary.puml`
- `s3-three-backend-adapter.puml`
- `s3-research-subagent-sequence.puml`
- `s3-budget-state-machine.puml`
- `s3-prompt-injection-tool-output.puml`
- `s3-least-privilege-tool-wall.puml`

Images match `slides.md`. If a PNG or JPG is missing, the mermaid block is the figure.
Run `python scripts/build_slides.py` before Marp so mermaid becomes SVG.

Locked beats:

- 0 to 10: MCP tool contracts. What a safe tool boundary looks like.
- 10 to 35: Hands-on. One live research assistant. Fill `loop.py` two functions.
- 35 to 40: Retries, budgets, failure modes.

---

## s3-01. Title

Say what this hour is not: a tour of nine frameworks.

Say the time out loud. 12:35 Central. Forty minutes.

Artifact: one working research assistant. Not a survey.

---

## s3-02. The clock

Read the table. Promise only this hour's artifact.

If a lab runs long, cut talk at the end, not the lab. Do not reteach Module 2.

---

## s3-03. Four objects

This is the map for the day. Point at M3. Question in, cited brief out.

Spend less than a minute. They have seen this graph twice already.

---

## s3-04. Same graph, new object

Point back at Module 1's three boxes. Nothing about them changes.

The only new thing is a tool that reaches outside the machine. That is the whole
delta, and it is why this module is only 40 minutes.

Saturday object is a cited brief. Paper pipelines are take-home. Do not import
those exits this hour. Pass, retry, escalate.

---

## s3-05. Section. Research is a subagent

A breath. Zero minutes.

The sentence on the card is the architecture: so the orchestrator window stays clean.

---

## s3-06. Four roles

Read the four boxes.

Researcher: search tools only. Isolated context.
Writer: `briefs/` only.
Judge: `check_brief` in Python. Citations are arithmetic.

LangChain Deep Agents ships this as the default example. Use that sentence.
Saturday lab stays two functions in `loop.py`.

---

## s3-07. Isolated context

Point back at Lost in the Middle from Session 1 if anyone looks blank.

Raw search never returns to the orchestrator. A summary does.
That is why researcher is a subagent, not a tool on the parent.

---

## s3-08. Writer and judge scope

Writer writes `brief.md`. Researcher has no write method. Judge has no write method.

Citations are arithmetic. The judge does not get a vote.
Same lesson as Module 2, pointed at a brief.

---

## s3-09. Section. A safe tool boundary

A breath. The next block is the 0 to 10 contract.

---

## s3-10. What MCP is

Expand Model Context Protocol on this slide, then use MCP.

`context7` needs no key. Perplexity is optional. Fixture when the room has no wifi.

`.mcp.json` ships with the repo. Approve `context7` at minimum.
Nothing in the labs requires `perplexity-ask`.

Do not tour servers.

---

## s3-11. Allowed and denied

Two lists. Read both.

Allowed: search, and write into this loop's own output folder.
Denied: merge, deploy, ticket state, anything in production.

A tool contract is a short list of what an agent may do and a much more
interesting list of what it may not.

---

## s3-12. Narrow schema

Land the schema point.

`add_review_comment(issue_id, body)` is a tool.
An HTTP client holding your credentials is a liability.

Narrow beats general. Expand HTTP on this slide if you have not yet.

---

## s3-13. ToolPrivBench

Three findings, and the third is the one that stings: prompt-based controls gave
only limited mitigation.

Say the practical version. You do not fix this with a stronger sentence. You fix
it by not shipping the sledgehammer.

If asked: transient failures made escalation more likely, not less. Retries
push agents toward bigger tools.

Cite Yang et al., ToolPrivBench 2026, arXiv:2606.20023, OpenReview AXH6buTOVx.

---

## s3-14. Tool output is untrusted input

AgentDojo. Content that comes back from a tool can carry instructions.

The sentence to land: your search results are a document the internet wrote, not
a system prompt.

---

## s3-15. MCP authorization

Authorization lives at the tool boundary, not in a sentence in the system prompt.

Validate the token audience server side, never pass a token through.
That is the confused-deputy fix.

---

## s3-16. MCP threat surface

Four threats: tool poisoning, rug pulls, prompt injection via tool output,
capability escalation through composition.

Four controls: pinned manifests, output sanitization, scoped credentials,
transport-level policy.

A prompt is not a control. A pinned manifest is.
Do not turn this into a survey. Name them, then move.

---

## s3-17. Three backends

Read the table. Then say the point: the loop calls one function and never learns
which backend answered.

Say the practical promise out loud. Saturday does not depend on a signup form.
Anyone without a key uses `--backend fixture` and gets the same lesson.

---

## s3-18. The clock, ten minutes

Fall-behind rule. There is no drop-in loop.py. Watch Rick finish.

**You should be at 10 minutes here.**

---

## s3-19. Section. Lab 3

Lab card. 25 minutes. Do not linger.

---

## s3-20. Lab command

Read the command. Say that the question is boring on purpose.

This is not "write my next post." SQLAlchemy nullable datetime column is the
fixture's recorded question, close enough to match.

`loop.py`. Two functions. Codex, Grok, and OpenCode have the same prompt shape.

Call time at 15 and at 5 remaining.

---

## s3-21. Fill one file

The stub raises. They fill two functions.

The backend does not appear in `loop.py`. That is the point of a tool boundary.

---

## s3-22. plan_questions

A template, not a planner. Three sub-questions you can tell were answered or not.

A plan step you cannot check is a wish.

Swapping in a model is the stretch goal. Downstream checks do not change.

The common stall is over-designing this function. Three strings is enough.

---

## s3-23. check_brief

The common stall is `check_brief`, because people reach for a model.

Remind the room that both checks are arithmetic.

A confident sentence nobody can trace is the failure that matters, and a model
judge is the wrong tool for catching it.

The filled answer is `return brief.check(body, sources)`.

---

## s3-24. Judge arithmetic

Four rows. `has_sources`, `grounded`, `cited`, `style`.

No model call. Point at `BriefScore.passed`.

---

## s3-25. loops/brief.py

`ungrounded_citations` and `strip_em_dashes`.

Style is a rule, not a negotiation. Code spans are left alone.

If someone asks why em dashes: the house style forbids them, and a model will
argue. Python will not.

---

## s3-26. Research sequence

Walk the diagram once, top to bottom.

Orchestrator owns the budget. Researcher asks the boundary. Writer writes the
brief. Judge is arithmetic. Python holds the loop.

Stop on the alt. Same gaps twice is escalate. Budget left is retry.

---

## s3-27. Three backends in code

`choose()` order: Perplexity, then websearch inbox, then fixture.

Nothing is never an option. A research loop that silently returns no evidence
is worse than one that refuses.

Saturday path is `--backend fixture`. File is `loops/fixtures/research.json`.

---

## s3-28. langchain-mcp-adapters

`langchain-mcp-adapters` loads the servers. The loop still cannot merge.

Loading a server is not granting production. The wall is the tool list.

---

## s3-29. Deep Agents takehome

Saturday lab stays Claude Code, or Codex, Grok, OpenCode. Fill `loop.py`.

The Deep Agents port is the takehome: `solutions/sol3_research_deep_agents/`.
Issue #119.

LangChain's own quickstart is a research agent. Use that sentence.

Python still owns `Budget` and `gates.decide`.

---

## s3-30. Fall behind

Copy the answer. They continue Module 4 with a working artifact.

See `labs/lab3_research/FALL-BEHIND.md`.

Nobody is graded here.

---

## s3-31. The judge output

Put the four rows on the screen and read them.

Grounded and cited are arithmetic. No model call. Then the line that matters: a
confident sentence nobody can trace is the failure that matters.

Budget line: `$0.00 / $0.20 (soft $0.10), 3/8 calls`. That is the live default.

---

## s3-32. Walk the room

Do not reteach the architecture. Point at the brief and the trace.

Three exits. No fourth. The last one is the honest one: no source found
escalates, and it never ships an uncited brief.

Call time at 15 and at 5 remaining.

**You should be at 35 minutes here.**

---

## s3-33. Section. Retries, budgets, failure modes

Last five minutes. A research loop needs a harder stop than code does.

---

## s3-34. Unbounded search

The setup: a code loop stops when the tests go green. A research loop has no
equivalent, because the search space has no end.

"Keep searching until confident" is not a stop condition.

---

## s3-35. Budget is a type

Show the dataclass. Soft target warns. Hard cap raises.

A budget that only warns is a budget that gets ignored at three in the morning.

`BudgetExceeded` is a `RuntimeError`. Not a warning, not a nudge.

Live loop in `loops/researcher.py`: `max_usd=0.20`, `max_calls=8`, `soft_usd=0.10`.

Perplexity costs `0.006` per call. Fixture costs nothing, which is why Saturday
still teaches the cap.

---

## s3-36. Charge path

Walk the diamond. Ninth search raises. Dollar cap raises. Soft target warns
without stopping.

The ninth search does not run. That is the point.

---

## s3-37. Four stops

Call budget 8. Dollar budget. Stable failure. No-source escalates.

The last one is the honest one: no source found escalates, and it never ships
an uncited brief.

Python holds the loop, so the model never counts its own retries.

---

## s3-38. Two numbers

15.7% one step repeated. 12.4% not knowing it was already done.

`signature` is what failed, not how it was worded. Two equal signatures mean
the last attempt changed nothing.

---

## s3-39. Retry cost

A retry usually replays the whole context, so a 20% per-step failure rate can
roughly double the bill, not add a fifth to it.

That is why the researcher is a subagent. The orchestrator window stays small.

---

## s3-40. Cost is architecture

Closing line: cost is an architecture problem, not a pricing problem.

Budget, isolated context, `gates.decide`, stable failure.
Do not shop for a cheaper model first.

---

## s3-41. Six lines

Read them. Do not add a seventh.

---

## s3-42. Bibliography

Skip in the room unless asked.

---

## s3-43. Break

15 minutes. Next: the same stack with nobody at the keyboard.

Module 4 is the unattended fixer.

---

## Deep Agents research

LangChain's own quickstart is a research agent. Use that sentence.
Researcher is a subagent so raw search stays out of the orchestrator.
Fixture backend is the Saturday path. Issue #119 is the takehome port.

Saturday still fills `plan_questions` and `check_brief` in `labs/lab3_research/loop.py`.
