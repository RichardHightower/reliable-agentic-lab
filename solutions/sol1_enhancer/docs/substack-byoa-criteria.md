# Criteria: Substack tutorial *Bring Your Own Agent*

Part 3 of the loop-engineering series. Part 1 is `sol1_enhancer_agent_sdk/docs/substack-python-owns-the-loop.md`. Part 2 is `sol1_enhancer_deep_agents/docs/substack-the-second-runtime.md`.

**This is the first article written under the no-table, no-list rules.** Load `references/tables.md` before drafting and again before publishing.

## The thesis this article must land

Parts 1 and 2 put Python around the loop and then proved the loop survived a runtime swap. Part 3 removes the Python entirely. The same enhancer runs as a Claude Code plugin, a Codex skill set, and a Grok Build plugin, and the script that decides when to stop comes across byte identical. Then the second question: an unattended loop has to live somewhere, and the trigger moves through four homes while the loop does not change.

## Two claims to verify before drafting, not after

`check_stop.py` is byte identical across the Claude Code, Codex, and Grok Build ports. Confirm with `diff` and paste the command.

`check_fields.py` is not identical. The Grok Build port added `source_evidence` to the bug rubric and a `source_status` gate that discards that field unless the judge says the source supports the reported behavior. That is a deliberate strengthening by one port, not drift, and the article says so plainly.

## Required outline

1. **Hook and thesis.** You already have a coding agent you like. The question is not which one, it is what survives when you switch. Thesis inside 400 words.
2. **Skill form and Python form.** Define the split. The skill form asks the platform to follow the role and budget instructions. The Python form makes them program data. Both ship the same two check scripts.
3. **Three layouts, one cast.** Claude Code, Codex, Grok Build side by side. Table image plus expansion.
4. **Three ways to deny the judge a write.** The strongest section. A frontmatter allowlist, an operating-system sandbox, and an allowlist paired with a denylist. The mechanisms escalate.
5. **What came across, and what one port chose to raise.** The identical `check_stop.py` and the stricter Grok rubric.
6. **Where the loop runs.** Four rungs: `poll-forever`, cron, GitHub Actions on issue events, and a webhook receiver behind ngrok or on a Droplet. Each rung gets a listing.
7. **The adapter is not the loop.** The receiver verifies, locks, replies, and starts. It never grades a ticket.
8. **Try it, closer, glossary, sources.**

## Hard fails

1. **Zero Markdown tables in the body.** Every table renders to a PNG in `docs/substack-images/` with a source at `docs/tables/<name>.html`. Every table image carries an expansion passage that adds background rather than restating cells.
2. **Zero `- ` bullets and zero `1. ` numbered items in the body.** Content that wants to be a list becomes a table with a column carrying the reason.
3. **Glossary and Sources are run-in bold text.** Bold term, colon, sentence. Neither is a list and neither is a table.
4. `scripts/publish-gist.sh --check-only` exits 0 before any push.
5. Every command matches the real `HOW_TO_RUN.md`, `Taskfile.yml`, `GITHUB-ACTIONS.md`, or the deploy scripts. Cron has no lab material, so that passage is written fresh and says so.
6. The three covered ports are `sol1_enhancer`, `sol1_enhancer_codex`, `sol1_enhancer_grok_build`. Name opencode, vscode, antigravity, and copilot CLI in one sentence and do not walk them.
7. Zero em dashes. No sentence starts with So, That, Thus, Hence, or Here. No sentence starts with a bare filename, command, or identifier.
8. No internal or event vocabulary: Saturday, Packt, Eventbrite, RICK40, RKC, PKC, AGER, SAC, WikiTicket, "second brain", "seminar", "attendee", "takehome".
9. Named listings with `# ①` on load-bearing lines, notes one number per line.
10. The rubric difference between ports is presented as a deliberate choice with its reasoning, never as a fault.
11. Part 1 and part 2 are reviewed in a few sentences and linked, not re-taught.
12. Real output only. Anything shown as terminal output is captured from a real run or is not shown.

## Axes (0 to 5, pass: no hard fail, no axis below 4)

| Axis | 5 looks like |
| --- | --- |
| Teachability | A reader picks a coding agent and a deployment target by the end |
| Table images | Every table is a PNG whose expansion passage teaches more than the cells |
| Concept-to-code | Every portability claim has a listing and a reproducible `diff` |
| Runnable path | No drift from the lab's own files |
| Substack shape | Dek, hook, pull quotes, figures, closer. No tables, no lists |
| Honesty | The skill form asks where the Python form enforces, and the article says so |
| Series fit | Reviews parts 1 and 2 briefly, carries the callbacks, forward-maps part 4 |

## Callbacks to carry

The turbine and its governor. The intern grading their own homework. The proper-subset gate. Exact `LGTM` as a human gate. The `<!-- enhancer-loop -->` marker, which reappears as a workflow `if:` guard. Bounded authority, which escalates through the article from a tool list to an operating-system sandbox to a systemd unit.

## Figures

Cover, one deployment-ladder diagram through imagen-diagrams with theme `agent-control`, and three table images through the Chrome recipe in `references/tables.md`.

## Runnable path

```bash
git clone https://github.com/RichardHightower/reliable-agentic-lab.git
cd reliable-agentic-lab/solutions/sol1_enhancer
cp config.json.example config.json
task setup && task clone
task table && task checks && task test
task reset-test-tickets && task create-test-tickets
task run --
# exact LGTM on green tickets, then poll again
```
