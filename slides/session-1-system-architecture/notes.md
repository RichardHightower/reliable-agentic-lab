# Session 1 notes. System Architecture.

Open is 10 minutes. Module 1 is 45. Then the first break.
Artifact they keep: a working autonomous loop on their machine.

Do not reteach 20 August. Point back, then type.
Do not build the CRM. They clone it with `task setup`.

Images match `slides.md`. If a PNG or JPG is missing, the mermaid block is the figure.
Run `python scripts/build_slides.py` before Marp so mermaid becomes SVG.

**Clock checkpoints.** Slide s1-14 at 10 minutes. Slide s1-35 at 25 minutes.
Slide s1-39 at 50 minutes.

Expanded from the original 19-slide outline to 44 slides. Same narrative.
Same lab. More architecture, more evidence, more failure modes.

Diagram coverage, Session 1: 21 mermaid figures on 38 substantive slides (55%).
PlantUML source for the same architecture lives in `slides/diagrams/plantuml/`.

---

## s1-01. title

You are here to engineer a loop, not to collect prompts.
Say the time out loud. 10:00 Central, 11:00 Eastern.

## s1-03. Four artifacts

Promise exactly four things. Do not add a fifth.

## s1-05. Prompting dies under volume

Ask the room: who has a prompt that worked brilliantly once and never again?
Hands go up. Move on.

## s1-07. A loop is a state machine

Read the four items slowly. Say the last one twice. The model does not
enforce its own transition, and that is the whole workshop.

## s1-09. AlphaCodium

Give them one number they can quote to their manager: 19 to 44 on pass@5,
same model, different flow. Do not oversell replication.

## s1-12. Two repos

The engine never imports the CRM. That is what makes it point at their
repo on Monday.

## s1-13. The clock

Say the fall-behind rule now. Copying `solutions/sol1_enhancer/.claude/`
puts a working enhancer in their tree.

**You should be at 10 minutes here.**

## s1-15. Five parts

Point at Verify.

## s1-18. Write scope

An agent can argue past an instruction, and cannot argue past a tool it
was never given.

## s1-20. Verify

The judge reports. It does not fix.

## s1-23. Three exits

pass, retry, escalate. The forgotten exit is stable failure.

## s1-25. Lost in the middle

More than 30% accuracy drop when the fact sits in the middle.
Big output goes to a file. A short summary comes back.

## s1-27. Human oversight

Today LGTM. In Module 2 a pull request. Never merge.

## s1-30. Four objects

This is the map for the whole day. Spend the full two minutes.

## s1-37. Lab

Walk the room. Do not reteach the architecture. Point at the trace.

## s1-38. The interesting run is the one that stops

If they only remember one line from the lab, this is it.

## s1-43. Break

Module 2 is the one that does not get cut.
