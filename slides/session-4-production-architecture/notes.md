# Session 4 notes. Production Architecture.

35 minutes. Then 10 minutes close.
Artifact they keep: a production-ready architecture.

Same stack. Unattended. If the room is late, the fixer is a diagram and a folder, not a live build. The Actions runner still ships.

Images match `slides.md`. Reuse `four-artifacts.png` from Session 1 on the close.

---

## s4-01. Title

Eventbrite name. Production Architecture, the capstone.

Tell them the graph does not get a new personality. The human leaves. That is the only new requirement.

---

## s4-02. What changes when you stand up. Image `human-leaves.png`

Empty chair. Factory still ticks.

Trigger changes: cron, pull request, ticket ready. Not a keystroke.

State must live on disk. Chat will not be there in the morning. That is the Session Illusion article, in one picture.

If they cannot read the last score, they cannot debug at 2am. Say 2am. It lands.

---

## s4-03. Durable state. Mermaid.

Four fields. Ticket. Branch. Trace id. Last score.

That is enough to resume. Do not invent a database for Saturday.

Actions fires the runner. Runner writes `state.json` and traces. Human appears only on escalate.

---

## s4-04. Observability at 2am. Image `observability-2am.png`

A printout with `gate: escalate` and failed node ids. A mug. A lamp.

Langfuse is allowed. A dashboard nobody opens is decoration. Local JSON that they actually read is production.

---

## s4-05. Actions triggers. Image `actions-trigger.png`

Three pistols. `workflow_dispatch`, `pull_request`, weekday cron.

They all fire the same runner. Saturday you use dispatch. You do not wait for 15:00 UTC cron while people watch.

GitHub Actions is already on the event page as a prereq. Do not teach YAML from zero. Open the file. Fire it.

---

## s4-06. PR Fixer. Mermaid on top.

Failing PR in. Tests or review findings. Mergeable out. Human still merges.

This is the production pattern from the locked three loops. Live build only if the room is on time. Otherwise the mermaid plus `solutions/m2-harness/loops/fixer` as a pointer is honest.

Do not start a second product here.

---

## s4-07. Lab.

Run m2 unattended. Run m3 unattended. Cat state.json.

Then dispatch the workflow if the network is kind. If Actions is slow, the local runner is the lab. The YAML is the take-home.

---

## s4-08. Read state.json. Image `state-json.png`

Read `human: false` out loud. That is the slide.

`last_score.passed` is whether they go back to bed.

The file is gitignored. Upload it as an artifact. That is the production record. Committing secrets-adjacent run output is how people get sloppy.

---

## s4-09. Swap the object. Mermaid.

Keep orchestrator, Maker, Checker, gate.

Swap their tickets, their trigger, their grader.

This is how the CRM does not follow them home as a product. The graph does.

---

## s4-10. Seven loops, named not built. Image `seven-loops-named.png`

Daily triage. PR babysitter. CI sweeper. Name a few. Stamp NOT TODAY.

That list is in the Loop Engineering article they can read on the plane. Building seven labs would have broken the outline. Denim bought four modules.

---

## s4-11. Close section card.

Ten minutes. Q and A. Do not start a new demo.

---

## s4-12. Four artifacts again. Reuse `four-artifacts.png`.

Same bench as the morning. Now with checks. They can feel the day.

---

## s4-13. Folders, not branches.

Point at `solutions/`. Labs are next, not old `done-m2` branches.

Fall-behind was "copy the solution folder." Say it once more so the recording has it.

---

## s4-14. Monday. Image `adapt-to-org.png`

One backlog object. A contract that can fail. Maker and Checker before MCP. State and a budget on a trigger they already have.

If they try to adopt all four artifacts on five teams this week, they will adopt none.

---

## s4-15. Questions.

The loop is the product. The prompt is not.

If they ask what to cut: do not cut Session 2.
If they ask what they take home: the four artifacts, in order.
If they ask when: you already told them. Do not reopen the clock.
