# Post-handoff verification: Python Owns the Loop

## Verdict

PASS. The article now works as the Module 1 companion as well as a runnable tutorial. It adds the missing role graph, flow evidence, durable-context lesson, Human-versus-exit mapping, four-job forward map, skill-form versus Python-form contrast, and a precise live-run record. The stale workflow, sequence, and two-fences rasters were regenerated from their corrected Mermaid sources; their labels and transitions now match the code.

## Evidence checked on 2026-08-30

- `task table` produced the article's role table, with `judge` set to `writes: no`.
- `task checks` passed both deterministic scripts.
- `task test` passed: 310 tests in 0.65 seconds.
- The captured Agent SDK poll is represented honestly: T900 timed out and received `needs-human`; T901 then continued; a backend credit failure on T902 ended the overall command before final per-ticket lines could print.
- The three GitHub screenshots are explicitly identified as course-lab UI, separate from the Agent SDK transcript.
- The old figure apologies are gone because the current workflow routes green-without-`LGTM` to `waiting`, the sequence separates `check_fields` from the still-red `check_stop` branch, and `NO_WRITE` includes `NotebookEdit`.
- Static scan found no em dash, banned course-logistics terms, CDI imports, or `Recap.` / `Next.` stamps in the article.

The figures now use the installed `imagen-diagrams` pipeline with its `agent-control` theme. A visual review confirmed every source label and branch in the workflow, sequence, and two-fences diagrams. The two regenerated images that initially failed fidelity were rejected and rerendered with concrete correction feedback.

---

# Earlier grade: Python Owns the Loop (pre-handoff rewrite)

## Verdict
PASS

No hard fail. No axis below 4. The rewrite dropped the CDI spine (ATM, Recap./Next., victory lap, interceptors, beans.xml). Outline beats are present. Load-bearing listings match this folder. Voice is manifesto plus CrewAI-guide rhythm with one leftover worksheet heading.

## Hard fails

