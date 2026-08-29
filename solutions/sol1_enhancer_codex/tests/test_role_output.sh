#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/.harness/doer-T001.md"

mkdir -p "$(dirname "$OUT")"
printf 'stale role output\n' > "$OUT"

PATH="$ROOT/tests/fixtures:$PATH" "$ROOT/bin/role.sh" enhancer-doer "$OUT" "draft a ticket" > "$TMP/stdout"
test "$(cat "$OUT")" = "fresh role output"
test "$(cat "$TMP/stdout")" = "fresh role output"

printf 'stale role output\n' > "$OUT"
if FAKE_CODEX_MODE=empty PATH="$ROOT/tests/fixtures:$PATH" "$ROOT/bin/role.sh" enhancer-doer "$OUT" "draft a ticket" > /dev/null 2> "$TMP/empty.err"; then
  echo "role runner accepted missing output" >&2
  exit 1
fi
grep -F "enhancer-doer produced no output" "$TMP/empty.err" > /dev/null
test ! -e "$OUT"
