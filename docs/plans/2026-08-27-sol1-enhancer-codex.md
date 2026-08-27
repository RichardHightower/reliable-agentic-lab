---
date: 2026-08-27
slug: sol1-enhancer-codex
title: Port the lab 1 ticket enhancer to Codex CLI
epic: 01M1217WSS22TWYCM42N3N6E9W
items: [01M1217WT9586S4PHZFXV2RZQQ, 01M1217WT9NYGSJ2B43G3YE7FW, 01M1217WT9X3FMDT5YYM9D0E4B, 01M1217WTAEM5W96N68WVN3CVS, 01M1217WTAPT5AVHK27NAJJPMY, 01M1217WTA3WFB7X29CF69BMJ5, 01M1217WTAK4MAAXX3P7279H54]
git_hash: "85ff7bdcea104b6e58b54dbf382af3c6271c40fa"
---

# Port the lab 1 ticket enhancer to Codex CLI

## Tasks

- [ ] Probe the three Codex sandbox assumptions
      Confirm a read-only child still holds tools, that a skill resolves by
      its $name marker, and that a workspace-write process can spawn a
      read-only child. Each probe has one allowed fallback that keeps the
      child process read-only.

- [ ] Replace the old Python port with a Codex skill tree
      Delete loop.py, criteria.py, gates.py, and ticket.py. Add
      .agents/skills/enhancer-loop, enhancer-judge, and enhancer-doer, plus
      AGENTS.md and bin/role.sh.

- [ ] Port the orchestrator SKILL.md step for step
      Keep every step number, the argument list, the ready rule, the state
      file, and all seven gh commands. Steps 5 and 7 run bin/role.sh as a
      shell command, never an in-session skill.

- [ ] Give a simulated comment a stable id
      Compute sim:<sha256 first 12 hex> in step 3 and persist it as
      last_comment_id in step 8, so a repeated simulate reads as the same
      comment and the stable failure exit fires.

- [ ] Write the Codex Taskfile and the runnable scripts
      Orchestrator runs workspace-write with network on and --add-dir on the
      target repo. Copy check_fields.py and check_stop.py verbatim.

- [ ] Write SPEC.md, HOW_TO_RUN.md, and IMPLEMENTATION_NOTES.md
      IMPLEMENTATION_NOTES.md explains to an attendee why Codex isolation is
      a process sandbox and not a per-agent tool list. Link it from the other
      two.

- [ ] Verify the loop end to end and update the pointers
      Run the eight verification steps. Only after one real poll passes,
      rewrite labs/lab1_enhancer/prompts/codex.md and the solutions/README.md
      table row.