| item | result | evidence |
| --- | --- | --- |
| 1. Runnable from the article | pass | Clone URL `https://github.com/RichardHightower/reliable-agentic-lab.git`, then `cd reliable-agentic-lab/solutions/sol1_enhancer_agent_sdk`. Commands match `HOW_TO_RUN.md` and `.agents/skills/test-sol1-ticket-enhancer/SKILL.md`: `cp config.json.example config.json`, `echo 'ANTHROPIC_API_KEY=...' >> ../../.env`, `task setup`, `task clone`, `task table`, `task checks`, `task test`, `task reset-test-tickets`, `task create-test-tickets`, `task run --`, exact `LGTM`, `task run --`. `task poll-forever --` appears in the trigger recap and in Run it, including `while true: task run; sleep poll_interval`. Reset vs create vs poll is explicit: create is the only task that opens issues; `task run --` never does; closing is not a reset. Optional `timeout 420 task run --` matches HOW_TO_RUN. |
| 2. Define before use | pass | **Loop engineering**, **production loop**, and the five nodes (trigger, action, verify, memory, exit) are defined in the first concepts section before any file is opened. **Harness engineering** is the next paragraph. Four properties get a table after the figure. **ReAct** is inner cycle vs outer control before the ReAct figure. **Stable failure** is defined in the failure list. **Signature** is defined in walkthrough step 8, then again immediately before listing 6. **Proper subset** is defined in step 7 before listing 7c. **Maker / checker** is banking dual-control, then doer/judge. **Contract** is disambiguated as `.loop.yml` / `contract.py` before the architecture figure. **Front-matter union** is defined in listing 3 note ④ at first use. Exact `LGTM` is taught as a comment token, not a model word, in the app overview and step 3. |
| 3. Concept has a listing | pass | Spot-check against source: listing 5 `REQUIRED` matches `check_fields.py` (bug / feature / ui keys). Listing 6 `check()` order matches `check_stop.py`: same signature, cost, max turns, `round_ + 1 >= budget`, then `stop: False`. Listing 3 `NO_WRITE = ["Edit", "Write", "NotebookEdit", "Bash"]` matches `roles.py`. Listing 4 deny envelope matches `scope_hook`: `hookSpecificOutput` / `hookEventName: "PreToolUse"` / `permissionDecision: "deny"` / reason text; empty `{}` on non-write, missing path, and in-scope. Listing 7b `_one` is findable: find issue, never create, `needs-human` wait, judge the real ticket, ready plus exact `LGTM` is `passed` with `state.clear`, ready without is `waiting`, `_exhausted()` before the doer, then `_improve`, then `check_stop.check`, then `round += 1`. Listing 7c `_improve` is `if after < before:` then `shutil.copyfile`, `finally: candidate.unlink(missing_ok=True)`. Paths on listings 2 to 10. Elision is marked `# ...` on the long cuts (LOOPS, `options_for`, `poll`, `_one`, `_improve`, adapter, `draft`). Naive listing 1 has no path, which the criteria allows under concepts. |
| 4. No seminar logistics | pass | Zero Saturday, Packt, Eventbrite, RICK40, RKC, PKC, AGER, SAC, WikiTicket, second brain. Zero `seminar`. "It is not a workshop recap" is the required refusal, not assumed vocabulary. |
| 5. Hard style bans | pass | Zero `—` or `–`. No sentence starts with So, That, Thus, or Hence. `--` appears only as CLI flags (`task run --`, `task poll-forever --`, `--ticket`, `--simulate-comment`) and markdown `---` rules. |
| 6. Diagrams | pass | Published figures are `substack-images/cover.jpg` plus `*_imagen.png`: four-properties, react-outer-loop, architecture, workflow, sequence, two-fences. No raw Mermaid or PlantUML. `ager-sol1-enhancer_imagen.png` is unused. Each teaching figure has an intro sentence, the image, then teaching. Two-fences is named as the **action** node at tool grain. |
| 7. Named listings with circled line notes | pass | **Code Listing 1** through **10** (7 as 7a/7b/7c). Load-bearing lines carry `# ①` through `# ⑥` where needed. Notes under each listing consume those numbers. Listing 6 marks the round-budget return `# ④`. |
| 8. Recap. / Next. stamps | pass | Zero `**Recap.**` / `**Next.**`. Transitions are prose: "The rest of this article is the governor around that `while`." / "Before we open them, walk one poll as a story." / "The rest of the article is the code that makes those eight steps true." CrewAI tell-show-notes-move-on, not a stamp on every H2. |
| 9. No CDI-import | pass | Zero AutomatedTellerMachine, AtmMain, `beans.xml`, "victory lap", "second interceptor". Banking appears once as maker/checker dual control, not as an ATM demo. "declare victory because the last reply said DONE" is ordinary false-completeness language, not the CDI victory-lap chapter. |
| 10. Honesty | pass | `needs-human` on stop, hang, and already-set label. Hung dump `.harness/last-doer-T<id>.md` written in `turns.py` `draft()` before `stop_reason` is inspected. Fail-open `{}` taught in listing 4, the pull quote, and listing 10. Proper-subset replace: `after < before`, "Not worse is not good enough." Bug vs feature rubric: listing 5 notes plus inspect ("A bug needs title, steps, expected, actual, environment"). T900 may fail closed. Still-red `waiting` (`round N, still missing ...`) is not green waiting. `_exhausted()` before the doer. 180s timeout. Red rubric never consumes `LGTM`. Comments never start a round. Closing is not a reset. |
| 11. Open and close | pass | Open: title, subtitle, cover, italic dek, intern/turbine hook, **In this article**, "not a prompt cookbook / not a workshop recap." Close order: **Do this today** (five bullets), then **Five nodes, five files**, then a closer a stranger can share ("reply and tell me which loop you need to put a governor on"). |
| 12. Voice | pass | First screen is lived ("I have watched an agent declare a ticket done") plus manifesto (turbine/governor, intern grading homework). Tutorial rhythm is CrewAI: syllabus paragraph, named listings, circled notes, figure then what it proved, Do this today, side-by-side recap. Headers name concepts ("Bounded authority", "ready is a fact", "Cost is data"). Not a 2011 DZone pastiche. Residual rubric smell is isolated: "## How this demonstrates loop engineering" plus "Walk the five nodes only through listings you already saw." The heading is a worksheet label, not the whole article. Axis Substack shape is capped at 4 for it. Not a hard fail. |

## Axis scores

**Teachability: 4.** Author outline is complete: intro, loop vs harness, five nodes plus four properties plus ReAct plus four failures, app and cast, one-poll walk with workflow and sequence, listings that implement the walk, five-node demonstration through listings already shown, Run it, Do this today. Listings follow the walk (fences, ready, stop, then `poll` / `_one` / `_improve`). Cap below 5: beat 7 is a lookup table rather than new teaching, and two narrator lines announce the outline ("Then the listings will have somewhere to sit." / "Walk the five nodes only through listings you already saw.") instead of moving in prose.

