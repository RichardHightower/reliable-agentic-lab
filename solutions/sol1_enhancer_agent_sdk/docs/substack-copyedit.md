# Post-handoff resolution

The items below record the pre-handoff review. The later course-companion pass resolved its figure findings by correcting and regenerating the three affected PNGs rather than teaching readers to distrust them. It also added actual `task table` output, an honestly bounded live-poll excerpt, clear screenshot attribution, and the Module 1 concepts requested in the handoff plan. The regenerated diagrams now use the `imagen-diagrams` `agent-control` rendering pipeline and passed visual fidelity review.

---

# Earlier copy edit: Python Owns the Loop

## Verdict

The article already works as a loop-engineering tutorial: outline beats 1 to 8 are present, listings 1 to 10 are named with circled notes, honesty paths are taught, and the run path matches `HOW_TO_RUN.md`. Voice is manifesto plus CrewAI rhythm, not a CDI clone. No em dash, no So/That/Thus/Hence openers, no seminar catalog names. What still hurts a stranger is the first screen (sources before the syllabus), one figure that teaches the wrong `LGTM` path, a heading that fights listing 6, a leftover turbine reprise, a table that restates a figure, and an unused use-cases figure that belongs in the app overview. Do not rewrite the piece. Execute the numbered list.

## Section-by-section

**Title, subtitle, dek, cover.** Keep the stack. Subtitle and dek agree: vague ticket in, ready ticket out, Python holds the loop. Cover alt is thin versus the PNG (tweak 12).

**Hook through In this article.** Tweak. The intern-grading-homework hook is the right first screen. Two source paragraphs then sit between that hook and **In this article**, so the syllabus arrives late. Fold the field guide, lab, and newsletter into the syllabus sentence that already names them. Keep "not a prompt cookbook / not a workshop recap" after the pull quote.

**Turbine pull quote.** Keep the first-screen governor and the pull quote. Cut later reprises (tweak 7).

**Loop engineering, and the harness around it.** Keep. Five nodes and harness are defined in plain English before jargon. The field-guide four-line table is useful. Cut "ship a turbine with the flyballs removed" (already said above).

**Four properties of one iteration.** Tweak. Introduce-show-teach is there. The table restates the four boxes. Keep the paragraph that maps boxes onto the five nodes. Do not say "Trigger starts the row"; the PNG has no Trigger box.

**Inner ReAct, outer control.** Keep. Intro, figure, then inner three versus outer two. Mention that both return arrows from Decide are retry (tweak is optional; see image audit).

**What breaks when the governor is off.** Keep. Four failures, then the naive `while`. Listing 1 notes match the marked lines. Signature is defined here before listing 6.

**The app: a ticket enhancer.** Tweak. Cast, GitHub inbox, and architecture figure match outline item 4. `CRM` is used before it is named as the Northwind target checkout. Insert `use-cases_imagen.png` after the three-role bullets, before the architecture control room. Skip `model_imagen.png` (see image audit).

**One poll, step by step.** Tweak. The numbered walk and the outcomes table are the machine. The workflow PNG sends Human LGTM? No into `check_stop`, which is not the code and contradicts the later warning in the Exit section. Teach the divergence. Sequence figure: the orange box is labeled TOOLS on the Enhancer column; inner ReAct is the Agent SDK column. Keep both figures once the teach paragraphs tell the truth.

**Bounded authority: the cast is data.** Keep the listings. Two-fences introduce-show-teach is the best figure cycle in the piece. Add one sentence that the PNG omits `NotebookEdit` (listing 3 includes it). Restore the `scope_hook` docstring line the file still has.

**Verify: ready is a fact.** Keep. Listing 5 matches `check_fields.py`, including the one-line `ValueError`. Notes consume ① to ④. Bug versus feature versus UI is taught.

**Exit: three computed stops, no fourth the model can type.** Tweak the heading only. The listing is already "four computed stops, none from the model," and the notes number four `stop: True` returns. Completing via `LGTM` is correctly a different exit in `enhancer.py`.

**The state machine: one poll in Python.** Keep. 7a/7b/7c follow the eight-step walk. `recorded = tkt.meta.get("github_issue")` is shown. Proper subset, `needs-human`, `_exhausted()` before the doer, and `round += 1` as retry are all here.

**Cost is data, and a hang is a file.** Keep. 180s, hung dump path, fail-open is not this section's job. Notes match ① to ③. The `wait_for` call lives in prose, not in the listing; that is acceptable if you do not claim it is in the excerpt.

