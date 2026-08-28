# Session 2 notes. Harness Engineering.

55 minutes. The center of gravity. This module never gets cut.
Artifact they keep: a reusable evaluation harness.

Vocabulary is fixed here. Unit test, end-to-end test, rubric, rubric judge, final
judge, planner, doer, orchestrator, target repo. The outline says "Maker and
Checker". Say once, on s2-08 and s2-09, that maker means doer and checker means
judge, then never use the old words again.

**Clock checkpoints.** Slide s2-18 at 15 minutes. Slide s2-32 at 25 minutes.
Slide s2-43 at 50 minutes.

Expanded from the original 22-slide outline to 52 slides. Same narrative.
Same lab. More architecture, more evidence, more failure modes.

Diagram coverage, Session 2: 31 mermaid figures on 45 substantive slides (69%).
PlantUML source for the same architecture lives in `slides/diagrams/plantuml/`
as `s2-*.puml`.

If a PNG or JPG is missing, the mermaid block is the figure.
Run `python scripts/build_slides.py` before Marp so mermaid becomes SVG.

Do not reteach Session 1. Point back, then type.
Do not demo `create_deep_agent` live unless the room is ahead.

---

## s2-01. Title

Say it plainly: this is the hour that makes the other three worth having.
Say the time out loud. 11:10 Central, 12:10 Eastern. 55 minutes. Never cut.

## s2-02. This module does not get cut

Point at 55. If a lab runs long, cut talk. Do not cut this module.
Promise the artifact: a reusable evaluation harness.

## s2-03. The loop you just built will lie to you

Three ways it lies. Edit forever, declare victory on red, stuff the window.

The last line is the thesis: a harness stops that, not a better prompt.

## s2-04. Four ways a loop lies

Same four collapses as Session 1, now named as harness gaps.
False completeness, runaway iteration, context rot, stagnation.
Each one is a missing check, not a model failure.

## s2-05. Context is not memory

Callback to Liu et al. Big output goes to a file. A short summary comes back.
That is why the planner is its own subagent. It writes `steps.jsonl` and
returns a count. The orchestrator never sees the diff.

## s2-06. A true story from this repo

Tell it as a story, not as a slide. Seven tests, green on every run, testing
the wrong tree.

The conftest put the finished answer on `sys.path` ahead of the work copy. The
fail-then-pass demo had never once worked, and nothing reported an error.

## s2-07. A check that measures the wrong thing

Land the closing line hard: a check that reports success while measuring the
wrong thing is worse than no check. That is the bug class this whole hour is
about. Callback when you hit the receipt.

## s2-08. Section. Maker and Checker

A breath. Zero minutes. Say the mapping once: maker means doer, checker means
judge. Then drop the old words.

## s2-09. Two doers, disjoint scope

The important sentence is the last one. The code implementer cannot weaken a
test, not because it was told not to, but because it holds no write path to one.

`test_implementer` writes `tests/**`. `code_implementer` writes `app/**` and is
denied `tests/**`. Judge writes nothing.

## s2-10. Five roles

Orchestrator writes nothing. Planner writes `steps.jsonl`. Two doers. Judge
reads. Same graph as Session 1, two more parts. `loops/roles.py` · `build()`.

## s2-11. Scope is a type

Show the class. There is no `write` method.

A rule in a prompt is a suggestion an agent can reason around. A missing method
is not. One minute, then move.

## s2-12. Deny always beats allow

`.loop.yml` in the target. `write_deny: ["tests/**"]` beats `write_allow`.
An empty allow list permits nothing. `WriteScope.permits`.

## s2-13. The whole sequence

Walk the diagram once, top to bottom, naming each box.

Stop on the diamond. If the new tests are not failing, the loop stops there. That
is the red gate and it gets its own slide in a moment.

Closing line: Python holds the loop, so the model never counts its own retries.

**You should be near 12 minutes here.**

## s2-14. Four planes

Intent, Execution, Verification, Control. The model proposes. The harness
decides. That is the whole module.

## s2-15. Hallucination containment

The model may claim done. The harness will not take its word. Red ids, junit,
unparseable verdict, same signature. Claims are not evidence. Files are.

## s2-16. Deep Agents

Say this once. Do not demo `create_deep_agent` live unless the room is ahead.

Deep Agents is a harness. The subagent `tools` list replaces the parent.
The judge's list is `read_file` only. No `write_file`.
Saturday they fill `harness.py`. Takehome is issue 118.

## s2-17. Python owns the gate

`create_deep_agent` does not count retries. Python still owns the red gate and
`gates.decide`. Closing of the first block.

**You should be at 15 minutes here.**

---

## s2-18. Section. Spec-driven development

A breath. Zero minutes. Clock checkpoint.

## s2-19. If an acceptance criterion cannot fail a test, it is a wish

Read AC-4 out loud. Notice it names a condition, a boundary, and a negative case.

Then say what "should be intuitive" names. Nothing.

## s2-20. Graph engineering

Intent becomes a graph of steps. `plan_for()` writes one test step and one code
step per criterion. Derived today, not generated. The schema is already enforced.
Swapping in a planner subagent is the stretch.

## s2-21. steps.jsonl

The plan is a file, so the plan is checkable. JSON Lines. Every step carries a
validation statement. A step you cannot check is a wish.

## s2-22. The plan is rejected when it cannot be checked

