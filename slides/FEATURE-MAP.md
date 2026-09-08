# Feature map

One role graph, four objects. Same orchestrator, doer, and judge every hour. Only the
object changes, and each hour adds one piece of machinery.

Loop Engineering is the outer control around ReAct. Harness Engineering is the
grader, scope, receipt, and stop. Graph Engineering is intent as `steps.jsonl`.
"The graph" in Sessions 1, 3, and 4 means the role graph, not Graph Engineering,
and not LangGraph.

Do not survey seven production loops as labs. Name them in Module 4. Build one graph.

| Feature | Module that proves it | What the room actually sees |
|---|---|---|
| Trigger | 1 | A draft ticket on disk, in a repo the engine does not import |
| Action inside a scope | 1 | A doer edits the ticket body and nothing else |
| Verify | 1 | A judge classifies the ticket and names what is missing |
| Memory outside the chat | 1 | The ticket file and the trace. Point back to 20 August. |
| Skills and memory as mounts | 4 | A role loads its instructions on demand, not always resident |
| Human oversight | 1 | The loop proposes a contract. A human accepts it. |
| Three exits, no fourth | 1 | `pass`, `retry`, `escalate`, printed on the trace |
| Stable failure | 1 | The same gaps twice, and the loop stops rather than spend the budget |
| The repo contract | 1 | `Taskfile.yml` plus `junit.xml`. The only interface the loops need. |
| Five roles | 2 | Orchestrator, planner, test implementer, code implementer, judge |
| Write scope as a type | 2 | `Judge` has no `write` method. Not a rule. A missing method. |
| Two doers, disjoint scope | 2 | The code implementer is denied `tests/**` |
| Spec as a testable contract | 2 | Seven acceptance criteria, each one a test can be red about |
| Graph Engineering (`steps.jsonl`) | 2 | Each criterion becomes a test step and a code step. Derived, not generated. |
| The red gate | 2 | New tests must fail before the code implementer starts |
| The ten-row rubric | 2 | "The tests passed" is one row of ten |
| Deterministic judge | 2 | Arithmetic over `junit.xml`, `coverage.xml`, and the diff |
| Model final judge | 2 | After a green rubric the judge subagent answers `done`. Green plus `judge_done=False` is escalate |
| Unparseable verdict is a fail | 2 | A synthetic failing verdict, never a pass. Both sol2 ports parse JSON and treat garbage as `done=False` |
| The push gate | 2 | A `PreToolUse` hook in the CRM clone refuses `git push` without a green receipt. It lives at `.claude/hooks/gate.py` and shells `scripts/receipt.py check` |
| The receipt | 2 | Green, this tree, and newer than the last edit. All three. Both sol2 ports write `.harness/receipt.json` |
| Defense at two layers | 2 | In-process scope catches the loop. `write_scope` catches the subprocess. |
| Reading harness output | 2 | Walk one trace. Name the row that blocked. |
| MCP tool contract | 3 | One narrow tool. Search. No merge, no deploy. |
| Tool output is untrusted input | 3 | AgentDojo. Authorization lives at the boundary, not in the prompt. |
| Least privilege, measured | 3 | ToolPrivBench. Agents reach for the bigger tool. |
| One boundary, three backends | 3 | Perplexity, WebSearch, or a fixture. The loop cannot tell. |
| Research in a sub-agent | 3 | The orchestrator gets a summary, never the dump |
| Cost accounting | 3 | Every call adds to the budget. A hard cap raises. |
| Grounding as arithmetic | 3 | Every citation resolves. Every claim paragraph cites. No model call. |
| House style and glossary | 3 | STE prose, no marketing verb, a first-use term in a Glossary, and a non-marketing CTA closing section, not just the citation belt |
| Stopping an unbounded search | 3 | Call budget, dollar budget, stable failure, and no-source escalation |
| Unattended trigger | 4 | `workflow_dispatch`, `pull_request`, or cron. Not a keystroke. |
| Durable state | 2 | `.harness/state.json`. Runs, gate, reason, timestamp, loop, phase, and the resume fields. Both sol2 ports write it. Neither sol4 port does. |
| Exit codes CI can read | 2 | 0 pass, 2 escalate, 1 crash. Both sol2 ports return these from `main`. Neither sol4 port defines them. |
| Observability | 4 | If you cannot read the last score, you cannot debug at 2 a.m. |
| Local and remote gates agree | 4 | The same receipt rule in the hook and in the workflow |
| Why the receipt exists | 4 | A model that acts and verifies can invent its own evidence |
| PR Fixer pattern | 4 | A failing branch to a mergeable one, or an honest explanation |
| Swap the object | 4 | Keep the graph. Replace the CRM ticket with their backlog. |
| Deep Agents tool lists | 2 | Judge subagent has no write tool. List replaces parent |
| Python owns the gate | 2 | `create_deep_agent` does not count retries |
| Isolated research context | 3 | Researcher subagent. Orchestrator gets a summary |
| MCP adapters plus fixture | 3 | context7, optional Perplexity, fixture offline |
| Agent SDK `query()` | 4 | Unattended fixer. PreToolUse is write scope |
| Merge stays human | 4 | Fixer never receives a merge tool |


Module 1 is a loop that can run once.
Module 2 is that loop made repeatable, and made honest.
Module 3 is the same graph pointed at a question, with one tool boundary.
Module 4 is the same graph with nobody at the keyboard.

The paper follows one house style, published once on the wiki as [Sol-3-White-Paper-Style](https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style). The check module grades third person and no marketing verb (`person`, `marketing`), no contraction and no Latin abbreviation (`ste_language`), and a heading that answers its own question (`question_heading`). The body names no search host (`policy_leak`) and states a caveat once (`caveat_once`). A first-use term earns a `TERM:` marker and a Glossary entry (`glossary_complete`, `glossary_exact`). A figure earns a caption and a mention in its own section (`captioned`, `figure_referenced`). The body carries Methods and, for a human study, a study table (`methods_present`, `study_table`), with front matter above the Abstract (`front_matter`). The last body section is a next step, never a sale (`next_step`, `cta_language`), and the abstract is written last, graded against the body (`abstract_matches_body`).

The evidence contract is arithmetic, not a promise from the model. `source_policy.py` seeds the allowlist by field (`seed_for_field`), bans a host outright (`DENYLIST`), and grades a source's tier (`tier_for`). A shaky numeric claim spends one follow turn, and a generalizing claim spends one counter turn before a lever is ruled out; the `counterweighed` row names a claim nobody checked. A safety claim needs a cited guideline (`guideline_cited`), and a question with stated evidence requirements needs `evidence_requirements_met`. A citation's title, authors, and year come from the fetched record, never the model's guess, and a claim earns attribution only when the fetched text supports it. A diagram is graded against the section's own claims before it is embedded.
