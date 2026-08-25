# Session 1 notes. System Architecture.

Open 10 minutes. Module 1 is 45 minutes. Then a break.
Artifact they keep: a working autonomous loop on their machine.

Do not reteach 20 August. Point back. Then type.
Do not build the CRM. They clone it.

Images match `slides.md`. If a PNG is missing, describe the prompt and keep moving.

---

## s1-01. Title

You are here to engineer a loop, not to collect prompts.

Session 1 is System Architecture, the foundation. Eventbrite title. Locked. 45 minutes plus the 10 minute open.

Say the time. 10:00 Central. 11:00 Eastern. We end this block before the first break.

---

## s1-02. Four artifacts. Image `four-artifacts.png`

Promise the four things they take home. Do not add a fifth.

1. A running loop in the first hour.
2. A reusable evaluation harness.
3. One live research assistant over Model Context Protocol (MCP).
4. A production architecture they can hand to an org.

The picture is four physical objects on a bench. Not four vendor logos.

---

## s1-03. Loop Engineering. Mermaid full width.

Loop Engineering is the work of making an agent repeatable.

The figure is the whole slide. Five boxes. Trigger. Action. Verify. Memory. Human.

Verify is the stage that separates self-correction from a script that happens to call a model. That sentence is the thesis of the day. Repeat it in Session 2.

---

## s1-04. Prompting dies under volume. Image `prompting-volume.png`

One clever prompt works once. Ten tickets a day, it drifts. A hundred, nobody remembers what good looked like.

The bottleneck is not the model. It is you. That is the Loop Engineering claim. Do not spend five minutes defending it. Point at the picture of the engineer drowning in identical chats, then move.

---

## s1-05. Point back to 20 August. Image `second-brain-point-back.png`

If they were in the free hour, they already have the mental model. The repo is the second brain. The event log is the source of truth.

We do not rebuild ContextPacks, wiki_ticket_sdd, or graph runtime as a lecture. That hour stopped short of graders. Graders are why they paid.

---

## s1-06. TicketCloser on a CRM. Image `crm-not-tickets.png`

The object is a small customer relationship management (CRM) app. Customers. Sales tasks. Docker. SQLite. Thin pages.

It is not a ticketing app. Say that out loud. Too meta. They would spend the morning arguing about tickets about tickets.

First graded ticket: add a due date on sales tasks. Vague on purpose. Field type, timezone, required or optional, overdue filter. The draft does not decide those. The ready contract does.

---

## s1-07. Three loops. You build one live. Mermaid.

Name all three so the day has a map.

1. Ticket Enhancer. Draft to ready. Session 3.
2. Ticket Implementer. Ready to pull request. This hour.
3. Broken PR Fixer. Failing PR to mergeable. Session 4 pattern.

They do not build all three from scratch. If someone wants to, tell them the clock will not.

---

## s1-08. Clock and fall-behind.

25 minutes of typing inside this module. Anatomy first, then type.

Stuck: stop typing. Watch you finish. Copy `solutions/m1-implementer`. Continue.

Say it now so it is not a humiliation later.

---

## s1-09. Section card. Anatomy.

Triggers. Actions. Verify. Memory. Human oversight. Five words. Then one slide each.

---

## s1-10. The five-part figure. Mermaid on top, one line under.

Trigger is ready ticket T001. Action is five CRM files. Verify is hidden pytest. Memory is the work copy and the PR body. Human merges.

If they cannot point at verify after the lab, they built a generator.

---

## s1-11. Trigger. Image `trigger-ticket.png`

Something outside the model starts the work. Ours is a file. `solutions/tickets/T001-due-dates.ready.md`.

Not a chat. Chat is a courtesy, not a trigger. Production loops start from tickets, cron, or PR events. Session 4 will swap the trigger. The rest of the graph stays.

If the trigger is the vague draft, the loop invents a required local-time field and the grader stays red. That is the enhancer's job. Not this hour.

---

## s1-12. Action. Image `action-scoped-files.png`

Smallest change that can pass. `dates.py`, `models.py`, `main.py`, two templates.

Show the red stamp on graders and tickets. Action does not get to rewrite the test. That is how agents cheat.

---

## s1-13. Verify. Image `verify-pytest.png`

A check the agent did not write. Hidden tests for model, API, form, `due_before`, `overdue`. Null due dates stay valid. No hardcoded customer names.

"Looks good to me" is not verify. LLM-as-judge can sit on the PR description later. It does not replace pytest on this contract.

---

## s1-14. Memory. Image `memory-not-chat.png`

Chat evaporates. The work copy is memory. The PR body is memory.

Point back to 20 August. One sentence. Then: we are not packing a ContextPack in this lab. We are putting the result in git where Session 2 can score it.

---

## s1-15. Human oversight. Image `human-merges.png`

The loop opens a PR. It does not merge. A human still owns production.

Oversight is a box on the graph. If you skip the box, you did not forget a courtesy. You changed the architecture.

---

## s1-16. Ready contract. Mermaid.

Read two bullets off the ready ticket. Optional UTC ISO `due_date`. Overdue means open and before today UTC.

This is spec-driven development as a file, not as a vibe. Session 2 will load those bullets as a rubric. Plant that now.

---

## s1-17. Lab start.

They clone. They do not scaffold.

Known-good CRM already passes the hidden grader. The implementer loop copies `starter_crm`, applies the due-date files, writes `PR.md`.

You run `python solutions/m1-implementer/loop.py` on the projector first so the room hears a pass.

---

## s1-18. Fail then pass. Image `starter-crm-fail.png`

Walk the starter. Customers exist. Tasks exist. Due column is a hole.

After the loop the form has `name="due_date"`. The list filters. Seed rows are still valid with null. That last part is how you know they did not require a backfill.

---

## s1-19. Name the five parts again.

They just ran it. Make them say trigger, action, verify, memory, human. Cold call if the room is shy. Two people. Then stop.

---

## s1-20. Where one-shot breaks. Image `oneshot-breaks.png`

Three panels. No contract. No stop. Context rot.

This is the bridge, not a new lecture. You are selling Session 2. Do not start Maker and Checker until after the break.

---

## s1-21. Break.

Fifteen minutes. Next is the center of gravity. Do not cut it.
