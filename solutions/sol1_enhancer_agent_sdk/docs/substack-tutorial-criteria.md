# Criteria: Substack tutorial *Python Owns the Loop*

Grade `docs/substack-python-owns-the-loop.md` as a **loop-engineering tutorial** a stranger can read and run.

The previous draft failed as *writing* even when it passed a rubric. It cloned the *structure* of an old CDI AOP article (ATM, Recap./Next. labels, "victory lap", "second interceptor"). The author pointed at those pieces as **voice**, not as a template to copy.

## Voice to match (style, not spine)

**Substack manifesto:** [*The Loop Is the Product*](https://rickhigh.substack.com/p/the-loop-is-the-product)

- Title, subtitle, cover, italic dek
- Thesis in the first screen, then teach
- Pull quotes that restated the thesis
- Short headers that name a concept
- Turbine / governor used once, then the work
- "When this thing is wrong, who is allowed to say so?"
- You-address. First person for something lived. No TED filler.

**Tutorial rhythm:** [*Remembering Is Not the Same as Knowing*](https://spillwave.com/guides/crewai/part-06-memory-and-knowledge/)

- Emotional hook in the first screen
- **In this article** as a one-paragraph syllabus
- For each idea: say what we are about to show, show a listing or figure, describe the marked lines, then move on in prose (not a **Recap.** / **Next.** stamp)
- Named listings. Load-bearing lines carry `# ①`. Notes under the listing use those numbers
- Introduce a figure, show it, then say what it proved
- **Do this today** (five bullets) then a side-by-side recap

The DZone CDI piece is the same *teaching habit* (full listings, naive contrast, run it). Do **not** import ATM, `beans.xml`, interceptors, or "victory lap" into this article.

## Required outline (the author's)

A missing beat is a hard fail on Teachability.

1. **Intro.** Title, subtitle, cover, hook, In this article. What we will teach. What we will not (not a prompt cookbook, not a workshop recap).
2. **Concepts.** Loop engineering vs harness engineering in plain English.
3. **Loop engineering this article covers.** Five nodes (trigger, action, verify, memory, exit). Four properties of one iteration (figure). Inner ReAct vs outer control (figure). Failures: context rot, tool storms, false completeness, stable failure. Exit the model cannot waive.
4. **Overview of the app.** Ticket enhancer. GitHub inbox. Cast: Python orchestrator, doer (maker), judge (checker). Architecture figure. The files that matter.
5. **Step-by-step walkthrough of the app.** What one poll does, in order a reader can follow. Workflow and sequence figures. Exact `LGTM`. Candidate proper subset. `passed` / `waiting` / `escalated`.
6. **Code listings + explanation.** Named listings from this folder. After each listing: how the code works, which concept it implements. Circled line notes.
7. **How the code demonstrates loop engineering and harness engineering.** Walk the five nodes only through listings already shown. Then harness: maker/checker, fences, rubric, gates, budgets, tests.
8. **Run it.** Commands from `HOW_TO_RUN.md` and `.agents/skills/test-sol1-ticket-enhancer/SKILL.md`. Then **Do this today** and a closer.

A short *wrong* `while` sketch may appear under concepts. It is not a required "naive ATM" chapter.

## Hard fails

1. A reader can run from the article: clone (or `cd` into) `solutions/sol1_enhancer_agent_sdk`, `task setup`, `task table`, one poll, exact `LGTM`. Commands match `HOW_TO_RUN.md` and the e2e skill (`task poll-forever --`, reset vs create vs poll).
2. Every named loop/harness concept is defined in plain English before it is used as jargon.
3. Every concept is shown in a real excerpt with path. Line-accurate enough to find in the file. Elision marked `# ...`.
4. No seminar logistics as assumed vocabulary: Saturday, Packt, Eventbrite, RICK40, RKC, PKC, AGER, SAC, WikiTicket, "second brain". No workshop pitch.
5. Zero em dashes. No sentence starts with So, That, Thus, or Hence.
6. Figures are existing `substack-images/*_imagen.png` plus `cover.jpg`. No raw Mermaid/PlantUML as the published figure. No `ager-sol1-enhancer_imagen.png`. Each figure is introduced, shown, taught.
7. Named listings with `# ①` on load-bearing lines and notes that use those numbers.
8. The article teaches, it does not stamp **Recap.** / **Next.** on every heading. Natural transitions, like the CrewAI guide.
9. No CDI-import: AutomatedTellerMachine, AtmMain, `beans.xml`, "victory lap", "second interceptor" as the organizing metaphor.
10. Honesty: `needs-human`, hung dump `.harness/last-doer-T<id>.md`, fail-open `{}` hook, proper-subset replace, bug vs feature rubric.
11. Open: title, subtitle, cover, hook, In this article. Close: Do this today, then a five-node recap, then a closer a stranger would share.
12. Voice is the manifesto + CrewAI guide, not a design-doc table marathon and not a pastiche of a 2011 DZone article.

## Axes (0–5, pass: no hard fail, no axis below 4)

| Axis | 5 looks like |
| --- | --- |
| Teachability | Author outline complete. Concepts, then app, then walkthrough, then listings that explain the walkthrough. |
| Line notes | ① ② ③ on load-bearing lines; notes consume them |
| Concept-to-code | Every named concept has a listing |
| Runnable path | HOW_TO_RUN + e2e skill, no drift |
| Substack shape | Dek, hook, pull quotes, figures, closer. Reads like Rick, not like a filled rubric |
| Honesty | Failure paths taught |

## Concepts that must be defined, then shown

Loop: production loop, five nodes, four properties, ReAct inner vs outer control, pass/retry/escalate, signature / stable failure, exact `LGTM`, proper subset.

Harness: role table, maker/checker, write scope, two fences (`NO_WRITE` + `PreToolUse`, empty `{}` fails open), `check_fields` `ready`, `check_stop`, adapter cost / 180s / hung dump, tests pin the deny envelope.

## Runnable path

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab/solutions/sol1_enhancer_agent_sdk
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
```

Seeds: T001 feature due dates; T900 bug may fail closed; T901 UI wireframe; T902 CSV export.
