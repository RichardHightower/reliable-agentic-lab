#!/usr/bin/env bash
# Fail with a useful message before Task shells out to `claude` and prints
# a bare exit 127. This folder is the Claude Code plugin. Grok, Codex, and
# OpenCode each have their own solution folder; the lab folder dispatches
# by skill tree.
set -euo pipefail

if command -v claude >/dev/null 2>&1; then
  exit 0
fi

cat >&2 <<'MSG'
"claude": executable file not found in $PATH

This folder is the Claude Code plugin. `task run` here always calls `claude`.
That is expected. It is not a Grok or OpenCode runner.

If you picked Grok Build:
  cd ../sol1_enhancer_grok_build
  task trust
  task create-test-tickets && task run --

If you picked OpenCode:
  cd ../sol1_enhancer_opencode
  task create-test-tickets && task run --

If you picked Codex:
  cd ../sol1_enhancer_codex
  task create-test-tickets && task run --

If you built the plugin in the lab:
  cd ../../labs/lab1_enhancer
  task detect
  task create-test-tickets && task run --

`task detect` prints grok, opencode, codex, or claude from the skill tree
you copied. A Grok build does not need Claude Code on PATH.

Install Claude Code only if that is the tool you chose:
  npm install -g @anthropic-ai/claude-code
MSG
exit 127
