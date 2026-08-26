# Session 2 notes. Harness Engineering.

55 minutes. The center of gravity. This module never gets cut.
Artifact they keep: a reusable evaluation harness.

Vocabulary is fixed here. Unit test, e2e test, rubric, rubric judge, final judge,
planner, doer, orchestrator, target repo. The outline says "Maker and Checker".
Say once, on s2-04, that maker means doer and checker means judge, then never use
the old words again.

**Clock checkpoints.** Slide s2-07 at 15 minutes. Slide s2-18 at 25 minutes.
Slide s2-16 at 50 minutes.

---

## s2-01. Title

Say it plainly: this is the hour that makes the other three worth having.

---

## s2-02. The loop you just built will lie to you

Three ways it lies. Edit forever, declare victory on red, stuff the window.

The last line is the thesis: a harness stops that, not a better prompt.

---

## s2-03. A true story from this repo

Tell it as a story, not as a slide. Seven tests, green on every run, testing the
wrong tree.

The conftest put the finished answer on `sys.path` ahead of the work copy. The
fail-then-pass demo had never once worked, and nothing reported an error.

Land the closing line hard: a check that reports success while measuring the
wrong thing is worse than no check. That is the bug class this whole hour is
about.

---

## s2-04. Two doers, disjoint scope

Say the mapping once, here: maker means doer, checker means judge. Then drop the
old words.

The important sentence is the last one. The code implementer cannot weaken a
test, not because it was told not to, but because it holds no write path to one.

---

## s2-05. Scope is a type

Show the class. There is no `write` method.

A rule in a prompt is a suggestion an agent can reason around. A missing method
is not. One minute, then move.

---

## s2-06. The whole sequence

Walk the diagram once, top to bottom, naming each box.

Stop on the diamond. If the new tests are not failing, the loop stops there. That
is the red gate and it gets its own slide in a moment.

Closing line: Python holds the loop, so the model never counts its own retries.

**You should be at 15 minutes here.**

---

## s2-07. Section. Spec-driven development

A breath. Zero minutes.

---

## s2-08. If a criterion cannot fail a test, it is a wish

Read AC-4 out loud. Notice it names a condition, a boundary, and a negative case.

Then say what "should be intuitive" names. Nothing.

---

## s2-09. steps.jsonl

The plan is a file, so the plan is checkable.

Name the three rejections: a step with no validation statement, a criterion that
maps to no step, a step marked done with no test named as evidence.

---

## s2-10. The red gate

Three steps, and step three is the one that matters.

Say the line: a test that passes before any code exists proves nothing, and it is
the most comfortable kind of nothing because it is green.

---

## s2-11. The rubric

Read the ten rows. Do not explain each one.

Then say the point: "the tests passed" is one row of ten. That reframing is what
they take back to their team.

---

## s2-12. Two judges

Four questions, three answered by arithmetic, one by a model.

Say the rule: use a model only where you must.

---

## s2-13. Why a model judge cannot be the gate

This is your own measured data. Say so.

41 articles. The deterministic detector separates good from bad at a threshold of
70. The LLM quality judge saturates near 0.97 and flags 41 of 41.

A judge that approves everything is not a judge.

---

## s2-14. Make the verdict a schema

Three rules, one minute.

A pass carrying a critical issue is not a decision. Output that will not parse is
a fail. Absent evidence is never clean.

---

## s2-15. The push gate

Read the refusal text out loud, exactly as printed.

Then tell them: your agent will hit this today. Saying it now turns a surprise
into a demonstration.

**You should be at 25 minutes here.**

---

## s2-18. Lab 2

This slide is out of id order on purpose. It runs here, at 25 minutes.

Read both commands. The `--doer none` run is the red gate refusing. Tell them
that before they run it.

`harness.py`. Three functions. Nothing else.

25 minutes. Call time at 15 and at 5 remaining. Walk the room. The common stall
is `score_attempt`, because people try to compute rows instead of forwarding the
evidence.

---

## s2-16. The receipt

Three claims or nothing. Passed, this tree, after the newest edit.

The closing line is the callback to s2-03: a zero exit code with no test report
is the silent-skip bug wearing a green shirt.

**You should be at 50 minutes here.**

---

## s2-17. One gate is never enough

The in-process scope stops the loop's own doer. The agent is a subprocess, so it
walks straight past that one.

`write_scope` reads the diff and catches it. Defense at one layer is a demo.

---

## s2-19. Reading the output

This is the outline's 50-to-55 slot. Walk one trace.

Three exits. Then the rule that saves money: the same rows twice means stop.

---

## s2-20. Final-attempt narrowing

One minute. A doer that spends its last turn on a naming nit leaves the blocking
row unfixed.

---

## s2-21. What you keep

Name the artifact: a harness that fails, iterates, passes on its own, and refuses
to ship when it should not.

---

## s2-22. Break

15 minutes. Next module points the same graph at a question.
