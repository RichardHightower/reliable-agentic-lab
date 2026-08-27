---
date: 2026-08-27
slug: sol1-enhancer-skill-comment-id-and-candidate-glob
title: Fix two poll-loop bugs in the sol1 enhancer skill
epic: 01M1220TB14QDQBZNAJGMJ2QR5
items: [01M1220TBFM1N45XT5R5W23GN4, 01M1220TBF79203GXPM50QP8GX, 01M1220TBFJZPVXXRW72XW58T4, 01M1220TBFCCMQQKNWR8SGS1C0]
git_hash: "85ff7bdcea104b6e58b54dbf382af3c6271c40fa"
---

# Fix two poll-loop bugs in the sol1 enhancer skill

The enhancer skill in `solutions/sol1_enhancer/` has two defects that make a
repeated poll misbehave.

## Tasks

- [ ] Persist `last_comment_id` in SKILL.md steps 3, 6, and 8
      Step 8 writes `round` and `previous_signature` but never
      `last_comment_id`, so the next poll sees the same comment as new and the
      loop never settles. Give every comment source an id: the numeric `id`
      for a real GitHub comment, and `sim:` plus the exact text for
      `--simulate-comment`. Write that id back in step 8, and in step 6's
      ready-but-not-LGTM branch.
- [ ] Skip `*.enhancer-candidate.md` in SKILL.md step 0
      Discovery lists `tickets/*.md` and skips only `*.ready.md`. A run that
      dies after step 7 leaves a candidate draft with `state: draft` and
      `loop: enhancer`, which the next run treats as a real ticket.
- [ ] Mirror both rules into lab1 prompt 4
      `labs/lab1_enhancer/prompts/claude-code.md` prompt 4 still describes the
      old step 0 and step 8, so a student rebuilds both bugs.
- [ ] Verify with two identical simulate polls
      The second `task run -- --ticket T001 --simulate-comment "..."` must be a
      no-op. Prove that a leftover candidate file is never picked as a ticket.