**Line notes: 5.** Every production listing marks load-bearing lines. Notes spend the numbers: `WRITE_TOOLS` membership, `NO_WRITE` includes Bash, deny envelope keys, `ready: not missing_fields`, `check_stop` order, proper subset `after < before`, hung dump then escalate, tests asserting `{}` vs deny. Listing 6's fourth mark is on `round_ + 1 >= budget`, and the notes admit four Python returns with no fifth that reads the model's sentence.

**Concept-to-code: 5.** Required loop concepts have excerpts: five nodes (7a, 7b, 5, 6, 9), four properties mapped onto those nodes and onto naive listing 1, ReAct inner vs outer (figure plus sequence), pass/retry/escalate (7b outcomes plus `round += 1`), signature (6 and 7b), exact `LGTM` (7b), proper subset (7c). Required harness concepts: role table (2), maker/checker (2 and 3), write scope (2 and 4), two fences plus fail-open `{}` (3 and 4), `check_fields` `ready` (5), `check_stop` (6), adapter cost / 180s (8), hung dump (9), tests pin the deny envelope (10).

**Runnable path: 5.** HOW_TO_RUN one-time setup, no-model scripts, live GitHub trio, inspect, exact `LGTM`, second poll, hung dump, two closed/missing-issue messages, and `task poll-forever --` all appear. Skill seeds T001 / T900 / T901 / T902 with the same expected roles. Skill rule that `task run --` polls and does not create issues is restated. Article inspect is stricter than the skill (bug scored against `REQUIRED`, not Problem/Proposal/Value). No command drift.

**Substack shape: 4.** Title, subtitle, cover, italic dek, hook in the first screen, **In this article**, pull quotes that restate the thesis, concept-named headers, six teaching figures plus cover, Do this today, shareable closer. You-address and first person are in register. Below 5: turbine / flyballs returns three times in concepts plus the closer (manifesto used it once, then the work). Seven tables, including a four-properties table that restates the figure. Beat 7 heading is the author's outline item pasted as an H2.

**Honesty: 5.** Failure paths are taught as outcomes, not footnotes: `needs-human`, hung dump path, fail-open `{}`, proper-subset replace, bug vs feature rubric, T900 fail-closed, still-red `waiting`, `_exhausted` before another draft, 180s cap, comments do not start a round, a red rubric does not consume `LGTM`. Sibling `solutions/sol1_enhancer/` is named as the other host, same facts, different fence shape.

## Required edits

PASS. Optional polish, max 8:

1. Rename `## How this demonstrates loop engineering` and drop the syllabus echo "Walk the five nodes only through listings you already saw." Keep the five-node walk. Give the section a concept name.
2. Listing 2: `PURPOSE` silently drops planner and the other keys; `FALLBACK_SCOPE` silently drops `writer`. Mark those cuts `# ...` the way `LOOPS` already does.
3. Listing 7b uses `recorded` after `# ...` without showing `recorded = tkt.meta.get("github_issue")`. Show the assignment or stop using the name.
4. Listing 5 wraps `ValueError` across three lines. `check_fields.py` is one line. Match the file or mark the wrap.
5. Listing 6 is titled "three exits, no fourth" and then numbers four `stop: True` returns. Retitle to four computed stops, none from the model.
6. Cut one turbine reprise. Keep the first-screen governor, the pull quote, and the closer. Drop "Ungoverned, the inner cycle is a turbine with the flyballs removed." (already said at harness: "ship a turbine with the flyballs removed").
7. Listing 4 docstring omits `That is why tests/test_roles.py asserts the deny shape key by key.` Restore it or mark the cut.
8. Dek `A ready contract out` fights the later line `A **contract** here is not the ready ticket`. Change the dek to a ready ticket, or a rubric-ready body.

## Ban scan

| token | count |
| --- | --- |
| em dash `—` or `–` | 0 |
| `--` as punctuation | 0 (CLI flags and markdown `---` only) |
| Sentence-start So / That / Thus / Hence | 0 |
| Saturday / Packt / Eventbrite / RICK40 | 0 |
| RKC / PKC / AGER / SAC | 0 |
| WikiTicket / second brain | 0 |
| seminar | 0 |
| workshop | 1, required refusal: "It is not a workshop recap." |
| AutomatedTellerMachine / AtmMain / `beans.xml` | 0 |
| victory lap | 0 |
| second interceptor / interceptor | 0 |
| Recap. / Next. stamps | 0 |
| `ager-sol1-enhancer_imagen.png` | unused |
| "declare victory" | 1, ordinary false-completeness (line 378), not the CDI stamp |