**The harness is production code.** Keep listing 10. The sibling `solutions/sol1_enhancer/` paragraph is extra, not a seminar pitch. Leave it unless you need the space.

**Who is allowed to say so.** Keep the heading and the five-node map. Drop the worksheet opener "The five nodes are already in the listings. Here is the map, without a new file." Start with **Trigger.**

**Run it.** Keep. Clone, `task setup`, `task table`, `task checks`, `task test`, reset, create, one poll, exact `LGTM`, second poll, `task poll-forever --` as a laptop stand-in. Do not copy HOW_TO_RUN's word "seminar." Seeds T001 / T900 / T901 / T902 match.

**Do this today.** Keep. Five bullets, same jobs as the CrewAI closer.

**Five nodes, five files.** Keep as the side-by-side recap.

**Sources.** Tweak placement. Keep the three bullets (field guide, GitHub lab, newsletter). Lift the turbine closer out so it follows the recap, then Sources as endnotes.

## Image audit

| file | used? | section | introduce-show-teach? | alt vs PNG | recommended tweak |
| --- | --- | --- | --- | --- | --- |
| `cover.jpg` | yes | open | Cover, not a teaching figure. No teach required. | Alt says "small writing desk inside a mechanical control ring." PNG is a faceless clerk at a wooden desk inside a gear ring with railway tracks, a top gauge, a right-hand shield, and a punch-tape stack, in a control room. | Expand alt (tweak 12). |
| `four-properties_imagen.png` | yes | Four properties | Yes, then a table that repeats the boxes. | Alt names the four boxes. Matches. Teach says "Trigger starts the row"; PNG has no Trigger. Box 3 is dashed orange (same stroke as the tool fence later). | Cut the table. Fix the Trigger sentence. One clause: dashed orange here is evidence, not the tool list. |
| `react-outer-loop_imagen.png` | yes | Inner ReAct | Yes. | Alt matches Perceive/Trigger, inner three, Decide, retry. PNG also draws a second unlabeled return under the row. | Optional: both arrows from Decide are retry. |
| `architecture_imagen.png` | yes | The app | Yes. Control room, then five-node mapping. | Alt matches CLI, Python loop, contract, enhancer, backend, checks, GitHub, tickets. | Keep. Insert use-cases *before* this figure, not instead of it. |
| `workflow_imagen.png` | yes | One poll | Intro is thin. Teach is the numbered walk, which is a different machine than the PNG. | Alt is "Workflow of one poll." PNG is diamonds: Ticket available, Ready, Human LGTM, Retry; orange judge/doer; green Target Repository. LGTM No goes to `check_stop`. Publish is "Orchestrator writes issue and labels." | Teach the LGTM-no divergence. Richer alt. Do not re-render. |
| `sequence_imagen.png` | yes | One poll | Intro claims inner ReAct is the SDK box. PNG paints an orange TOOLS box around Enhancer. | Alt names judge, doer, checks. PNG is five columns plus opt revision / opt final state. One arrow is `check_fields and check_stop` together. | Tell the reader to ignore TOOLS as a role label. Name the compression. Richer alt. |
| `two-fences_imagen.png` | yes | Bounded authority | Yes. Best cycle in the article. | Alt matches. PNG: Fence 1 strips Edit, Write, Bash; judge path green; deny uses `hookSpecificOutput`. Code also strips `NotebookEdit`. | One honesty sentence. Keep the figure. |
| `use-cases_imagen.png` | no | n/a | n/a | PNG: Operator polls, Human reviewer LGTM, GitHub, Claude Agent SDK into Tool Actions (judge, draft, enforce write scope), Publish status and labels. | **Include** in The app, after the three-role bullets, before architecture. |
| `model_imagen.png` | no | n/a | n/a | PNG: Contract, RolePlan, Enhancer, AgentSdkBackend, Ticket. `AgentSdkBackend.judge/draft` are `Enhancer` / `turns.py` in this folder. `Ticket.criteria` is parsed `(AC-n)` lines, not `check_fields.ready`. | **Skip.** The class diagram fights listing 5 and listings 7 to 9. |
| `ager-sol1-enhancer_imagen.png` | no | n/a | n/a | Catalog types this tutorial does not teach. | **Skip.** Do not mention it. |

## Numbered tweaks (writer must do these)

