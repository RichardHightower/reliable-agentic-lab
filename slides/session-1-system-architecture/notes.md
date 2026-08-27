# Session 1 notes. System Architecture.

Open is 10 minutes. Module 1 is 45. Then the first break.
Artifact they keep: a working autonomous loop on their machine.

Do not reteach 20 August. Point back, then type.
Do not build the CRM. They clone it with `task setup`.

Images match `slides.md`. If a PNG is missing, read the prompt aloud and move on.

**Clock checkpoints.** Slide s1-08 at 10 minutes. Slide s1-16 at 25 minutes.
Slide s1-17 at 50 minutes.

---

## S1-01. title

You are here to engineer a loop, not to collect prompts.

Say the time out loud. 10:00 Central, 11:00 Eastern. This block ends before the
first break.

---

## s1-02. Four artifacts

Promise exactly four things. Do not add a fifth.

Say that all four run from a clean clone with one command. That promise is the
one they will check.

---

## s1-03. Prompting dies under volume

The failure is not that the model is bad. It is that you are the bottleneck.

Ask the room: who has a prompt that worked brilliantly once and never again?
Hands go up. Move on. Do not collect stories.

---

## s1-04. A loop is not "call the model until it says done"

This is the definition slide. Read the four items slowly.

Explicit state, bounded authority, observable evidence, an externally enforced
transition. Say the last one twice. The model does not enforce its own
transition, and that is the whole workshop.

---

## s1-05. AlphaCodium

Give them one number they can quote to their manager: 19 to 44 on pass@5, same
model, different flow.

If someone asks whether it replicates: say the general result, that test-based
iteration beats single-shot for code, is broad. The exact number is one paper on
one benchmark. Do not oversell it.

---

## s1-06. The object is a CRM in another repo

Two sentences on why a ticketing app would be too meta.

The important line is the third one: the engine never imports the CRM. That is
what makes it point at their repo on Monday.

---

## s1-07. The clock

Say the fall-behind rule now, before anyone needs it. Nobody is graded.

Copying `solutions/sol1_enhancer/.claude/` in puts a working enhancer in
their tree. Say it once before they need it.

**You should be at 10 minutes here.** If you are over, cut s1-05 next time.

---

## s1-08. Section. Anatomy of an agent loop

Just a breath. Zero minutes.

---

## s1-09. The five parts

Point at Verify. Say the line: this is what separates a loop from a script that
calls a model.

Everything else on the diagram is plumbing they already know.

---

## S1-10. trigger

A trigger is outside the model. Today it is a file. In production it is a hook.

The last bullet is the one that costs money: a trigger that fires when nothing
changed burns budget for no work. Module 4 comes back to it.

---

## s1-11. Action, inside a scope you declared

This is the first appearance of write scope. Set it up here so Module 2 can land
the punch.

Say the closing line as written: an agent can argue past an instruction, and
cannot argue past a tool it was never given.

---

## S1-12. verify

The judge reports. It does not fix.

If someone asks why the judge cannot just make the small fix it found: answer
that a thing which can both act and grade will eventually grade its own work
green. Module 4 has the evidence. Do not spend it here.

---

## S1-13. memory

Give them the lost-in-the-middle number: more than 30% accuracy drop when the
fact sits in the middle.

Then the practical rule: big output goes to a file, a short summary comes back.
That rule is why the planner is its own subagent in Module 2.

---

## s1-14. Human oversight

Oversight is a step you build, not a hope you hold.

Today the loop rewrites a ticket and a human accepts it. In Module 2 it opens a
pull request and still does not merge.

---

## s1-15. Three parts, four objects

This is the map for the whole day. Spend the full two minutes.

Say plainly: you learn this graph once, and then we change only the object. If
they get nothing else, they should leave with this table.

**You should be at 25 minutes here.**

---

## s1-16. Lab 1

Read the two commands. The first one escalates on purpose. Tell them that before
they run it, or half the room will think they broke it.

Walk the room. The two functions are small. The common stall is `decide_next`,
because people forget the stable-failure exit.

25 minutes. Call time at 15 and at 5 remaining.

---

## s1-17. Read the trace

Put the escalate trace on the screen and read it out loud.

The point: the interesting run is the one that stops. An iteration that burns
tokens and reproduces the identical failure is not progress.

**You should be at 50 minutes here.**

---

## s1-18. Where this breaks at scale

Four failures, four fixes, all four fixes in Module 2. Do not fix any of them
now.

This is the bridge. Keep it to two minutes.

---

## S1-19. break

Say the length: 15 minutes. Say what is next: the harness.

Say that Module 2 is the one that does not get cut. They will remember that you
said it, and it buys you the room's patience later.
