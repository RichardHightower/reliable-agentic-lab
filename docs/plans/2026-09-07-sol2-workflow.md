---
date: 2026-09-07
slug: sol2-workflow
title: Make the sol2 implementer loop match the Module 2 slides
git_base: "cb88cbc8"
branch: docs/sol2-module-2-plan
epic: 414
wiki: Sol-2-Workflow-Plan
review: Sol-2-Implementer-Review
---

# sol2: make the implementer loop match the Module 2 slides

Parent ticket: [#414](https://github.com/RichardHightower/reliable-agentic-lab/issues/414).
Review: [Sol-2-Implementer-Review](https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-2-Implementer-Review)
(repo copy [`docs/status/sol2-implementer-review.md`](../status/sol2-implementer-review.md)).

Recommendation and queue only. **No loop code in the filing PR.** One PR per
child when a story is scheduled.

#287 / #288 made both ports real eight-step drivers. This epic makes the
classroom demo match FEATURE-MAP Module 2 and the Lab 2 speaker notes.

## The five primitives

Trigger, scope, verify, state on disk, three exits.

Sol2 has four of five. State on disk is `.harness/last-implementer.json` plus
a receipt, not a resume spine. The push gate is `receipt.check` with no hook.
The judge is asked about "this diff" and is not given one.

## What is true on `cb88cbc` (read this before changing anything)

Both folders: `solutions/sol2_implementer_deep_agents` and
`solutions/sol2_implementer_agent_sdk`. Copy, do not import.

| Claim on the slides | Code |
|---|---|
| Push gate: a `PreToolUse` hook refuses `git push` without a green receipt (FEATURE-MAP row 34, session-2 s2-30) | `receipt.check` exists in both `receipt.py`. No hook, no `git push` matcher, no test of `check()`. `write()` is tested. |
| Model judge answers "does this diff do what the ticket asked?" | `_ask_judge` in both `implementer.py` sends the ticket and the rubric report. It does not send a diff. Offline backends return `done=True`. There is no fixture that returns `done=False` through a live-shaped `judge()` method. |
| Isolated run | `implementer.run` mutates `contract.repo` in place. Classroom HOW_TO_RUN resets the CRM with `git checkout --force main && git clean -fd`. No worktree. |
| Durable state + CI exits (FEATURE-MAP rows 47–48, taught in Module 4, wanted here so Module 2 is honest) | `_finish` writes `last-implementer.json`. Process exit is `0` on pass, `1` on anything else. No `state.json`. No `--resume`. Escalate is not `2`. Crash is not distinct from escalate. |
| Test implementer reads the plan | Test phase prompt is `the_ticket.for_prompt()` only. One shot. Red-gate miss is instant escalate. Retry feedback exists only on the code phase (`_code_prompt`). |
| Graph Engineering is "derived, not generated" | `plan_for` is Python. Correct for five hours. Wiring a planner subagent is still stretch, behind a flag, fail-closed on schema. |
| No role holds `Bash` | SDK SPEC and `OVERRIDES` strip it; `GLOBAL_DENY = ["Bash"]`; tests pin it. DA `roleplan.py` still hands `Bash` to the judge and to every writer. `CliBackend` / `CLI_COMMANDS["claude"]` pass `--allowedTools ... Bash`. |
| Deep Agents Layer-3 fence | `test_build_agent_fences_the_harness` hits `fake_deepagents`. SPEC does not name the fence at SDK depth. |

Saturday `labs/lab2_implementer` is the three-function stub. Do not copy these
fences into it.

## What this epic is

1. Tell the truth on the slides, or wire the missing hook.
2. Show the judge the diff. Cover green-rubric / judge-says-no offline.
3. Stop mutating the CRM clone. Isolated worktree.
4. Durable `.harness/state.json` + `--resume`. Exit codes 0/2/1.
5. Test-phase retry. Test implementer reads `steps.jsonl`.
6. Planner-as-subagent behind a flag. Schema already enforced.
7. Deep Agents SPEC and live fence probe brought up to SDK depth.
8. Fence or drop `CliBackend` / `Bash`.
9. Docs: FEATURE-MAP, lab slides, both SPECs, implementer docstring, wiki.

## What this epic is not

- Not a rewrite of the eight-step loop.
- Not a shared `loops/` package.
- Not Saturday `labs/lab2_implementer`.
- Not sol3 (#385, #386) and not sol4.
- Not a fourth exit.

## Copy

Both ports. Do not import. Same discipline as #387 / #288.

## Hold

One PR per child when a story is scheduled. This filing is docs + tickets
only. Do not implement the loop in the filing PR. Story 0/9 (publish the
review page) is the exception: it is the wiki landing of this pack.

## Queue

Publish the review page
  → receipt.check tests + push-gate decision
  → judge sees the diff + fixture judge
  → isolated worktree
  → state.json + resume + exit 0/2/1
  → test-phase retry + plan consumption
  → planner flag
  → DA SPEC + DA fence probe
  → Bash fence
  → docs / FEATURE-MAP / wiki / parity

---

## Story 0/9: publish Sol-2-Implementer-Review on the wiki

Kind: ops. The retrieve-and-execute handle for every later story.

**Task:** Publish the review page and point Home, Lab-2, and Sidebar at it.

- Subtask: land [[Sol-2-Implementer-Review]] and [[Sol-2-Workflow-Plan]] on the wiki.
- Subtask: patch `Home.md`, `Lab-2-Ticket-Implementer.md`, `_Sidebar.md`.
- Subtask: keep repo copies at `docs/status/sol2-implementer-review.md` and
  `docs/plans/2026-09-07-sol2-workflow.md`.

Done when those two wiki URLs render the pages, not Home.

---

## Story 1/9: receipt.check tests in both ports, then wire or strike the push gate

Kind: feature.

`receipt.check` (`receipt.py`) already has one return per failure mode. Nothing
calls it. FEATURE-MAP row 34 and session-2 s2-30 promise a `PreToolUse` hook
that refuses `git push` without a green receipt. Session-2 s2-44 says "four
refusal reasons"; the function has six failure returns plus the green path.

**Task:** Tests for `receipt.check` in both ports.

Keep the branches as a checklist inside this task, not seven extra tickets.

- [ ] missing receipt
- [ ] unreadable JSON
- [ ] `report_usable` is false
- [ ] `green` is false (failed_ids in the reason)
- [ ] `tree_hash` mismatch
- [ ] source `mtime` newer than `written_at`
- [ ] green and matches this tree → `(True, ...)`

Copy the tests. Do not import.

**Task:** Wire the push gate, or strike the slides.

Either:

1. A hook (Claude Code `PreToolUse` matcher on `git push`, plus the SDK/DA
   equivalent the port actually has) that shells `receipt.check` and denies on
   a non-zero exit, **or**
2. FEATURE-MAP row 34, session-2 s2-30 / s2-44, and both SPECs stop promising
   a hook this folder does not run.

Do not do both. A hook that is not on the live path is theater.

Tests that must fail if reverted: a green receipt on a dirty tree is denied;
`git push` (or the port's push-shaped call) is denied when `check` returns
false, *or* the FEATURE-MAP row no longer claims a hook.

---

## Story 2/9: the judge sees the diff, and offline can say not done

Kind: feature.

Both `_ask_judge` implementations (`implementer.py`) prompt:

> Does this diff do what the ticket asked?

and then send `ticket.for_prompt()` plus `score.report()`. No diff. No plan.
`Backend.judge` for none/reference returns `{"done": true, ...}`. Unit tests
cover "unparseable → done=False" and "green + judge_done=False → escalate"
only by patching internals, not by a fixture backend that *says* no.

**Task:** Put the diff (and the plan summary) in the judge prompt.

Python computes the diff (`git diff` against the preexisting baseline, or
the same `changed_files` the rubric already uses). The model does not.
Include `steps.jsonl` summary so the judge can name a criterion.

**Task:** A fixture judge can say no.

Add a scripted/fixture backend whose `judge()` returns
`{"done": false, "why": "..."}`. Green rubric plus that verdict is escalate.
Keep the classroom default (`none`, `reference`) as `done=True` so
`--doer reference` still passes. Unparseable stays `done=False`.

Tests that must fail if reverted: the prompt `backend.judge` receives
contains at least one changed path from the code phase; a fixture `done=False`
after a green rubric yields `gate == escalate`.

---

## Story 3/9: run the loop in an isolated git worktree

Kind: feature.

`HOW_TO_RUN.md` currently resets the public CRM clone in place. A failed live
run and a classroom `--doer reference` fight over the same tree. Module 2
should not teach "we wrecked the clone, check it out again."

**Task:** Isolated worktree as the `repo` the loop mutates.

- Subtask: create a worktree (or a throwaway clone) from the CRM HEAD, run
  against that path, remove it on success. Leave it on escalate/crash so the
  receipt and trace are inspectable.
- Subtask: `--repo` still works. The worktree is the default classroom path,
  not a hidden second mode that nobody runs.
- Subtask: the original clone's working tree is byte-identical after
  `--doer reference` and after `--doer none`.

Do not invent a container. `git worktree add` is the isolation the slides
can name in one line.

Tests that must fail if reverted: a run against a fixture repo does not
change files outside the worktree path; the original `repo` has no
`.harness/` from that run.

---

## Story 4/9: durable state, resume, and CI exit codes

Kind: feature.

FEATURE-MAP rows 47–48 are Module 4, but the lesson is the same spine.
Sol2 already writes a trace. It does not write a resume document and it
does not speak CI.

`_finish` today: `last-implementer.json` + `receipt.write` + process exit
`0` if `gate == pass` else `1`. `harness.py` and `implementer.main` agree
on that.

**Task:** `.harness/state.json` next to the receipt.

Fields the Module 4 slides already name: `runs`, `last_gate`, `last_reason`,
`last_run_at`, `loop`. Keep `last-implementer.json` as the verbose trace.
A corrupt `state.json` is not a fresh start (fail closed, print one line,
exit 1). Same rule Module 4 teaches.

**Task:** `--resume` continues from state.

Re-enter the loop from the last unfinished phase. Do not replay a green
test phase. Do not invent a new ticket. If there is nothing to resume,
exit 1 with a reason.

**Task:** Process exits 0 / 2 / 1.

- 0 pass
- 2 escalate (red gate, judge no, budget, same signature twice)
- 1 crash (contract error, corrupt state, unhandled)

`retry` is not a process exit. It is an in-process continue. Only the
terminal gate becomes an exit code.

Tests that must fail if reverted: `main()` returns 2 on a `--doer none`
red-gate escalate; returns 0 on `--doer reference` happy path; a truncated
`state.json` does not start a new run.

---

## Story 5/9: the test implementer reads the plan and may retry

Kind: feature.

Code-phase retry is done (#288). Test phase is still one shot. The prompt
is the ticket, not the plan the planner (or `plan_for`) just wrote. This
is the Graph Engineering hole: we derive `steps.jsonl` and then hide it
from the only role that should consume the test steps.

**Task:** Test-implementer prompt includes the plan.

Every test step (`role == test_implementer`) goes into the prompt. The
code implementer still does not see test-step actions it should not write.

**Task:** Test phase may retry inside the budget.

A red-gate miss is retry, not instant escalate, until iteration budget or
stable failure (same signature twice). Empty new-ids after budget still
escalates. Scope violations still escalate immediately. Do not let the
test implementer retry by editing `app/**`.

Tests that must fail if reverted: the first test-phase `backend.run` prompt
contains a step id from `steps.jsonl`; a scripted tester that writes
nothing on turn 1 and a failing test on turn 2 gets past the red gate
when budget ≥ 2.

---

## Story 6/9: planner-as-subagent behind a flag, schema unchanged

Kind: feature.

`plan_for` stays the default. FEATURE-MAP row 28 ("Derived, not generated")
remains true for the five-hour path.

**Task:** `--planner derived|sdk|deep`. Default `derived`.

- `derived` is `plan_for`. No model.
- `sdk` / `deep` call that port's planner subagent. Python validates with
  the existing `steps.Plan` schema (`ticket` / `role` / `action` /
  `validation`). Schema miss is fail-closed: escalate, do not invent
  `kind/path/goal`, do not skip the red gate.
- Classroom `--doer none|reference` uses `derived` even if the flag is
  wrong. Live planner is for live doers.

Tests that must fail if reverted: default path never calls a planner
backend; a planner payload with `kind` instead of `role` does not become
`steps.jsonl`; `plan.validate` still runs.

---

## Story 7/9: Deep Agents SPEC and live fence probe, copied not imported

Kind: feature.

SDK SPEC already says: no Bash, `tools=[...]` plus one `PreToolUse` hook,
parent writes nothing. DA SPEC is the short eight-step restatement.
`test_build_agent_fences_the_harness` is Layer 3 and it is mocked
(`fake_deepagents`). The comment in `tests/test_roles.py` is the lesson:
without it, the default general-purpose subagent walks around every tool
list above it.

**Task:** DA SPEC names the fence at SDK depth.

Bash, tool lists replace parent, judge is `read_file` only, `virtual_mode`
is routing not a security boundary, orchestrator `permissions` are deny-all
writes, general-purpose subagent is off. Copy the words. Do not import the
file.

**Task:** Layer-3 fence probe that fails if the mock is lying.

A test (SDK-free, no key) that instantiates the objects `create_deep_agent`
would receive and asserts: general-purpose disabled, `write_file` /
`execute` excluded on the parent, judge tools `== [read_file]`, last
permission deny. If Deep Agents is installed, run against the real types;
if not, skip the real-type assertion and keep the fake. A skip is not a
pass on CI for the fake path; the fake path already exists.

Tests that must fail if reverted: enabling the general-purpose subagent
in `build_agent` fails a test; judge tools growing a write tool fails a
test.

---

## Story 8/9: no live backend holds Bash

Kind: feature.

SDK already fences this. DA `roleplan.plan` still puts `Bash` on the judge
and on every writer. `doers.CLI_COMMANDS["claude"]` allows Bash. `CliBackend`
is a live backend the `--doer` flag will construct.

**Task:** Copy SDK `OVERRIDES` into DA `roleplan.py`.

Implementer cast holds no Bash. Table still prints judge writes `no`.

**Task:** Fence or drop `CliBackend` for the implementer ports.

Either delete `CliBackend` from these two folders, or make it refuse to
start with Bash in the tool list, or stop advertising `claude|codex|grok|
opencode` on `implementer.main --doer`. `--doer deep` and `--doer sdk`
must not hold Bash. A shell is the path around the write hook.

Tests that must fail if reverted: DA
`[name for name, role in cast.items() if "Bash" in role.tools] == []`
(same assertion SDK already has); constructing `CliBackend("claude")` in
this folder either fails or the command line it would run has no Bash.

---

## Story 9/9: docs, traces, and parity tests

Kind: ops. Last. Depends on 1–8 being decided, even if some children chose
"strike the slide" instead of "wire it."

**Task:** Docs match the code that shipped.

FEATURE-MAP rows 32–35 and 47–48, both `SPEC.md` / `DESIGN_DOC.md` /
`HOW_TO_RUN.md`, SDK `E2E_PLAN.md` / `TEST_PLAN.md`, both sol2 slide decks,
implementer module docstring (still cites `task loop:implementer`), wiki
[[Lab-2-Ticket-Implementer]], [[Sol-2-Implementer-Review]], this plan.

**Task:** Parity tests across both ports.

Pin: judge prompt contains a changed path; `main()` exit 0/2/1; `state.json`
keys; no `from loops` / `from solutions`; no Bash on the implementer cast;
`receipt.check` branches. Group by behavior, not a checksum (same lesson as
#278).

**Task:** Optional live T001 traces.

`--doer deep` and `--doer sdk` traces under `docs/status/` or a checked-in
`.harness` example. Not a merge blocker. Honest escalate is a pass.

---

## Constraints that do not move

- No `loops/` package. Duplicate the files.
- Each folder is standalone. An attendee copies one folder somewhere else
  and it runs.
- Saturday Lab 2 stays `labs/lab2_implementer`. Three functions.
- Python owns `gates.decide`. The model does not pick Pass / Retry / Escalate.
- Both ports. Same behavior. Different maker.
- Do not mix sol3 #385 / #386.
- Do not implement the loop in the filing PR.

## Retrieve-and-execute

Epic: [#414](https://github.com/RichardHightower/reliable-agentic-lab/issues/414)
Plan (this file): `docs/plans/2026-09-07-sol2-workflow.md`
Wiki: https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-2-Workflow-Plan
Review: https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-2-Implementer-Review
