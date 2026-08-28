---
marp: true
paginate: true
title: Session 2. Harness Engineering
description: Engineering Reliable Agentic AI Systems. Packt. 29 August 2026.
footer: Spillwave Solutions | spillwave.com
style: |
  /* @theme spillwave */
  @import url("https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap");

  :root {
    --bg: #eef2f7;
    --surface: #ffffff;
    --ink: #1b2437;
    --muted: #4a5b70;
    --faint: #7a8b9c;
    --navy: #1a365d;
    --orange: #d9772a;
    --teal: #2aa8bb;
    --line: #c9d4e0;
    --stripe: #1e3a6e;
  }

  section {
    background-color: var(--bg);
    background-size: contain !important;
    background-repeat: no-repeat !important;
    background-position: center right !important;
    color: var(--ink);
    font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
    padding: 28px 48px 50px;
    font-size: 20px;
    line-height: 1.32;
    justify-content: flex-start;
    overflow: hidden;
  }

  section::before {
    content: "SPILLWAVE SOLUTIONS  ·  LOOP ENGINEERING WORKSHOP";
    display: block;
    color: var(--navy);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--line);
    padding-bottom: 6px;
    margin-bottom: 12px;
  }

  section::after {
    color: var(--faint);
    font-size: 11px;
    font-weight: 500;
  }

  h1 {
    font-family: "Plus Jakarta Sans", sans-serif;
    font-style: normal;
    font-weight: 800;
    color: var(--ink);
    font-size: 28px;
    line-height: 1.12;
    letter-spacing: -0.028em;
    margin: 0 0 12px 0;
  }

  h2,
  h3 {
    color: var(--navy);
    font-weight: 700;
  }

  p,
  li {
    color: var(--ink);
  }

  ul {
    list-style: none;
    padding-left: 0;
    margin: 0;
  }

  ul li {
    position: relative;
    padding: 8px 0 8px 20px;
    border-bottom: 1px solid var(--line);
    font-size: 20px;
    line-height: 1.32;
  }

  ul li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.95em;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--navy);
  }

  ul li:last-child {
    border-bottom: none;
  }

  ul li:last-child::before {
    background: var(--orange);
  }

  small,
  cite {
    color: var(--muted);
    font-size: 13px;
  }

  code,
  pre {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    background: #e4eaf2;
    color: var(--ink);
    font-size: 14px;
  }

  pre {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 12px 14px;
    max-height: 300px;
    overflow: auto;
  }

  table {
    font-size: 16px;
    width: 100%;
  }

  th {
    color: var(--muted);
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  td {
    border-color: var(--line);
    padding: 6px 10px 6px 0;
  }

  img {
    display: block;
    margin: 8px auto 0;
    max-width: 100%;
    height: auto;
    object-fit: contain;
    object-position: center;
  }

  footer {
    color: var(--muted);
    font-size: 11px;
  }

  /* Title */
  section.lead::before {
    display: none;
  }

  section.lead {
    border-left: 14px solid var(--stripe);
    padding: 40px 48px 40px 40px;
    justify-content: center;
  }

  section.lead h1 {
    font-size: 44px;
    font-weight: 800;
    color: var(--ink);
    font-style: normal;
    line-height: 1.08;
  }

  section.lead p {
    color: var(--navy);
    font-weight: 500;
    font-size: 20px;
  }

  .hero {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 20px;
    align-items: center;
    width: 100%;
  }

  .hero img {
    max-height: 420px;
    width: 100%;
    object-fit: contain;
    margin: 0;
  }

  /* Diagram-first slides: the drawing is the slide */
  section.diagram h1 {
    font-size: 26px;
    margin-bottom: 8px;
  }

  section.diagram img {
    max-height: 340px;
    width: auto;
    max-width: 100%;
    margin-top: 4px;
  }

  section.diagram p,
  section.diagram small {
    margin-top: 8px;
  }
---

<!--
id: s2-01
layout: title
minutes: 1
beat: talk
_class: lead
notes: This is the hour that makes the other three worth having. Say the time. 11:10 Central. 55 minutes. This module never gets cut.
-->

<!-- _class: lead -->

<div class="hero">
<div>

# Harness Engineering, the validation layer

Session 2. The center of gravity. 55 minutes.

Saturday 29 August 2026. 11:10 Central.

Rick Hightower. Spillwave. Packt workshop.

</div>

![w:480](images/title-mark.jpg)

</div>

---

<!--
id: s2-02
layout: figure-bottom
minutes: 1
beat: talk
notes: Point at 55. If a lab runs long, cut talk. Do not cut this module. Artifact they keep: a reusable evaluation harness.
-->

<!-- _class: diagram -->

# 55 minutes. This is the one that does not get cut.

![w:1000](images/diagram-s2-02.jpg)

| Block | Minutes | What they keep |
|---|---|---|
| Why loops fail without a harness | 0 to 15 | Maker and Checker as types |
| Spec-driven development | 15 to 25 | Intent as a testable contract |
| Lab. Fill `harness.py` | 25 to 50 | Three functions that hold the loop |
| Reading output. When to stop | 50 to 55 | Three exits, a receipt, a gate |

---

<!--
id: s2-03
layout: split-right
minutes: 1
beat: talk
image: images/loop-without-harness.jpg
image_prompt: >
  16:9. The Session 1 five-box loop, now jittering. Verify is a shrug made of
  dust. Extra arrows spawn and never stop. Gray-green. No logos. No readable UI.
notes: Three ways it lies. Edit forever, declare victory on red, stuff the window. Last line is the thesis.
-->

# The loop you just built will lie to you.

- It can edit forever.
- It can declare victory on a red test.
- It can stuff the whole repo into the next call.
- A harness is how you stop that. Not a better prompt.

---

<!--
id: s2-04
layout: figure-bottom
minutes: 1
beat: talk
notes: Four collapses from Session 1, now named as harness gaps. Each one is a missing check, not a model failure.
-->

<!-- _class: diagram -->

# Four ways a loop lies. Each is a missing harness piece.

![w:1000](images/diagram-s2-04.jpg)

| Failure | Missing piece | What this hour adds |
|---|---|---|
| False completeness | Independent verify | Ten-row rubric, red gate |
| Runaway iteration | External transition | `gates.decide()` |
| Context rot | Memory on disk | Planner subagent, summaries |
| Stagnation | Progress detection | Same signature twice |

---

<!--
id: s2-05
layout: figure-bottom
minutes: 1
beat: talk
notes: Liu et al. from Session 1. The planner is its own subagent so the plan never sits in the orchestrator window. Big output goes to a file.
-->

<!-- _class: diagram -->

# Context is not memory. The window is a scratch pad.

![w:1000](images/diagram-s2-05.jpg)

The orchestrator sees summaries. Never the whole plan. Never the patch.

That is why the planner runs as its own subagent. It writes `steps.jsonl` and returns a count.

<small>Liu et al., Lost in the Middle. TACL 2024. arXiv:2307.03172</small>

---

<!--
id: s2-06
layout: figure-bottom
minutes: 2
beat: talk
notes: Tell it as a story. Seven tests, green on every run, testing the wrong tree. Land the closing line hard.
-->

<!-- _class: diagram -->

# A true story from this repo.

Seven tests. Green on every run. They had never tested the thing they named.

```python
# tests/conftest.py
CRM_ROOT = Path(__file__).resolve().parents[2] / "crm"
sys.path.insert(0, str(CRM_ROOT))   # wins over the PYTHONPATH the loop sets
```

![w:1000](images/diagram-s2-06.jpg)

The loop pointed the tests at the work copy. The conftest pointed them at the finished answer.

---

<!--
id: s2-07
layout: figure-bottom
minutes: 1
beat: talk
notes: This is the bug class the whole hour is about. A silent skip wearing a green shirt. Callback when you hit the receipt.
-->

<!-- _class: diagram -->

# A check that measures the wrong thing is worse than no check.

![w:1000](images/diagram-s2-07.jpg)

The fail-then-pass demo had never once worked. Nothing reported an error.

Absent evidence is never clean. That rule shows up in the rubric, the receipt, and the final judge.

---

<!--
id: s2-08
layout: section
minutes: 0
beat: talk
_class: lead
notes: Section card. Say the mapping once. Maker means doer. Checker means judge. Then drop the old words.
-->

# Maker and Checker

Two doers. Disjoint scope. A judge with no hands.

---

<!--
id: s2-09
layout: split-left
minutes: 2
beat: talk
image: images/two-doers.jpg
image_prompt: >
  16:9. Two desks separated by a low wall. Left desk labeled TEST IMPLEMENTER
  holds a red pen and a stack of test cards. Right desk labeled CODE IMPLEMENTER
  holds a keyboard and source files, and has no reach over the wall. A third
  figure at a lectern labeled JUDGE has no keyboard at all. No logos.
notes: Say the mapping once, here: maker means doer, checker means judge. Then drop the old words. The last sentence is the one they quote.
-->

# Two doers. Disjoint scope.

- The test implementer writes `tests/**`. Nothing else.
- The code implementer writes `app/**`. It is **denied** `tests/**`.
- The judge writes nothing at all.

The code implementer cannot weaken a test to reach green. Not because it was told not to. Because it holds no write path to one.

---

<!--
id: s2-10
layout: figure-bottom
minutes: 1
beat: talk
notes: Five roles. Orchestrator writes nothing. Planner writes steps.jsonl. Two doers. Judge reads. Same graph as Session 1, two more parts.
-->

<!-- _class: diagram -->

# Five roles. Write scope is the point.

![w:1000](images/diagram-s2-10.jpg)

<small>`loops/roles.py` · `build()`</small>

---

<!--
id: s2-11
layout: figure-bottom
minutes: 1
beat: talk
notes: Show the class. There is no write method. A rule in a prompt is a suggestion. A missing method is not. One minute, then move.
-->

# Scope is a type, not a sentence.

```python
@dataclass
class Judge(Role):
    """Scores work. Holds no write path.

    There is deliberately no `write` method on this class.
    Adding one is not a convenience. It is the end of the split.
    """

    def read(self, relative: str) -> str:
        return (self.repo / relative).read_text(encoding="utf-8")
```

A rule in a prompt is a suggestion an agent can reason its way around. A missing method is not.

<small>`loops/roles.py` · `test_a_judge_has_no_write_method`</small>

---

<!--
id: s2-12
layout: figure-bottom
minutes: 1
beat: talk
notes: Deny always beats allow. The code implementer has app/** allowed and tests/** denied. An empty allow list permits nothing.
-->

<!-- _class: diagram -->

# Deny always beats allow.

![w:1000](images/diagram-s2-12.jpg)

```python
code_implementer:
  write_allow: ["app/**", "src/**"]
  write_deny:  ["tests/**"]
```

<small>`loops/roles.py` · `WriteScope.permits` · `.loop.yml` in the target</small>

---

<!--
id: s2-13
layout: figure-top
minutes: 2
beat: talk
notes: Walk the diagram once, top to bottom. Stop on the diamond. If the new tests are not failing, the loop stops there. Python holds the loop, so the model never counts its own retries. You should be near 12 minutes.
-->

<!-- _class: diagram -->

![w:1000](images/diagram-s2-13.jpg)

# The orchestrator owns the budget and sees summaries, never the diff.

Python holds the loop. The model never counts its own retries.

---

<!--
id: s2-14
layout: figure-bottom
minutes: 1
beat: talk
notes: Four planes. One graph. The model proposes. The harness decides. That is the whole module.
-->

<!-- _class: diagram -->

# Four planes. One graph.

![w:1000](images/diagram-s2-14.jpg)

| Plane | Who | Job |
|---|---|---|
| Intent | The ready ticket | A contract a test can fail |
| Execution | Maker | Writes inside a declared scope |
| Verification | Checker | Read-only, or Python over junit |
| Control | Harness | Budget, retry, stop. Outside the model |

---

<!--
id: s2-15
layout: figure-bottom
minutes: 1
beat: talk
notes: Hallucination containment is architectural. The model may claim done. The harness will not take its word.
-->

<!-- _class: diagram -->

# Hallucination containment is a missing method, not a better prompt.

![w:1000](images/diagram-s2-15.jpg)

The model proposes. The harness decides. Claims are not evidence. Files are.

---

<!--
id: s2-16
layout: figure-bottom
minutes: 1
beat: talk
notes: Deep Agents is a harness, not a chat wrapper. Subagent tools list REPLACES the parent. Judge gets read_file only. Do not demo create_deep_agent live unless the room is ahead. Saturday they fill harness.py.
-->

<!-- _class: diagram -->

# This graph in Deep Agents.

`create_deep_agent` is a harness, not a chat wrapper.

![w:1000](images/diagram-s2-16.jpg)

- Each subagent gets its own `tools` list. That list **replaces** the parent.
- The judge's list is `read_file`. No `write_file`.
- Path scope lives inside the write tool. `WriteScope.check` still runs.

<small>`solutions/sol2_implementer_deep_agents/roles.py`</small>

---

<!--
id: s2-17
layout: figure-bottom
minutes: 1
beat: talk
notes: Closing of the first block. create_deep_agent does not count retries. Python still owns the red gate and gates.decide. You should be at 15 minutes here.
-->

<!-- _class: diagram -->

# Python owns the gate. `create_deep_agent` does not count retries.

![w:1000](images/diagram-s2-17.jpg)

```python
return create_deep_agent(
    model=model,
    tools=[run_tests_tool(repo)],
    subagents=subagents_for(contract, loop),
)
```

Saturday lab stays Claude Code. Fill `harness.py`.

The Deep Agents port is the takehome. `solutions/sol2_implementer_deep_agents/`. Issue 118.

---

<!--
id: s2-18
layout: section
minutes: 0
beat: talk
_class: lead
notes: A breath. Zero minutes. Clock checkpoint: 15 minutes. Intent becomes a contract the machine can check.
-->

# Spec-driven development

Intent becomes a contract the machine can check.

---

<!--
id: s2-19
layout: split-right
minutes: 1
beat: talk
image: images/ready-ticket-rubric.jpg
image_prompt: >
  16:9. Left, a ticket with bullet criteria. Right, the same bullets as a
  checklist with empty pass boxes, each wired to a named test. Paper and green
  ink. No logos.
notes: Read AC-4 out loud. Notice it names a condition, a boundary, and a negative case. Then say what should be intuitive names. Nothing.
-->

# If an acceptance criterion cannot fail a test, it is a wish.

```markdown
- (AC-4) `GET /api/tasks?due_before=<date>`
  returns only tasks due before that date,
  and never tasks with no due date.
```

Seven acceptance criteria. Each one names a condition a test can be red about.

"Should be intuitive" names nothing.

---

<!--
id: s2-20
layout: figure-bottom
minutes: 1
beat: talk
notes: Graph engineering. Intent becomes a graph of steps. Each criterion maps to a test step and a code step. The planner is derived today, a subagent as stretch.
-->

<!-- _class: diagram -->

# Graph engineering. Intent becomes a graph of steps.

![w:1000](images/diagram-s2-20.jpg)

`loops/implementer.py` · `plan_for()`. Derived, not generated. Swapping this for a planner subagent is the stretch. The schema it must satisfy is already enforced.

---

<!--
id: s2-21
layout: figure-bottom
minutes: 1
beat: talk
notes: The plan is a file, so the plan is checkable. Read the JSON. Name validation. A step you cannot check is a wish.
-->

# The plan is a file, and it is checkable.

```json
{"id":"S1T","ticket":"T001","role":"test_implementer",
 "action":"Write a test that fails until due_date accepts null",
 "validation":"a test covering AC-1 exists and fails before any code",
 "criterion":"AC-1","status":"todo","evidence":null}
```

`steps.jsonl`. JSON Lines. Every step carries a **validation statement**.

The file is disposable. It belongs to one run against one ticket.

<small>`loops/steps.py`</small>

---

<!--
id: s2-22
layout: figure-bottom
minutes: 1
beat: talk
notes: Name the three rejections. Plus two more the code actually raises: no test step, marking done without evidence. Keep it to the three the outline names, then the evidence rule.
-->

<!-- _class: diagram -->

# The plan is rejected when it cannot be checked.

![w:1000](images/diagram-s2-22.jpg)

`PlanRejected`. The orchestrator refuses to run it.

Marking a step done without naming the test that proves it is grading the loop on a claim.

<small>`loops/steps.py` · `validate()` · `mark()`</small>

---

<!--
id: s2-23
layout: split-left
minutes: 1
beat: talk
image: images/red-gate.jpg
image_prompt: >
  16:9. A traffic gate across a road. The barrier is down. A sign reads
  NO RED, NO ENTRY. Behind the gate, a test result card showing four failures in
  red, being checked by a guard. Workshop poster style. No logos.
notes: Three steps, and step three is the one that matters. A test that passes before any code exists proves nothing, and it is the most comfortable kind of nothing because it is green.
-->

# The red gate. Tests first, and prove it.

1. The test implementer writes the tests.
2. The orchestrator reads `junit.xml`.
3. **If the new tests are not failing, stop.**

A test that passes before any code exists proves nothing. It is the most comfortable kind of nothing, because it is green.

---

<!--
id: s2-24
layout: figure-bottom
minutes: 1
beat: talk
notes: Show the function. New failing ids, not any failing ids. A test that already existed and still fails is not proof of a new contract.
-->

<!-- _class: diagram -->

# New failing ids. Not any failing ids.

```python
def _new_test_ids(before: set[str], after_failed: set[str]) -> set[str]:
    """Test ids that are failing now and did not exist before. The red proof."""
    return {test_id for test_id in after_failed if test_id not in before}
```

![w:1000](images/diagram-s2-24.jpg)

<small>`loops/implementer.py` · `_new_test_ids` · `require_red` in `.loop.yml`</small>

---

<!--
id: s2-25
layout: figure-bottom
minutes: 2
beat: talk
notes: Read the ten rows. Do not explain each one. Then say the point on the next slide: the tests passed is one row of ten.
-->

# The rubric. Ten rows. No model call.

```
PASS  tests_ran          25 tests
PASS  tests_passed       all green
PASS  red_first          6 tests were red first
PASS  coverage_floor     80.42% against a floor of 78.0%
PASS  criteria_covered   all covered
PASS  steps_done         14 steps: done 14
PASS  ui_has_e2e         2 interface files changed, end-to-end green
PASS  format_clean       clean
PASS  lint_clean         clean
PASS  write_scope        every write was inside its role's scope
```

Every row is computed from `junit.xml`, `coverage.xml`, exit codes, `steps.jsonl`, and the diff.

<small>`loops/rubric.py` · `score()`</small>

---

<!--
id: s2-26
layout: figure-bottom
minutes: 1
beat: talk
notes: That reframing is what they take back to their team. A judge that checks only tests_passed can be satisfied by one trivial test.
-->

<!-- _class: diagram -->

# "The tests passed" is one row of ten.

![w:1000](images/diagram-s2-26.jpg)

A judge that checks only `tests_passed` can be satisfied by an agent that writes one trivial test and deletes the rest.

Absent evidence is never a pass. Every argument left `None` becomes a failing row.

---

<!--
id: s2-27
layout: split-right
minutes: 1
beat: talk
image: images/two-judges.jpg
image_prompt: >
  16:9. Left, a mechanical scale with exact weights, labeled DETERMINISTIC.
  Right, a person reading a document with a thoughtful expression, labeled
  MODEL. Between them a divider showing which questions go which way. No logos.
notes: Four questions, three answered by arithmetic, one by a model. Use a model only where you must.
-->

# Two judges, and only one of them guesses.

| Question | Who answers |
|---|---|
| Did the tests run and pass? | Arithmetic |
| Does coverage meet the floor? | Arithmetic |
| Did anyone write outside scope? | Arithmetic |
| **Is the ticket actually done?** | A model |

Use a model only where you must.

The implementer's judge is deterministic. The enhancer's judge reads ticket prose and needs a model.

---

<!--
id: s2-28
layout: figure-bottom
minutes: 1
beat: talk
notes: This is your own measured data. Say so. 41 articles. Deterministic detector gates at 70. LLM quality judge saturates near 0.97 and flags 41 of 41. A judge that approves everything is not a judge.
-->

<!-- _class: diagram -->

# Why a model judge cannot be the gate.

Measured across 41 published articles in a production pipeline:

![w:1000](images/diagram-s2-28.jpg)

| Judge | Behavior |
|---|---|
| Deterministic tell-detector | Gates at 70. Separates good from bad. |
| Large Language Model (LLM) quality judge | Saturates near 0.97. Flags **41 of 41**, regardless. |

A judge that approves everything is not a judge. It is a rubber stamp with a temperature setting.

---

<!--
id: s2-29
layout: figure-bottom
minutes: 1
beat: talk
notes: Three rules. A pass carrying a critical issue is not a decision. Output that will not parse is a FAIL, never a pass. Absent evidence is never clean.
-->

<!-- _class: diagram -->

# So make the model's verdict a schema.

```python
if verdict.done and verdict.blocking_issues:
    return synthetic_fail("says done while listing blocking issues")
```

![w:1000](images/diagram-s2-29.jpg)

- A pass carrying a critical issue is not a decision. Reject it.
- Output that will not parse is a **FAIL**, never a pass.
- Absent evidence is never clean.

<small>`loops/final_judge.py` · `parse_verdict` · `synthetic_fail`</small>

---

<!--
id: s2-30
layout: split-left
minutes: 1
beat: talk
image: images/push-gate.jpg
image_prompt: >
  16:9. A terminal window mid-command, with a red BLOCKED banner across it. A
  physical turnstile in front of the screen. A small green paper receipt on the
  desk beside it, unstamped. No logos, no readable brand names.
notes: Read the refusal text out loud, exactly as printed. Then tell them: your agent will hit this today. Saying it now turns a surprise into a demonstration. You should be at 25 minutes. Lab next.
-->

# The gate that makes it real.

```
BLOCKED by pre-tool hook: git push
Last run: FAILED (1 tests).
  first failure: tests.test_due_date::test_model_has_optional_due_date
Run `task test` first.
```

A Claude Code `PreToolUse` hook refuses `git push` without a green receipt.

No push and no pull request until the suite runs green locally.

Your agent will hit this today.

---

<!--
id: s2-31
layout: section
minutes: 0
beat: lab
_class: lead
notes: Lab card. 25 minutes. Walk the room. Do not reteach the architecture. Point at harness.py.
-->

# Lab 2. The Ticket Implementer

25 minutes. A ready ticket in. A green rubric out.

---

<!--
id: s2-32
layout: lab
minutes: 20
beat: lab
notes: Read both commands. The --doer none run is the red gate refusing. Tell them that before they run it. harness.py. Three functions. Nothing else. Call time at 15 and at 5 remaining.
-->

# Lab. 25 minutes. Fill `harness.py`.

```bash
cd labs/lab2_implementer
claude -p "$(cat prompts/claude-code.md)"
```

Fill three functions. Nothing else.

```bash
task loop:implementer -- --ticket T001 --doer reference   # ten rows
task loop:implementer -- --ticket T001 --doer none        # red gate refuses
```

Falling behind is fine: watch Rick finish `harness.py` and keep going.

---

<!--
id: s2-33
layout: figure-bottom
minutes: 1
beat: lab
notes: The order is the whole point. Leave this up while they type. tests first, prove them red, code until green, judge, gate.
-->

<!-- _class: diagram -->

# Three functions. The order is the lesson.

![w:1000](images/diagram-s2-33.jpg)

```
tests first  ->  prove them red  ->  code until green  ->  judge  ->  gate
```

`red_gate`. `score_attempt`. `run_loop`. The stub already imports `gates` and `rubric`.

<small>`labs/lab2_implementer/harness.py`</small>

---

<!--
id: s2-34
layout: figure-bottom
minutes: 1
beat: lab
notes: Point at the docstring. An empty result must stop the loop. The solution forwards to implementer._new_test_ids.
-->

# `red_gate(before, after)`. New ids that are failing now.

```python
def red_gate(before: RunResult, after: RunResult) -> set[str]:
    """Return the test ids that are failing now and did not exist before.

    A test that passes before any code is written proves nothing,
    so an empty result must stop the loop rather than let it continue.
    """
    seen = before.junit.passed_ids | before.junit.failed_ids
    return implementer._new_test_ids(seen, after.junit.failed_ids)
```

An empty set is not a small problem. It is the red gate refusing.

---

<!--
id: s2-35
layout: figure-bottom
minutes: 1
beat: lab
notes: Common stall lives here. People try to compute rows instead of forwarding the evidence. The answer is one line. Absent kwargs become failing rows.
-->

<!-- _class: diagram -->

# `score_attempt`. Forward the evidence. Do not invent rows.

```python
def score_attempt(contract: Contract, **evidence) -> rubric.Score:
    """Score one attempt against the ten rubric rows.

    Every argument left out becomes a failing row.
    Absent evidence is never a pass.
    """
    return rubric.score(contract=contract, **evidence)
```

![w:1000](images/diagram-s2-35.jpg)

Do not compute the rows yourself. `loops/rubric.py` already does.

---

<!--
id: s2-36
layout: figure-bottom
minutes: 1
beat: lab
notes: Python holds the loop. run_loop calls implementer.run. The model does not get to count its own retries. budget defaults to 3.
-->

<!-- _class: diagram -->

# `run_loop`. Python holds the retries.

```python
def run_loop(contract: Contract, budget: int = 3, ticket_id: str = "T001") -> dict:
    """Run the harness until it passes, stalls, or runs out of budget.

    Hold the loop in Python. The model does not get to count its own retries.
    """
    return implementer.run(
        repo=contract.repo,
        ticket_id=ticket_id,
        budget=budget,
        doer="reference",
    )
```

![w:1000](images/diagram-s2-36.jpg)

<small>`loops/gates.py` · `decide()`</small>

---

<!--
id: s2-37
layout: lab
minutes: 1
beat: lab
notes: Two commands. Reference copies known-good under write scope. None writes nothing, so the red gate must refuse. If reference is green and none is not, the harness is honest.
-->

# Two commands. Honesty is the second one.

```bash
task loop:implementer -- --ticket T001 --doer reference
# copies known-good into tests/** then app/**
# expect ten PASS rows and gate: pass

task loop:implementer -- --ticket T001 --doer none
# writes nothing on purpose
# expect gate: escalate
# reason: red gate: no new test was observed failing
```

The `none` backend is how you prove the loop reports failure honestly, with no model key.

---

<!--
id: s2-38
layout: figure-bottom
minutes: 1
beat: lab
notes: Walk this if they ask why none fails. No test was ever red, so nothing has been proven. Refuse to continue.
-->

<!-- _class: diagram -->

# `--doer none` is the red gate doing its job.

![w:1000](images/diagram-s2-38.jpg)

`test_a_doer_that_writes_nothing_is_stopped_by_the_red_gate`.

If this run were green, the harness would be lying.

---

<!--
id: s2-39
layout: lab
minutes: 1
beat: lab
notes: Say the fall-behind rule. There is no drop-in harness.py. Watch Rick finish. Nobody leaves this room behind.
-->

# Falling behind is fine. Watch Rick finish and continue.

```bash
cp harness.py harness.py.my-attempt
```

There is no drop-in `harness.py`. Watch Rick finish and type what he typed.

You continue the next module with a working artifact.

Put the empty stub back later if you want to retry:

```bash
git checkout -- harness.py
```

See `labs/lab2_implementer/FALL-BEHIND.md`.

---

<!--
id: s2-40
layout: figure-bottom
minutes: 1
beat: lab
notes: The common stall is score_attempt. People try to compute rows. Tell them to forward **evidence. If they stall on red_gate, they forgot passed_ids union failed_ids.
-->

<!-- _class: diagram -->

# The common stall is `score_attempt`.

![w:1000](images/diagram-s2-40.jpg)

If you stall, read `loops/implementer.py`, `loops/rubric.py`, and `loops/gates.py`. They are the answer, not a hint.

Do not edit the target repo's tests to make something pass.

---

<!--
id: s2-41
layout: figure-bottom
minutes: 1
beat: lab
notes: After class. Same eight steps. Python still owns the gate. Do not demo live unless the room is ahead. Issue 118.
-->

<!-- _class: diagram -->

# After class. The same eight steps on Deep Agents.

![w:1000](images/diagram-s2-41.jpg)

```bash
cd solutions/sol2_implementer_deep_agents
python3 -m pytest tests -q
python3 harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer deep
```

`--doer deep` needs `deepagents` installed. The tests do not.

Python still owns the red gate and `gates.decide`. The model never counts its own retries.

---

<!--
id: s2-42
layout: section
minutes: 0
beat: lab
_class: lead
notes: 50 to 55 slot. Clock checkpoint: 50 minutes. Walk one trace. Name the row that blocked.
-->

# Reading harness output

Knowing when to stop is the feature.

---

<!--
id: s2-43
layout: figure-bottom
minutes: 1
beat: talk
notes: Three claims or nothing. Passed, this tree, after the newest edit. Callback to conftest: a zero exit code with no test report is the silent-skip bug wearing a green shirt.
-->

<!-- _class: diagram -->

# A receipt proves three things, or it proves nothing.

```json
{"green": true,
 "tree_hash": "3da2f2dc9611...",
 "written_at": 1787720405.98,
 "report_usable": true}
```

![w:1000](images/diagram-s2-43.jpg)

A zero exit code with no test report is not green. It is the silent-skip bug wearing a green shirt.

<small>`scripts/receipt.py`</small>

---

<!--
id: s2-44
layout: figure-bottom
minutes: 1
beat: talk
notes: tree_hash is content, not git status. Staged, unstaged, and untracked all count. written_at must beat newest_source_mtime. Show check() reasons.
-->

<!-- _class: diagram -->

# `tree_hash` and `written_at`. Stale is a refusal.

![w:1000](images/diagram-s2-44.jpg)

<small>`scripts/receipt.py` · `check()`</small>

---

<!--
id: s2-45
layout: figure-bottom
minutes: 1
beat: talk
notes: The agent is a subprocess. In-process scope stops the loop's own doer. write_scope reads the diff and catches the subprocess. Defense at one layer is a demo.
-->

<!-- _class: diagram -->

# One gate is never enough.

The write scope lives in the loop. Your agent is a **subprocess**.

![w:1000](images/diagram-s2-45.jpg)

```
in-process scope   stops the loop's own doer
rubric write_scope reads the diff, catches the subprocess
```

An agent that edits a test to reach green defeats the first and not the second.

Defense at one layer is a demo. Defense at two is a harness.

<small>`labs/lab2_implementer/` · write scope in the loop and in the rubric</small>

---

<!--
id: s2-46
layout: figure-bottom
minutes: 1
beat: talk
notes: Walk one trace. .harness/last-implementer.json. Ten rows, the gate, and the reason. The interesting run is the one that stops.
-->

<!-- _class: diagram -->

# Read the trace. Name the row that blocked.

```
FAIL  coverage_floor     71.4% against a floor of 78.0%
gate: escalate
reason: the same rows failed twice: coverage_floor. Not converging.
```

![w:1000](images/diagram-s2-46.jpg)

- `pass` and you are done.
- `retry` and the doer gets one more scoped attempt.
- `escalate` and a human takes it.

**The same rows twice means stop.**

---

<!--
id: s2-47
layout: figure-bottom
minutes: 1
beat: talk
notes: signature is what failed, not how it was worded. Two equal signatures mean the last attempt changed nothing. gates.decide has the same signature twice as escalate. Also: green rubric but final judge says not done is escalate.
-->

<!-- _class: diagram -->

# `gates.decide()`. Same signature twice is escalate.

![w:1000](images/diagram-s2-47.jpg)

`signature` is the failed row names, not the wording.

Green rubric plus `judge_done=False` is escalate. The deterministic rows can all pass on work that misses the point.

<small>`loops/gates.py` · `decide()`</small>

---

<!--
id: s2-48
layout: figure-bottom
minutes: 1
beat: talk
notes: One minute. A doer that spends its last turn on a naming nit leaves the blocking row unfixed. retry_instruction narrows on final_attempt.
-->

<!-- _class: diagram -->

# On the final attempt, narrow the ask.

```
FINAL ATTEMPT. Fix only what blocks: tests_passed.
Do not refactor. Do not address anything else.
```

![w:1000](images/diagram-s2-48.jpg)

A doer that spends its last turn on a naming nit leaves the blocking row unfixed.

<small>`loops/gates.py` · `retry_instruction()`</small>

---

<!--
id: s2-49
layout: figure-bottom
minutes: 1
beat: talk
notes: Name the artifact: a harness that fails, iterates, passes on its own, and refuses to ship when it should not.
-->

<!-- _class: diagram -->

# What you keep.

A harness that fails, iterates, and passes on its own, and refuses to ship when it should not.

![w:1000](images/diagram-s2-49.jpg)

The reusable evaluation harness is `harness.py` plus `loops/rubric.py`, `loops/gates.py`, and `scripts/receipt.py`.

---

<!--
id: s2-50
layout: figure-bottom
minutes: 1
beat: talk
notes: Six lines. Read them. Do not add a seventh.
-->

# Six lines to keep.

1. Two doers. Disjoint scope. The judge has no write method.
2. A step without a validation statement is a wish.
3. New tests must be red before code starts.
4. "The tests passed" is one row of ten.
5. Unparseable is FAIL. Same signature twice is stop.
6. A receipt proves three things, or it proves nothing.

---

<!--
id: s2-51
layout: title
minutes: 0
beat: bridge
_class: lead
notes: 15 minutes. Next module points the same graph at a question. MCP. One tool boundary.
-->

# Break. 15 minutes.

Next: the same graph, pointed at a question instead of a ticket.

---

<!--
id: s2-52
layout: figure-bottom
minutes: 0
beat: talk
notes: Bibliography. Skip in the room unless asked.
-->

# Primary references for this session.

- Liu et al. Lost in the Middle. TACL 2024. arXiv:2307.03172
- Yao et al. ReAct. arXiv:2210.03629
- Ridnik, Kredo, Friedman. AlphaCodium. arXiv:2401.08500
- `loops/implementer.py`, `loops/rubric.py`, `loops/gates.py`, `loops/roles.py`, `loops/steps.py`, `loops/final_judge.py`
- `scripts/receipt.py`
- `labs/lab2_implementer/ARCHITECTURE.md`
- `solutions/sol2_implementer_deep_agents/SPEC.md`
