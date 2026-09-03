---
date: 2026-09-03
slug: sol3-outline-first-handoff-prompt
title: Handoff prompt for implementing the outline-first sol3 pipeline
git_base: "b93e8765"
branch: claude/sol3-research-agent-review-6tvdak
---

# Handoff prompt

Paste everything below the rule into a fresh coding-agent session.

---

You are implementing the outline-first research white-paper pipeline in
`RichardHightower/reliable-agentic-lab`. This is an implementation task.
Two review documents already exist; read them first and do not re-derive
their conclusions.

## Repository and branch

- Repo: https://github.com/RichardHightower/reliable-agentic-lab
- Start from branch `claude/sol3-research-agent-review-6tvdak`, which
  carries the design docs. Create your working branch from it:
  `codex/sol3-outline-first-phase1` (or your agent's prefix).
- Target folder for this pass: `solutions/sol3_research_agent_sdk/`.
  Do not touch `solutions/sol3_research_deep_agents/` yet. That port is
  a copy step after this one lands.

## Read in this order

1. `CLAUDE.md` at the repo root. It is non-negotiable. In particular: no
   shared libraries, no `loops/` package, every solution folder is
   standalone, `task test` from inside the folder is the check.
2. `docs/plans/2026-09-02-sol3-white-paper-review.md`. The diagnosis:
   why the current pipeline writes short papers.
3. `docs/plans/2026-09-03-sol3-outline-first-design.md`. The target
   design. The section "The pipeline, phase by phase" is your spec. The
   section "What to avoid, named" is a list of failures you must not
   reproduce.
4. `solutions/sol3_research_agent_sdk/SPEC.md`, `HOW_TO_RUN.md`, and
   `roleplan.py`. Then `paper.py`, `turns.py`, `load_agents.py`,
   `roles.py`, `checks.py`, `gates.py`, and `tests/`.

## Scope of this pass: phase 1 of the design, the outline stage

Implement, in `solutions/sol3_research_agent_sdk/` only:

1. **Outline schema.** Replace the planner's plan shape with the
   `Outline` / `OutlineSection` shape from the design doc: per section
   `id`, `heading`, `objective`, `abstract`, `key_questions[]`,
   `claims_to_support[]`, `required_evidence[]`, `word_target`,
   `figures[{name, kind: diagram|chart, shows, data_needed}]`,
   `depends_on[]`; paper-level `title`, `audience`, `thesis`,
   `word_target_total`. Define it as a JSON schema in `load_agents.py`
   next to `PLAN_SCHEMA` and pass it as `output_format`. Keep it bounded
   and non-recursive.
2. **Outliner role.** Rename or replace `research-planner` with
   `research-outliner` in `plugin/agents/`. Read tools only. Its prompt
   states the schema, the profile's word budget, and book-gen2's style of
   validation checklist ("sections must be objects", unique ids, id
   patterns). Model: `claude-sonnet-5`, set on the `AgentDefinition`.
3. **Deterministic outline validator** in Python, run before anything
   else sees the outline: ids unique, `depends_on` references earlier
   sections only and is acyclic, word targets sum to
   `word_target_total` within ten percent, every `kind: chart` figure
   has a non-empty `data_needed`, every section has at least two
   `key_questions`. Its error text is the retry instruction. Two
   attempts, then escalate, using the existing `attempt()` helper in
   `paper.py`.
4. **Outline judge role.** New `research-outline-judge` agent, read
   tools only, model `claude-opus-5`, adaptive thinking (omit the
   `thinking` parameter), effort `high`. Structured output
   `OutlineVerdict {passed, score, blocking_issues[{section, rule,
   description}], actionable_changes[]}`. Rubric: book-gen's five rows
   (logical flow, accuracy and recency, completeness, redundancy,
   titles) plus the white-paper rows from the design doc. Loop: judge,
   then outliner re-emits with `actionable_changes`, at most three rounds,
   and the failure signature goes through `gates.decide` so a repeated
   signature escalates as a stall. `passed` wins over `score`.
5. **Approval stamp.** `--approve` flag on `loop.py`. When set, after
   the judge passes, write `outline.md` (human-readable) beside
   `outline.json`, print its path, and exit with code 3. On `--resume`,
   diff the current `outline.json` against `outline-judged.json`; if
   changed, run the judge once more; then write
   `outline.approved.json` with `approved_by`, `approved_at`, and the
   sha256 of the approved outline. Without `--approve`, the judge's pass
   writes the same stamp with `approved_by: judge`. Every later phase
   reads `outline.approved.json` and nothing else. Do not re-derive
   sections, questions, or figures from anything but that file.
6. **Wire the existing phases to the approved outline.** `do_research`
   iterates `key_questions` per section in outline order. `write_sections`
   passes `objective`, `abstract`, `claims_to_support`, and `word_target`
   to the writer. `diagram` reads `figures` with `kind: diagram` only;
   ignore `kind: chart` for now with a logged note. `checks.check` gains an
   `outline_coverage` row: every approved section present in `paper.md`
   and every `key_question` named by at least one paragraph in its
   section. Keep the existing rows.
7. **Profiles.** `--profile demo|paper`. `demo` keeps today's numbers.
   `paper` sets `word_target_total` 4000, questions 20, verified claims
   60, `--max-usd` 40, iterations 3. Print the budget before the run.
8. **Scope the exit doctrine to the E2E lane.** `loop.py` passes
   `enforce_loop_doctrine=False` by default; `e2e.py` passes `True`.
   Remove `bind_exit_doctrine` from the normal plan path; keep it
   reachable from `e2e.py` through the commissioning brief.
9. **Fixture and offline twin.** Update `fixtures/research.json` and
   `OfflineTurns` in `turns.py` so `task demo` runs the new outline and
   judge phases with no key and no network. The offline judge returns
   `passed: true` with an empty issue list, as the offline review does.
10. **Tests.** Extend `tests/` so `task test` covers: schema validity,
    every validator rule with a failing example, the judge loop stall
    path, the approval stamp with and without `--approve`, the
    `outline_coverage` row, the doctrine default, and that the role
    table still prints exactly one `yes` in the writes column (the
    writer). No SDK, no key, no network in tests.
11. **Docs.** Update `SPEC.md`, `HOW_TO_RUN.md`, and
    `plugin/skills/research-loop/SKILL.md` so `tests/test_docs.py`
    passes and the role table in the skill matches `roleplan.py`.

## Out of scope for this pass

Forward-only per-section research and writing, the context assembler with
named slots, the Haiku ledger, charts, the editor role, and the Deep
Agents port. Those are phases 2 to 5 of the design's order of work. Do not
start them. Do not widen the source allowlist in this pass either; that
is a separate change.

## Rules

- Follow `CLAUDE.md`. If you find yourself extracting a helper so two
  folders can import it, stop and copy the file instead.
- Python owns validation, assembly, state, and the loop. Models return
  artifacts. No model writes `outline.json`, `outline.approved.json`, or
  `paper.md`.
- No role gains `Bash`. The outliner and judge hold read tools only.
- Model ids are exactly `claude-opus-5`, `claude-sonnet-5`, and
  `claude-haiku-4-5`. No date suffixes.
- Keep every existing check row. Extend, do not loosen.
- Run `task test` inside `solutions/sol3_research_agent_sdk/` until it is
  green, then `task demo`, before you push.
- Commit in small steps with clear messages. Push to your branch. Open a
  PR against `main` titled "sol3: outline-first phase 1 (Agent SDK
  port)" whose body lists what changed per item above and pastes the
  `task test` and `task demo` output.

## Acceptance

- `task demo` produces `outline.json`, `outline-verdict.json`,
  `outline.approved.json`, and a `paper.md` whose sections match the
  approved outline, offline.
- `task run --profile paper --approve TOPIC="how MCP servers
  authenticate"` stops at exit code 3 with a readable `outline.md`, and
  `task run --resume` continues from the approved outline. Report the
  outline it produced, verbatim, in the PR.
- `python3 loop.py --table-only` prints `no` in the writes column for
  every role except the writer.
- No `doctrine` row appears in `check.json` for a normal run.
