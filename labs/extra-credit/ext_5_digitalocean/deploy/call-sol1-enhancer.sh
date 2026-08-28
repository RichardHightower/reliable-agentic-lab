#!/usr/bin/env bash
# One poll of solutions/sol1_enhancer. The webhook calls this. You can too.
# Usage: call-sol1-enhancer.sh T001
#        call-sol1-enhancer.sh T001 --print
set -euo pipefail

PRINT=0
TICKET=""
for arg in "$@"; do
  if [[ "$arg" == "--print" ]]; then
    PRINT=1
  elif [[ -z "$TICKET" && "$arg" != -* ]]; then
    TICKET="$arg"
  fi
done
if [[ -z "$TICKET" ]]; then
  echo "usage: $0 T001 [--print]" >&2
  exit 2
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
BACKEND="${AGENT_BACKEND:-claude}"
case "$BACKEND" in
  grok) DIR="$ROOT/solutions/sol1_enhancer_grok_build" ;;
  opencode) DIR="$ROOT/solutions/sol1_enhancer_opencode" ;;
  codex) DIR="$ROOT/solutions/sol1_enhancer_codex" ;;
  agent-sdk) DIR="$ROOT/solutions/sol1_enhancer_agent_sdk" ;;
  deep-agents|langgraph) DIR="$ROOT/solutions/sol1_enhancer_deep_agents" ;;
  claude|python|*) DIR="$ROOT/solutions/sol1_enhancer" ;;
esac

CMD=(task run -- --ticket "$TICKET")
if [[ "$PRINT" == "1" ]]; then
  printf 'cd %q &&' "$DIR"
  printf ' %q' "${CMD[@]}"
  printf '\n'
  exit 0
fi
if [[ ! -d "$DIR" ]]; then
  echo "missing $DIR" >&2
  exit 127
fi
if [[ ! -f "$DIR/config.json" ]]; then
  echo "copy $DIR/config.json.example to config.json and set fork_owner" >&2
  exit 1
fi
cd "$DIR"
exec "${CMD[@]}"