Name the rejections: a step with no validation statement, a criterion that
maps to no step, a step marked done with no test named as evidence, no test
step at all. `PlanRejected`. The orchestrator refuses to run it.

## s2-23. The red gate

Three steps, and step three is the one that matters.

Say the line: a test that passes before any code exists proves nothing, and it is
the most comfortable kind of nothing because it is green.

## s2-24. New failing ids

`_new_test_ids`. Not any failing ids. A test that already existed and still
fails is not proof of a new contract. Empty set means escalate.

## s2-25. The rubric

Read the ten rows. Do not explain each one.

Then say the point on the next slide: "the tests passed" is one row of ten.

## s2-26. One row of ten

That reframing is what they take back to their team. A judge that checks only
`tests_passed` can be satisfied by one trivial test. Absent evidence is never
a pass. Every `None` becomes a failing row.

## s2-27. Two judges

Four questions, three answered by arithmetic, one by a model.

Say the rule: use a model only where you must. The implementer's judge is
deterministic. The enhancer's judge reads ticket prose.

## s2-28. Why a model judge cannot be the gate

This is your own measured data. Say so.

41 articles. The deterministic detector separates good from bad at a threshold of
70. The Large Language Model quality judge saturates near 0.97 and flags 41 of 41.

A judge that approves everything is not a judge.

## s2-29. Make the verdict a schema

Three rules, one minute.

A pass carrying a critical issue is not a decision. Output that will not parse is
a fail. Absent evidence is never clean. `synthetic_fail`. Never a pass.

## s2-30. The push gate

Read the refusal text out loud, exactly as printed.

Then tell them: your agent will hit this today. Saying it now turns a surprise
into a demonstration. Claude Code `PreToolUse` hook. Reads `.harness/receipt.json`.

**You should be at 25 minutes here.**

---

## s2-31. Section. Lab 2

Lab card. 25 minutes. Walk the room. Do not reteach the architecture.

## s2-32. Lab. Fill harness.py

This is the 25 minute slide. Leave it up. Call time at 15 and at 5 remaining.

Read both commands. The `--doer none` run is the red gate refusing. Tell them
that before they run it.

`harness.py`. Three functions. Nothing else.

Walk the room. The common stall is `score_attempt`, because people try to
compute rows instead of forwarding the evidence.

## s2-33. Three functions. The order is the lesson

Leave this up while they type.

tests first, prove them red, code until green, judge, gate.

## s2-34. red_gate

Point at the docstring. An empty result must stop the loop. The solution
forwards to `implementer._new_test_ids`.

## s2-35. score_attempt

The stall. People try to compute rows. The answer is one line:
`return rubric.score(contract=contract, **evidence)`.
Absent kwargs become failing rows on purpose.

## s2-36. run_loop

Python holds the retries. `implementer.run`. Budget defaults to 3.
Three exits, no fourth. Same signature twice is escalate.

## s2-37. Two commands

`reference` copies `known-good` under write scope. `none` writes nothing.
If reference is green and none is not, the harness is honest.

## s2-38. --doer none is the red gate doing its job

No test was ever red, so nothing has been proven. Refuse to continue.
If this run were green, the harness would be lying.

## s2-39. Falling behind is fine

Copy is gone. There is no drop-in harness.py. Watch Rick finish. Save their attempt first. See `FALL-BEHIND.md`.

## s2-40. The common stall is score_attempt

Three stalls. Computing rows by hand. Returning all failed ids instead of new
ids. Editing `loops/`. Fill only `harness.py`.

## s2-41. Takehome. Deep Agents. Issue 118

After class. Same eight steps. Python still owns the gate. Do not demo live
unless the room is ahead.

---

## s2-42. Section. Reading harness output

This is the outline's 50-to-55 slot. Clock checkpoint: 50 minutes.

## s2-43. The receipt

Three claims or nothing. Passed, this tree, after the newest edit.

The closing line is the callback to s2-06: a zero exit code with no test report
is the silent-skip bug wearing a green shirt.

**You should be at 50 minutes here.**

## s2-44. tree_hash and written_at

Content, not `git status`. Staged, unstaged, and untracked all count.
Four refusal reasons from `receipt.check`. Walk them.

## s2-45. One gate is never enough

The in-process scope stops the loop's own doer. The agent is a subprocess, so it
walks straight past that one.

`write_scope` reads the diff and catches it. Defense at one layer is a demo.
The realistic cheat is in `test_weakening_a_test_after_the_fact_is_caught_by_write_scope`.

## s2-46. Read the trace

Walk one trace. `.harness/last-implementer.json`. Name the row that blocked.

Three exits. Then the rule that saves money: the same rows twice means stop.

## s2-47. gates.decide

`signature` is what failed, not how it was worded. Two equal signatures mean
the last attempt changed nothing. Green rubric plus a disagreeing final judge
is escalate.

## s2-48. Final-attempt narrowing

One minute. A doer that spends its last turn on a naming nit leaves the blocking
row unfixed. `retry_instruction` with `final_attempt`.

## s2-49. What you keep

Name the artifact: a harness that fails, iterates, passes on its own, and refuses
to ship when it should not.

## s2-50. Six lines to keep

Read them. Do not add a seventh.

## s2-51. Break

15 minutes. Next module points the same graph at a question.

## s2-52. Bibliography

Skip in the room unless asked.
