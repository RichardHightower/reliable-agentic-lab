---
date: 2026-09-07
slug: sol2-implementer-review
title: "Sol 2 implementer review: where the loop still misses the Module 2 slides"
git_base: "cb88cbc8"
epic: 414
wiki: Sol-2-Implementer-Review
plan: Sol-2-Workflow-Plan
---

# Sol-2 implementer review

Read this first. Then execute
[Sol-2-Workflow-Plan](https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-2-Workflow-Plan)
(`docs/plans/2026-09-07-sol2-workflow.md`) against
[#414](https://github.com/RichardHightower/reliable-agentic-lab/issues/414).

This is a review of `main` at `cb88cbc` (3 September #288 already in). It is
not a rewrite proposal. The eight-step loop stays. The work is to make the
demo match the slides, or to make the slides match the demo.

Wiki copy: [[Sol-2-Implementer-Review]].

## What #287 / #288 already made true

Both take-home ports are standalone eight-step drivers.

| Folder | Runtime | Live doer |
|---|---|---|
| `solutions/sol2_implementer_deep_agents` | LangChain Deep Agents | `--doer deep` |
| `solutions/sol2_implementer_agent_sdk` | Claude Agent SDK | `--doer sdk` |

Python owns ready-ticket-in, `plan_for` → `steps.jsonl`, the red gate, the
ten-row rubric, `parse_judge_verdict` (garbage is `done=False`), and
`gates.decide`. Retry on the **code** phase prepends `gates.retry_instruction`
plus failing test ids. Receipt is three claims: green, this tree, newer than
the last edit. Saturday Lab 2 is still `labs/lab2_implementer`.

Do not reopen #190. Option 1 already shipped: the judge is wired.

## The five primitives, scored

Loop engineering is trigger, scope, verify, state on disk, three exits.

| Primitive | Sol2 today |
|---|---|
| Trigger | Yes. Ready ticket in. `Ticket.ready` fail-closed. |
| Scope | Yes, with a DA/SDK split. SDK has `OVERRIDES` + `GLOBAL_DENY = ["Bash"]` and tests. DA `roleplan.py` still grants `Bash` to the judge and to every writer. `CliBackend` allows it. |
| Verify | Rubric yes. Judge **called** yes. Judge **informed** no: the prompt says "this diff" and does not include one. Offline judge cannot say no. |
| State on disk | Half. `.harness/last-implementer.json` + `.harness/receipt.json`. No `state.json`. No `--resume`. |
| Three exits | In-process yes (`pass` / `retry` / `escalate`). Process exit is 0 or 1. Escalate is not 2. Crash is not distinct. |

Four of five. The missing spine is why Module 4 still has to introduce
`state.json` as if Module 2 never wrote a file.

## Slide promises that the folders do not keep

### 1. The push gate

FEATURE-MAP:

> The push gate · 2 · A `PreToolUse` hook refuses `git push` without a green receipt

Session-2 s2-30: "your agent will hit this today." s2-44: "Four refusal
reasons from `receipt.check`."

`receipt.check` is real and has **six** failure returns plus green. Nothing
in either sol2 folder, `hooks/`, or a PreToolUse matcher calls it. Tests
cover `write()`, not `check()`.

Tell the truth or wire the hook. Not both, not neither.

### 2. The judge sees the diff

Judge skill (both ports):

> Answer one question: does this diff do what the ticket asked for?

`_ask_judge` sends the ticket and `score.report()`. `git diff` is never
computed for the judge. A model asked about a diff it cannot read will
invent one from the rubric, which is the bug class Module 2 exists to kill.

`Backend.judge` on `none` / `reference` returns `done=True`. There is no
offline fixture that returns `done=False` through that method, so the
green-rubric / judge-says-no path is a unit-test patch, not a classroom
backend.

### 3. Isolated run

HOW_TO_RUN resets `work/northwind-field-crm` in place. Two attendees, or
one live run after a reference run, share one dirty tree. The loop has no
worktree.

### 4. Durable state and CI exits

FEATURE-MAP rows 47–48 (Module 4): `.harness/state.json`; exit 0/2/1.
Sol2 `_finish` maps every non-pass to 1. `implementer.main` and
`harness.py` agree. A CI job cannot tell escalate from crash.

### 5. Test phase is a stub of the code phase

The plan is derived, saved, and then ignored by the test implementer.
Prompt is `the_ticket.for_prompt()`. One attempt. Red-gate miss escalates
immediately. Graph Engineering on the FEATURE-MAP is "each criterion
becomes a test step and a code step." The code step is consumed. The test
step is not.

### 6. Planner flag

Still Python `plan_for`. This is the five-hour choice and it should stay
the default. Stretch is `--planner derived|sdk|deep` with fail-closed
schema. Do not let a live planner invent `kind/path/goal`.

### 7. Deep Agents fence, on paper vs on the probe

SDK SPEC is the teaching document for "how this runtime enforces scope."
DA SPEC is a restatement of the eight steps. Layer 3 lives in
`test_build_agent_fences_the_harness` against `fake_deepagents`. The
comment is correct ("without this, the default general-purpose subagent
walks around every tool list above it"). The probe is not live-shaped.

`virtual_mode` is routing. #288 already said so. Restate it in the DA SPEC
so the next port does not treat it as the fence.

### 8. Bash

SDK: no role holds Bash. Tests in `tests/test_roles.py` pin the empty list
and `disallowed_tools`. DA: `TOOLS_FOR_READER["judge"]` includes Bash;
writers get `(*READ_TOOLS, "Edit", "Write", "Bash")`; no `OVERRIDES`.
`doers.py` `CLI_COMMANDS["claude"]` includes Bash. A shell is the path
around the write hook (`sed -i` on a failing test). SDK SPEC already
says this in so many words. DA has not copied them.

## What to leave alone

- The eight-step order in `implementer.py`. Long on purpose.
- `plan_for` as the default planner.
- Folder-local copies of `gates.py`, `rubric.py`, `receipt.py`,
  `write_scope.py`, `observability.py`.
- Saturday `labs/lab2_implementer`.
- sol3 (#385, #386) and sol4.
- No `loops/` package.

## Recommended order

The same queue as the plan. Review page first so later tickets have a URL.

0. Publish this page.
1. `receipt.check` tests, then wire or strike the push gate.
2. Judge sees the diff; fixture judge can say no.
3. Isolated worktree.
4. `state.json` + `--resume` + exit 0/2/1.
5. Test-phase retry + plan in the test prompt.
6. `--planner derived|sdk|deep`.
7. DA SPEC + Layer-3 fence probe.
8. No live backend holds Bash.
9. Docs, traces, parity tests.

Copy both ports. One PR per story. Do not implement the loop in the
filing PR.

## Retrieve-and-execute

- Epic: https://github.com/RichardHightower/reliable-agentic-lab/issues/414
- Plan: https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-2-Workflow-Plan
- Repo plan: `docs/plans/2026-09-07-sol2-workflow.md`
- This review: `docs/status/sol2-implementer-review.md`
