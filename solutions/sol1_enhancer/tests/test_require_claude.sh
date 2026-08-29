#!/usr/bin/env bash
# No model. Asserts the preflight names the right folders instead of a bare 127.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ="$ROOT/bin/require_claude.sh"
chmod +x "$REQ"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok $*"; }

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/require-claude.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

FAKE="$WORKDIR/emptybin"
mkdir -p "$FAKE"
# Keep a unix PATH so env can find bash; just omit any claude binary.
PATH_NO_CLAUDE="$FAKE:/usr/bin:/bin"

out="$(PATH="$PATH_NO_CLAUDE" "$REQ" 2>&1)" && rc=0 || rc=$?
[[ "$rc" -eq 127 ]] || fail "missing claude should exit 127, got $rc"
[[ "$out" == *'"claude": executable file not found'* ]] || fail "expected PATH error, got $out"
[[ "$out" == *'sol1_enhancer_grok_build'* ]] || fail "expected grok folder, got $out"
[[ "$out" == *'sol1_enhancer_opencode'* ]] || fail "expected opencode folder, got $out"
[[ "$out" == *'sol1_enhancer_codex'* ]] || fail "expected codex folder, got $out"
[[ "$out" == *'labs/lab1_enhancer'* ]] || fail "expected lab folder, got $out"
[[ "$out" == *'task detect'* ]] || fail "expected task detect, got $out"
pass "missing claude names the other runtimes"

# Present claude: silent success, no redirect text.
cat > "$WORKDIR/claude" <<'BIN'
#!/usr/bin/env bash
exit 0
BIN
chmod +x "$WORKDIR/claude"
out="$(PATH="$WORKDIR:/usr/bin:/bin" "$REQ" 2>&1)" && rc=0 || rc=$?
[[ "$rc" -eq 0 ]] || fail "claude on PATH should exit 0, got $rc"
[[ -z "$out" ]] || fail "expected no stdout/stderr when claude exists, got $out"
pass "claude on PATH is a no-op"

echo "all tests passed"