1. **Where:** first screen, the two paragraphs after the intern hook ("The concepts in this article come from…" and "The newsletter version…")
   **Change:** Move **In this article** to sit immediately after the intern hook. Keep one source sentence inside that syllabus (it already names the field guide and the lab). Add the newsletter link there or leave it for Sources. Do not spend two paragraphs on citations before the syllabus.
   **Why:** CrewAI puts the syllabus on the first screen; the manifesto states the thesis before the bibliography.

2. **Where:** **The app: a ticket enhancer**, after the Python / Doer / Judge bullets
   **Change:** Insert `use-cases_imagen.png`. Intro: four actors sit around one poll. Alt: "Operator starts a poll; the SDK only judges, drafts, and enforces write scope; Python publishes status; a human types LGTM." After the figure: the operator starts the poll; the orange Tool Actions box is the only work the SDK does; LGTM is a human actor, not a model token. On first use, name **CRM** as the target checkout `northwind-field-crm`. Then keep the contract sentence and the architecture figure as the control room.
   **Why:** Outline item 4 is the cast. The unused figure is the cast as actors. Architecture is the wiring.

3. **Where:** **One poll, step by step**, after `workflow_imagen.png`
   **Change:** Keep the numbered walk as the source of truth. Add two sentences: Ready? No goes to the doer; Ready? Yes without exact `LGTM` is `waiting`, not `check_stop`. `check_stop` runs only while the rubric is still red. "Orchestrator writes issue and labels" means body and labels. A poll never opens a GitHub issue. Change alt to: "One poll: ticket available, judge, check_fields, ready, human LGTM, else doer and retry; check_stop and needs-human on a still-red stop."
   **Why:** The PNG's LGTM-no arrow is the reverse of listing 7b, and the Exit section already warns that reversing the calls attaches `needs-human` to a green ticket.

4. **Where:** same section, after `sequence_imagen.png`
   **Change:** Teach: the orange box is the Enhancer (outer control) even though the label says TOOLS. Inner ReAct is the Agent SDK column. The combined `check_fields and check_stop` arrow is shorthand; Python asks fields first, and stop only after a still-red `_improve`. Change alt to: "Sequence: loop.py poll, Enhancer, Agent SDK judge then optional draft, Checks, GitHub write at final state, outcome back to loop.py."
   **Why:** The intro and the PNG currently disagree about where tools live.

5. **Where:** `## Exit: three computed stops, no fourth the model can type` and listing 6 notes
   **Change:** Retitle the H2 to **Exit: four computed stops, none from the model**. In the notes, drop "The title still holds." Keep the sentence that completing a ticket (green plus `LGTM`) is a different exit in `enhancer.py`.
   **Why:** The listing already numbers four `stop: True` returns. The heading must not argue with the listing.

6. **Where:** **Four properties of one iteration**, the property table and "Trigger starts the row"
   **Change:** Delete the four-row table. Keep "Read the boxes left to right" and the map onto memory / action / verify / exit. Replace "Trigger starts the row" with: the row is one iteration; **Trigger** is outside this figure, the event that starts it. One clause: dashed orange on box 3 marks evidence you can point at, not the tool fence in the two-fences figure.
   **Why:** The figure already names the four properties. A restating table is the design-doc smell the criteria bans.

7. **Where:** harness paragraph, "still ship a turbine with the flyballs removed"
   **Change:** Cut that sentence (or the turbine half of it). Keep the first-screen governor, the pull quote, and the closer.
   **Why:** The manifesto uses the turbine once, then does the work. This draft returns to it in concepts and again at the end.

8. **Where:** **Who is allowed to say so**, first two sentences
   **Change:** Delete "The five nodes are already in the listings. Here is the map, without a new file." Start with **Trigger.** Listing 7a.
   **Why:** The heading is already a concept name. The opener is a leftover worksheet label.

9. **Where:** close (`## Five nodes, five files` then `## Sources`)
   **Change:** After the five-node table, put the closer paragraph that now ends Sources ("A high-powered agent without a governor is still a turbine…"). Then `## Sources` as the three bullets only.
   **Why:** Required close is Do this today, five-node recap, then a closer a stranger would share. Sources must not sit between recap and closer.

10. **Where:** **Code Listing 4**, `scope_hook` docstring
    **Change:** Restore the file's last docstring sentence: `That is why tests/test_roles.py asserts the deny shape key by key.` Remove the substitute comment. Do not rewrite the source line in prose voice; it is a listing.
    **Why:** `roles.py` still has that sentence. The listing is not line-accurate.

