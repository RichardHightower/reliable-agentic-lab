# Criteria: Substack tutorial *The Second Runtime*

Grade `docs/substack-the-second-runtime.md` as **part 2** of the loop-engineering series. Part 1 is `solutions/sol1_enhancer_agent_sdk/docs/substack-python-owns-the-loop.md`.

Part 2 has a different job from part 1. Part 1 taught the five nodes on a program. Part 2 puts the same loop on a second runtime and reports what that move proved and what it broke. A reader who never read part 1 must still be able to run this program. A reader who did read part 1 must not be made to sit through the five nodes again.

## The thesis this article must land

A harness you have only ever run on one runtime is a claim, not a fence. Porting the loop to LangChain Deep Agents is the test. The rubric, the red gate, the contract, and the write scope survived the move. The fences, the verdict shape, the result reader, and the exits belong to the runtime and were rewritten.

## Scope rule for this part

Teach concepts. Do not publish defects. The loop's own failure paths stay in, because escalation, timeouts, budgets, and `needs-human` are loop engineering. Do not name a bug in the lab's own code, do not say a test asserted the wrong thing, and do not call a design difference a regression. A port that chooses three exits instead of four made a choice, and the article compares the two choices rather than grading one.

## Voice to match

Same as part 1. Load `references/voice.md`, `references/traps.md`, and the two pre-AI samples. Grade every punch against the 2011/2012 corpus.

## Required outline

A missing beat is a hard fail on Teachability.

1. **Intro.** Title, subtitle, cover, dek, hook, **In this article**. Say plainly this is part 2 and what part 1 covered.
2. **A five-minute review of part 1.** A review, not a re-teach. One figure recaps the five nodes. Every carried word gets one sentence: loop engineering, harness engineering, production loop, node, agent, worker, subagent, isolated context, bounded and unbounded authority, rubric, proper subset, exact `LGTM`. Link part 1 for the full walk. Define only the words part 2 adds: runtime, port, harness profile, structured output, virtual mode, composite backend, declarative permission rule.
3. **What a port actually tests.** The claim under test. Three runtimes, one table.
4. **Overview.** The same enhancer object, the second runtime. Cast unchanged. What moved and what did not, with a real diff count.
5. **How this runtime says no.** Three fences, one listing each. The general-purpose subagent hole.
6. **What did not have to change.** The rubric listing, byte identical.
7. **What did change, and be honest about it.** Three exits, not four. The signature exit is gone. Say what that costs.
8. **Two frameworks, side by side.** The section this part exists for. A figure separating loop-owned from runtime-owned. A comparison table across at least eight concerns. A paragraph on each framework's temperament, naming a strength and a cost for both. Three practical readings a reader can apply to their own harness.
9. **Reading an answer out of a graph.** The adapter listing. Three tempting versions of the function are wrong, and the walk is written against all three.
10. **The tests.** No runtime, no key, no clone. Real numbers.
11. **Run it.** Prerequisites, commands from `HOW_TO_RUN.md`, validation, teardown.
12. **Do this today** (five bullets).
13. Five-node recap table (node vs file), then closer, then Sources, then Glossary.

## Hard fails

1. A reader can run from the article: `cd solutions/sol1_enhancer_deep_agents`, `task setup`, `task table`, `task checks`, `task test`, one poll, exact `LGTM`, `task reset-test-tickets`. Every command matches `HOW_TO_RUN.md` and `Taskfile.yml`.
2. Part 2 does not re-teach the five nodes, the four properties, ReAct, AlphaCodium, or Lost in the Middle as if they were new. It names them and links part 1.
3. Every claim about "the loop did not change" carries a real number a reader can reproduce with `diff`. No hand-waving. `check_fields.py` is 0 lines different. `roleplan.py` is 2 real lines plus a docstring. `enhancer.py` is not identical, and the article says so.
4. The exit difference is stated as a design choice, not a fault. Part 1 computes four stops. This port computes three. Both get a fair paragraph, and the shared property is named: every exit is computed outside the model.
5. Zero em dashes. No sentence starts with So, That, Thus, Hence, or Here. No sentence starts with a bare filename, command, or identifier.
6. No seminar logistics as vocabulary: Saturday, Packt, Eventbrite, RICK40, RKC, PKC, AGER, SAC, WikiTicket, "second brain".
7. Named listings with `# ①` on load-bearing lines, notes one number per line. Long listings get tell, show, tell.
8. The negative listing is labeled a negative example in its title and its intro, and its bad lines carry `# ① WRONG!`.
9. Honesty: the general-purpose subagent hole, the skill that was mounted and pasted at the same time, the self-answering comment bug that is still open on the sibling port, the two shipped ways of misreading a graph result.
10. `task` is go-task from this folder's `Taskfile.yml`. It is introduced in Run it, not in the architecture walk. It is never capitalized as `Task`.
11. Figures: rendered PNGs, not raw Mermaid or PlantUML. Sources live in `docs/diagrams/*.mmd`, rendered by imagen-diagrams with theme `agent-control` and density `article` so they match part 1's visual language. Every figure is introduced, shown, and taught in concept names rather than drawing furniture. Alt text describes the picture, the paragraph does not.
12. Terminal output is real, captured from this program. No invented run.

## Axes (0 to 5, pass: no hard fail, no axis below 4)

| Axis | 5 looks like |
| --- | --- |
| Teachability | Outline complete. A part 1 reader learns something new on every heading. |
| Line notes | ① ② ③ on load-bearing lines, notes consume them, one per line |
| Concept-to-code | Every claim about portability has a listing and a reproducible number |
| Runnable path | HOW_TO_RUN and Taskfile, no drift |
| Substack shape | Dek, hook, pull quotes, closer. Reads like Rick, not a port changelog |
| Honesty | The dropped exit, the open bug, and the two shipped mistakes are all in |
| Series fit | Reviews part 1 in one section and links it for detail. Forward-maps part 3 |
| Comparison | Both frameworks get a strength and a cost. Neither is declared the winner. A reader can apply the axes to a framework not covered |

## Concepts part 2 adds, and must define once

Runtime. Port. Harness profile. General-purpose subagent. Structured output / `response_format`. Virtual mode. Composite backend. Declarative permission rule. Comment marker.

Concepts carried from part 1, named but not re-taught: production loop, five nodes, worker, agent, subagent, isolated context, bounded authority, maker and checker, proper subset, exact `LGTM`, `needs-human`, failure signature.

## Runnable path

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab/solutions/sol1_enhancer_deep_agents
cp config.json.example config.json
task setup
task clone
task table    # judge writes = no
task checks
task test
task reset-test-tickets
task create-test-tickets
task run --
# exact LGTM on green tickets
task run --
task reset-test-tickets
```

Seeds: T001 feature due dates; T900 bug empty-query search; T901 UI wireframe; T902 feature CSV export.
