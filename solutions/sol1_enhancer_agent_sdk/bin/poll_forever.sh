#!/usr/bin/env bash
# Poll forever until killed (Ctrl-C).
#
# Seminar-only stand-in for a real scheduler. Run this in one terminal and
# treat it as if it were a long-running process in the cloud: it never
# stops on its own, whether every ticket has passed or not, it just keeps
# polling on poll_interval from config.json. For production, this becomes
# a cron trigger on a scheduled GitHub Actions workflow instead, see
# SPEC.md.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

INTERVAL="$(jq -r '.poll_interval // "10m"' config.json)"
NUM="${INTERVAL%[a-zA-Z]}"
UNIT="${INTERVAL: -1}"
case "$UNIT" in
  s) SECS=$NUM ;;
  m) SECS=$((NUM * 60)) ;;
  h) SECS=$((NUM * 3600)) ;;
  *) SECS=$INTERVAL ;;  # already a bare number of seconds
esac

echo "polling every ${INTERVAL} (${SECS}s). Ctrl-C to stop."
while true; do
  task run -- "$@"
  echo "--- sleeping ${INTERVAL} ---"
  sleep "$SECS"
done