11. **Where:** two-fences teach paragraph, after the figure
    **Change:** Add: the PNG labels Fence 1 as stripping Edit, Write, and Bash. Listing 3 also strips `NotebookEdit`. The judge path on the right is still the path with no write tool.
    **Why:** Alt and PNG under-teach `NO_WRITE` versus the listing the reader is about to trust.

12. **Where:** cover image alt
    **Change:** `Cover: a faceless clerk at a writing desk inside a gear ring, with railway switches, a gauge, a shield, and punch tape, in a control room`
    **Why:** The current alt matches the desk and the ring and misses what the PNG actually shows.

13. **Where:** unused `model_imagen.png`
    **Change:** Do not insert it. If you want types on the page, the file table plus listing 2 already name `RolePlan`. Ready stays `check_fields`, not `Ticket.criteria`.
    **Why:** The class diagram puts `judge`/`draft` on `AgentSdkBackend` and shows `Criterion[]`, which this tutorial never walks.

14. **Where:** **The app**, "The field guide's Table 2 is one control graph"
    **Change:** Drop the table number. Write: the field guide draws one control graph across four objects (enhancer, implementer, researcher, fixer). This tutorial is the first object.
    **Why:** A stranger has not opened the field guide to a numbered table, and the number adds nothing the sentence does not already say.

15. **Where:** `ager-sol1-enhancer_imagen.png`
    **Change:** Leave unused. Do not cite it.
    **Why:** Catalog types this tutorial does not teach.

## Do not change

Voice bans: no em dash; no sentence-start So / That / Thus / Hence in prose (the restored docstring in listing 4 is source, not prose). No Saturday / Packt / RKC / PKC / AGER / SAC / second brain. No ATM / `beans.xml` / victory lap. Do not copy HOW_TO_RUN's "For the seminar" onto `task poll-forever --`; the article's "laptop stand-in" is the right phrase.

Runnable commands already match `HOW_TO_RUN.md`: clone, `cp config.json.example config.json`, `task setup`, `task clone`, `task table`, `task checks`, `task test`, `task reset-test-tickets`, `task create-test-tickets`, `task run --`, exact `LGTM`, second `task run --`, `task poll-forever --`. Leave them.

Listing bodies that already match source: listing 5 `REQUIRED` and `ready: not missing_fields`; listing 6 `check()` order; listing 3 `NO_WRITE`; listing 7b/7c proper subset and `state.clear`. Do not "simplify" those excerpts.

Do not demand new rendered diagrams. Work with existing `*_imagen.png` and `cover.jpg` only.

## Writer applied

- Tweak 1: done (moved **In this article** onto the intern hook; folded field guide, lab, and newsletter links into that syllabus; dropped the two citation paragraphs)
- Tweak 2: done (inserted `use-cases_imagen.png` after the three-role bullets with intro/teach; named CRM as `northwind-field-crm` on first use in the doer bullet)
- Tweak 3: done (workflow alt rewritten; taught Ready-no to doer, green-without-`LGTM` as `waiting`, `check_stop` only on still-red, body-and-labels, poll never opens an issue)
- Tweak 4: done (sequence alt rewritten; taught orange TOOLS as Enhancer, inner ReAct as Agent SDK, combined checks arrow as shorthand)
- Tweak 5: done (H2 is **Exit: four computed stops, none from the model**; dropped "The title still holds."; kept completing-via-`LGTM` as a different `enhancer.py` exit)
- Tweak 6: done (deleted the four-row property table; Trigger is outside the figure; dashed orange on box 3 is evidence, not the tool fence)
- Tweak 7: done (cut the harness-paragraph turbine/flyballs reprise)
- Tweak 8: done (deleted the worksheet opener; section starts at **Trigger.** Listing 7a)
- Tweak 9: done (turbine closer follows the five-node recap; Sources is the three bullets only)
- Tweak 10: done (restored the `scope_hook` docstring last line from `roles.py`; removed the substitute comment)
- Tweak 11: done (two-fences teach now notes Fence 1 omits `NotebookEdit`; judge path is still no write tool)
- Tweak 12: done (cover alt names clerk, gear ring, railway switches, gauge, shield, punch tape, control room)
- Tweak 13: obeyed (did not insert `model_imagen.png`)
- Tweak 14: done (dropped Table 2; field guide draws one control graph across four objects)
- Tweak 15: obeyed (did not insert or cite `ager-sol1-enhancer_imagen.png`)
