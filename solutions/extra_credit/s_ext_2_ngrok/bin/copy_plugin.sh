#!/usr/bin/env bash
# Copy the Lab 1 ticket-enhancer plugin into this folder.
# Do not copy SPEC.md, Taskfile.yml, or HOW_TO_RUN.md. This folder owns those.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
SRC="${SOL1_SRC:-$ROOT/solutions/sol1_enhancer}"

if [[ ! -d "$SRC/.claude/skills/enhancer-loop" ]]; then
  echo "missing sol1_enhancer plugin at $SRC/.claude" >&2
  echo "Lab 1 has to exist first." >&2
  exit 1
fi

mkdir -p "$HERE/.claude" "$HERE/bin"
cp -R "$SRC/.claude/." "$HERE/.claude/"
cp "$SRC/config.json.example" "$HERE/config.json.example"
cp "$SRC/bin/setup_test_tickets.sh" "$HERE/bin/setup_test_tickets.sh"
chmod +x "$HERE/bin/setup_test_tickets.sh"

echo "copied plugin from $SRC into $HERE"
echo "next: cp config.json.example config.json and set fork_owner"
