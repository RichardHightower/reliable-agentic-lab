# Session 4 notes. Production Architecture.

35 minutes for the module, then 10 minutes to close.
Artifact they keep: a production architecture they can hand to their team.

Energy is lowest here. Keep it moving. The lab is 18 minutes, not 25.

**Clock checkpoints.** Slide s4-07 at 11 minutes. Slide s4-08 at 29 minutes.
Slide s4-12 at 35 minutes.

---

## s4-01. Title

Say the shape of the hour: build for 11 minutes, type for 18, land for 6, then
close.

---

## s4-02. What changes when you walk away

Four items. The graph is not one of them.

The last line is the hook for the whole hour: if you cannot read the last score,
you cannot debug at 2 a.m.

---

## s4-03. MAST

The headline is the takeaway: most agent failures are not model failures.

41.8% system design, 36.9% handoff, 21.3% verification. From 1,600 traces across
7 frameworks.

Say the closing line: every one of those three is something you build, not
something you buy. That justifies the whole day retroactively.

---

## s4-04. Durable state

Five fields. Read them.

The point is small and concrete: it survives the process. A chat transcript does
not.

---

## s4-05. Observability

A trace is not a log file. Name what a span carries.

Then three numbers per run: steps, loop count, cost per task. Those three catch
runaway loops before the invoice does.

Local JSON counts as production if it is the record you actually open.

---

## s4-06. Local and remote gates

Callback to the push gate they hit in Module 2.

Read the exit codes. 0 pass, 2 escalate, 1 crash. CI needs a number, not a
paragraph.

Closing line: same rule in both places, or the remote one is theater.

**You should be at 11 minutes here.**

---

## s4-07. Lab 4

Say the stash line out loud before anyone types. The target repo still holds
Module 2's work, and `git checkout broken-pr` refuses rather than deleting it.
That refusal is on brand, but it costs 30 seconds if you let them find it.

`--branch broken-pr` is what makes this real: the fixer
starts from a branch with one genuinely failing test. Point it at a green
branch and it reports a pass and proves nothing, which is the same shape as
the red gate in Module 2.

The second command is the unattended run.

`loop.py`. Two functions. The line to repeat while you walk the room: giving up
is allowed, giving up silently is the bug.

18 minutes. Call time at 10 and at 5 remaining.

---

## s4-08. Why the receipt exists

This is the payoff for the receipt work in Module 2. Do not rush it.

A model that may both act and verify can produce plausible false evidence.
Invented test passes. File edits that never happened.

Then the sharp version: that is a wrong judgment about the state of its own
output, and a self-check cannot catch it by construction.

**You should be at 29 minutes here.**

---

## s4-09. Swap the object

Point at the two subgraphs. Keep the left one, replace the right one.

Say it plainly: four modules, one graph, four objects, on purpose.

---

## s4-10. Seven loops named

One minute. Name them, do not build them.

If someone asks for the list in writing, point at the repo. Do not read seven
items off a slide.

---

## s4-11. The slow failure

The one nobody plans for. Passes every demo, earns trust, degrades over months
with nothing visibly breaking.

The fix is a cadence, not a tool. Weekly evaluation, not quarterly. A 2% weekly
drop is invisible in a week and catastrophic over a quarter.

**You should be at 35 minutes here.**

---

## s4-12. Section. Close

A breath. Zero minutes.

---

## s4-13. What you take home

Four artifacts, one per module. Check them off out loud.

Then the claim they will test on Monday: all four run from a clean clone with one
`task setup`.

---

## s4-14. Where everything lives

Point at the tree. Say that each `solutions/` folder is standalone, so they
already take this home. There is no shared engine to learn.
at their repo.

Name the done branches once more for anyone who fell behind.

---

## s4-15. Monday

Five steps, in order. The order is the advice.

Step 5 is the one people skip: arm the push gate on day one, while the loop is
still small enough that the refusals are cheap.

---

## s4-16. Questions

Four minutes. Hold the last line for the end.

The loop is the product. The prompt is not.

## Agent SDK unattended

query(), not ClaudeSDKClient. Nobody is chatting.
PreToolUse is write scope. Merge is never a tool.
Issue #120 is the takehome port.
