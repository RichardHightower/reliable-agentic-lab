#!/usr/bin/env bash
# Run one role (judge or doer) as its own read-only Codex process.
#
# This script is the jail. Codex has no per-agent tool list, so a role cannot
# be told "you hold no write tool" the way a Claude subagent can. What stops
# the judge grading its own draft, and the doer saving it, is that this
# process runs under `-s read-only`: the sandbox refuses every write before
# the model gets a say. See IMPLEMENTATION_NOTES.md.
#
# The flags live here and not in SKILL.md on purpose. A sandbox flag the
# orchestrator retypes each round is a sandbox flag the orchestrator can
# mistype, or drop.
#
# Usage: bin/role.sh <skill-name> <output-file> <prompt...>
set -euo pipefail

SKILL="$1"
OUT="$2"
shift 2

# The solution folder, not the target repo. Codex finds .agents/skills by
# probing ancestors of its working directory, so --cd has to land here or
# the role's SKILL.md is never loaded. A read-only process may still read
# outside its workspace, which is why ticket paths are passed absolute.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# `</dev/null` is load-bearing, not tidiness. When a prompt is passed as an
# argument and stdin is also open, `codex exec` appends stdin to the prompt
# as a <stdin> block, so it blocks until stdin reaches EOF. Called from an
# orchestrator that holds stdin open, that is an indefinite hang and not an
# error: no output, no exit, nothing in the log.
#
# Both output streams go to the floor. Codex narrates its own progress on
# stderr, and the caller wants the role's final message only: the judge's
# JSON, or the doer's candidate body. Anything else here corrupts the parse.
codex exec -s read-only --cd "$DIR" -o "$OUT" "\$$SKILL $*" </dev/null >/dev/null 2>&1

cat "$OUT"
