# Session 4 notes. Production Architecture.

35 minutes for the module, then 10 minutes to close.
Artifact they keep: a production architecture they can hand to their team.

Energy is lowest here. Keep it moving. The lab is 18 minutes, not 25.

Expanded from the original 16-slide outline to 48 slides. Same narrative.
Same lab. More architecture, more evidence, more failure modes.

Diagram coverage, Session 4: 24 Imagine diagrams on 40 substantive slides (60%).
Mermaid source lives in `slides/diagrams/mermaid/` as `s4-*.mmd`.
The audience sees the Imagine JPEG, never the diagram syntax.

**Clock checkpoints.** Slide s4-18 at 12 minutes. Slide s4-27 at 16 minutes.
Slide s4-32 at 30 minutes. Slide s4-39 at 35 minutes.

Do not survey seven production loops as labs. Name them. Build one graph.

---

## s4-01. Title

Say the shape of the hour: build for 12 minutes, type for 18, land for 5, then
close for 10.

13:15 Central. 14:15 Eastern.

---

## s4-02. The clock

Read the four rows. Artifact they keep is a production architecture they can
hand to their team.

If a lab runs long, cut patterns talk. Do not cut the close.

---

## s4-03. What changes when you walk away

Four items. The graph is not one of them.

The last line is the hook for the whole hour: if you cannot read the last score,
you cannot debug at 2 a.m.

---

## s4-04. Graph does not change. Trigger does.

Point at Keep. That is Modules 1 to 3.

Point at Swap. File, webhook, cron. A timer that fires on no change burns
budget for no work. They saw this anti-pattern in Module 1.

---

## s4-05. Four things around the loop

This is `solutions/sol4_fixer_agent_sdk/loop.py` in one picture. Durable state, a hard budget, a
written trace, an exit code.

The loop itself is `solutions/sol4_fixer_agent_sdk/fixer.py`. The SDK port wraps it.

---

## s4-06. Python holds the loop

Three exits, no fourth. The forgotten exit is still stable failure.

New in this hour: a suite that never ran is not a suite that failed. Name the
real problem and stop on the first round.

---

## s4-07. Unattended means query()

`query()`, not `ClaudeSDKClient`. Nobody is chatting.

Saturday lab stays two functions in `loop.py`.
The Agent SDK port is the takehome: `solutions/sol4_fixer_agent_sdk/`. Issue #120.

---

## s4-08. The Agent SDK contract

Read the five lines.

`permission_mode: dontAsk` because nobody is there to click Allow, and `dontAsk` fails closed.
`acceptEdits` auto-accepts every file edit before the allow list is read, which was the bug.
PreToolUse deny `tests/**` because the fixer cannot weaken a test to reach green.
`max_turns` is the SDK iteration budget. Python still owns the outer budget.
Tests after every turn are pytest, not a claim.
Merge is never a tool.

---

## s4-09. Merge stays human

Callback to Module 1. Merge, money, and production deploy stay human.

The fixer never receives a merge tool. That is a missing tool, not a polite
request.

---

## s4-10. Trust boundaries

Untrusted is model output, including invented evidence.
Trusted is Python: `gates.decide`, `WriteScope`, pytest, the receipt.
Human owns merge.

Same split as Module 1, now with nobody in the chair.

---

## s4-11. MAST

The headline is the takeaway: most agent failures are not model failures.

1,642 traces. 7 frameworks. 14 modes clustered into 3 categories.

41.8% system design issues. 36.9% inter-agent misalignment. 21.3% task
verification. Cemri et al., arXiv:2503.13657, NeurIPS 2025.

Say the closing line: every one of those three is something you build, not
something you buy. That justifies the whole day retroactively.

Do not invent other percentages. The paper uses these three category names:
system design issues, inter-agent misalignment, task verification.

---

## s4-12. Three categories, this hour

Map MAST onto the day.

FC1 system design: the graph, the scope, the budget, the trigger, the state.
FC2 inter-agent misalignment: the handoff. Orchestrator sees summaries, not dumps.
FC3 task verification: the judge, pytest, the receipt.

This hour is all three, with nobody watching.

---

## s4-13. Durable state

Five fields. Read them.

`.harness/state.json` in the target repo, next to the receipt.

The point is small and concrete: it survives the process. A chat transcript does
not.

A corrupt file is not a fresh start. `unattended.py` says so, then starts fresh.

---

## s4-14. State lifecycle

Walk load, run, save.

`runs` increments. `last_gate` and `last_reason` come off the trace.
`last_run_at` is UTC. `loop` is fixer, implementer, or enhancer.

