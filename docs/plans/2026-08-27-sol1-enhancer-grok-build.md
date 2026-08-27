---
date: 2026-08-27
slug: sol1-enhancer-grok-build
title: Ship the ticket enhancer as a Grok Build project plugin
epic: 01M121J9XMX7V6QA3NWTNQSA3C
items: [01M121J9Y5KMJJKXZ2JR9ESRZ3, 01M121J9Y5A87WHGYDEDR6VXPE, 01M121J9Y6HFQWKMY5S359NT9H, 01M121J9Y64S2BPQKED7BW6NB9, 01M121J9Y68EZJ6C630Y0KZ4SR, 01M121J9Y650XXJWZZ1PSF19C2, 01M121J9Y61HRS27S0WCWCA8PE, 01M121J9Y61NF9FPH3V467FC78, 01M121J9Y6M68WZ33M3Z8E2QRF, 01M121J9Y68196Y3XH6SX1Q6BP]
git_hash: "85ff7bdcea104b6e58b54dbf382af3c6271c40fa"
---

# Ship the ticket enhancer as a Grok Build project plugin

Replace the stale Python answer in `solutions/sol1_enhancer_grok_build/` with
a real Grok Build project plugin named `ticket-enhancer`. It runs the same
loop as the Claude Code answer in `solutions/sol1_enhancer/.claude/`, with the
same three roles and the same two deterministic gate scripts.

## Tasks

- [ ] (P1) Prove `.grok/plugins/` discovery before writing the loop
  Create a stub `plugin.json` plus one trivial skill, run `grok plugin
  validate`, trust the clone, and confirm `grok inspect` lists
  `ticket-enhancer` under Plugins. `--plugin-dir` does not exist on grok
  1.0.5, so project scope is the only path that keeps the plugin in the repo.

- [ ] (P1) Probe the real subagent spawn tool name
  Add a throwaway probe agent, run one headless call, and record which tool
  Grok actually names. Do not write `task` into SKILL.md on the strength of
  the README alone.

- [ ] (P1) Port the two agents and the orchestrator skill
  Copy the judge and doer prose intact, switch the frontmatter to Grok tool
  IDs so neither can write or spawn, and port SKILL.md with Grok script paths
  and no built-in `loop` skill.

- [ ] (P1) Fix the two Claude SKILL bugs in the port
  Step 8 must persist `last_comment_id`, using `sim:<hash>` for
  `--simulate-comment`. Step 0 must skip `*.enhancer-candidate.md` as well as
  `*.ready.md`. Do not edit `solutions/sol1_enhancer`.

- [ ] (P2) Copy the gate scripts, bin scripts, and config example
  `check_fields.py`, `check_stop.py`, `poll_forever.sh`,
  `setup_test_tickets.sh`, and `config.json.example` move across unchanged.

- [ ] (P2) Write the Taskfile with a pinned dir and a trust target
  `run` pins `dir` so Grok discovers the plugin from its cwd. `trust` is step
  zero. Port the deny rules from the Claude settings file.

- [ ] (P2) Add the debug hooks, and drop them if the schema refuses
  `grok -p` prints nothing until the run finishes, so `debug.log` earns its
  place. Hooks are a convenience, never a gate on the loop.

- [ ] (P2) Write SPEC, HOW_TO_RUN, AGENTS, README, and IMPLEMENTATION_NOTES
  IMPLEMENTATION_NOTES is attendee-facing: why a run does nothing without
  trust, why `--plugin-dir` is a dead end, and how to check the layout.

- [ ] (P2) Delete the stale Python answer
  Remove `loop.py`, `criteria.py`, `gates.py`, and `ticket.py` only after the
  plugin runs.

- [ ] (P1) Verify with two simulated polls on T001
  The second poll must hit the stable-failure exit and add `needs-human`.
  Also run both `--demo` self-checks, `task lint`, and confirm the deny rules
  still bite under whichever permission flag ships.