The next cron job reads this before it starts.

---

## s4-15. Observability

A trace is not a log file. Name what a span carries: tool name, arguments,
output, duration, retries, error.

Then three numbers per run: steps, loop count, cost per task. Those three catch
runaway loops before the invoice does.

Local JSON counts as production if it is the record you actually open.

---

## s4-16. Always write the file

`solutions/observability.py`. Always writes the local file, even on an exception.

A trace that only appears when the run succeeds is the trace you cannot use,
because the run you need to read is the one that failed.

Langfuse is optional. A missing key must never change what the loop does.

---

## s4-17. Local and remote gates

Callback to the push gate they hit in Module 2.

Same receipt rule in the hook and in the workflow. Same rule in both places, or
the remote one is theater.

---

## s4-18. Exit codes and the workflow

Read the exit codes. 0 pass, 2 escalate, 1 crash.

Escalate is not a crash, it is a decision, so it gets its own code.
CI needs a number, not a paragraph.

Then flash the workflow. `workflow_dispatch`, `pull_request`, cron `0 15 * * 1-5`.

There is no `unattended.py`. The live fixer is `solutions/sol4_fixer_agent_sdk/loop.py`.
The CI contract this hour is teaching:

    return {gates.PASS: 0, gates.ESCALATE: 2}.get(state["last_gate"], 1)

**You should be at 12 minutes here.** Then the lab.

---

## s4-19. Section. Lab

A breath. Zero minutes. 18 minutes of typing after the next few cards.

---

## s4-20. Lab 4 shape

Same three parts. Only the object changes.

There is no plan to write, because the work is already defined by what is red.

It runs unattended, so its exits matter more than its successes.

---

## s4-21. Stash Module 2 first

Say the stash line out loud before anyone types.

The target repo still holds Module 2's work, and `git checkout broken-pr` refuses
rather than deleting it. That refusal is on brand, but it costs 30 seconds if you
let them find it.

`solutions/sol4_fixer_agent_sdk/fixer.py` `checkout()` raises `SystemExit` naming both ways out: stash, or
discard. The work is still there. The loop did not decide for the human.

---

## s4-22. Two functions

Fill `loop.py`. Nothing else.

Two functions: `summarize_failure` and `repair_until_green`.

The line to repeat while you walk the room: giving up is allowed, giving up
silently is the bug.

---

## s4-23. summarize_failure

Name the failing tests and the first real error line.

Sending the log would put the failure in the middle of a long context, which is
where accuracy is worst. Callback to Lost in the Middle from Module 1.

The engine answer is `solutions/sol4_fixer_agent_sdk/fixer.py` `failure_summary`.

---

## s4-24. repair_until_green

Stopping is designed. Stopping without an explanation is a bug.

The next person to look at this pull request has to know why the agent walked
away. The returned trace carries the gate and the reason.

Four stop paths: suite green, suite never ran, same ids twice, budget spent.

---

## s4-25. Refuses to clean the tree

After Module 2 the target repo holds work somebody did.

A loop that quietly deletes it to make its own job easier is the behaviour this
workshop exists to prevent.

Test: `test_checkout_refuses_to_delete_an_earlier_lab_s_work`.

---

## s4-26. Research once

When the failure names an error it cannot place, it asks the research boundary
once, inside the budget, and carries the answer into the next attempt.

Budget is 2 calls, 0.05 dollars. Fixture in the room. Same boundary as Module 3.

---

## s4-27. Lab commands

`--branch broken-pr` is what makes this real: the fixer starts from a branch with
one genuinely failing test. Point it at a green branch and it reports a pass and
proves nothing, which is the same shape as the red gate in Module 2.

Walk the room. Do not reteach the architecture. Point at the trace.

18 minutes. Call time at 10 and at 5 remaining.

Falling behind is fine: watch Rick finish `loop.py` and keep going.

---

## s4-28. Three exits, the comment

The comment is for the next human. "A human should take this one."

The test `test_the_fixer_gives_up_with_an_explanation_when_it_cannot_fix`
asserts that sentence is present when the doer is `none`.

---

## s4-29. Fall behind

There is no drop-in `loop.py`. Watch Rick finish. They continue with a working artifact.

Read `labs/lab4_fixer/FALL-BEHIND.md`.

---

## s4-30. Why the receipt exists

This is the payoff for the receipt work in Module 2. Do not rush it.

A model that may both act and verify can produce plausible false evidence.
Invented test passes. File edits that never happened. Fabricated API responses.

Then the sharp version: that is a wrong judgment about the state of its own
output, and a self-check cannot catch it by construction.

**You should be at 29 minutes here.**

---

## s4-31. The receipt proves three things

Green. This tree. Newer than the last edit. All three, or it proves nothing.

Python writes it. The model does not. `scripts/receipt.py`.

---

## s4-32. One return per failure

Walk the table. Missing, unreadable, no report, not green, stale tree, source
newer.

One return per way a receipt can fail to prove its case. Collapsing them would
save a branch and cost the reader the reason.

**You should be at 30 minutes here.**

---

## s4-33. Section. Patterns

A breath. Zero minutes. Five minutes of naming, not building.

---

## s4-34. Swap the object

Point at the two subgraphs. Keep the left one, replace the right one.

Say it plainly: four modules, one graph, four objects, on purpose.

---

## s4-35. Four objects

They already ran all four. Module 4 is the same graph with nobody at the
keyboard. The object today is a failing pull request.

---

## s4-36. Seven loops named

One minute. Name them, do not build them.

Daily triage. Pull request babysitter. Continuous Integration sweeper. Ticket
groomer. Ready-ticket implementer. Research brief. Nightly eval.

If someone asks for the list in writing, point at the repo. Do not read seven
items off a slide twice.

That list is a map home. It is not a second product to start on Monday.

---

## s4-37. Map home

The trigger moves out of the loop. The exits stay in it.

A workflow file starts the run. It never decides when to stop.

Extra credit is `labs/extra-credit/`. Not on the Saturday clock. Do not skip
Module 2 to work on it.

---

## s4-38. The slow failure

The one nobody plans for. Passes every demo, earns trust, degrades over months
with nothing visibly breaking.

The causes are state, context, retrieval, latency, and observability. Not model
capability.

The fix is a cadence, not a tool. Weekly evaluation, not quarterly. A 2% weekly
drop is invisible in a week and catastrophic over a quarter.

**You should be at 35 minutes here.**

---

## s4-39. Section. Close

A breath. Zero minutes. Ten minutes.

---

## s4-40. What you take home

Four artifacts, one per module. Check them off out loud.

Then the claim they will test on Monday: all four run from a clean clone with one
`task setup`.

---

## s4-41. Where everything lives

Point at the tree. Say that each `solutions/` folder is standalone, so they
already take this home. There is no shared engine to learn.
at their repo.

Name the done branches once more for anyone who fell behind.

Every `solutions/sol<n>_*` folder is green. Copy from one any time.

Takehome lives in `labs/takehome/` and `solutions/sol4_fixer_agent_sdk/`.

---

## s4-42. Monday

Five steps, in order. The order is the advice.

1. One backlog object. Not five.
2. One ticket whose criteria a test can fail.
3. `Taskfile.yml` that emits `junit.xml`.
4. Split the doer before you add a single tool.
5. Arm the push gate on day one, while the loop is still small.

Step 5 is the one people skip: arm the push gate on day one, while the loop is
still small enough that the refusals are cheap.

---

## s4-43. The order is the advice

Same five steps as a flow so it sticks.

Do not add a tool until the doer is split.
Do not skip the gate because the loop is still a prototype.

---

## s4-44. Takehome Issue #120

`query()`, not `ClaudeSDKClient`. Nobody is chatting.
PreToolUse is write scope. Merge is never a tool.
Issue #120 is the takehome port.

Nobody is expected to finish this inside the five hours. The five-hour labs
need no model key. This one does.

---

## s4-45. Bibliography

Skip in the room unless asked.

MAST numbers are from the paper's analysis of 1,642 traces. Category names
are the paper's: system design issues, inter-agent misalignment, task
verification.

---

## s4-46. Questions

Three to four minutes. Hold the last line for the end.

If the room is quiet, ask them which object they will point this at on Monday.
Do not start building a seventh loop.

The loop is the product. The prompt is not.

---

## s4-47. Six lines plus one

The six lines from Module 1, plus the line from this hour.

If you cannot read the last score, you cannot debug at 2 a.m.

---

## s4-48. Closing line

Hold this for the end. Say it once. Stop. Do not undercut it with a joke.

The loop is the product. The prompt is not.

---

## Agent SDK unattended

`query()`, not `ClaudeSDKClient`. Nobody is chatting.
`permission_mode` is `dontAsk`.
PreToolUse is write scope. `tests/**` is denied.
`max_turns` is the iteration budget.
Tests after every turn are pytest.
Merge is never a tool.
Issue #120 is the takehome port.
