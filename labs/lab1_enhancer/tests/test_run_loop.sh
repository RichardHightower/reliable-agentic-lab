#!/usr/bin/env bash
# Detection tests for bin/run_loop.sh. No model, no GitHub, no real CLI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/bin/run_loop.sh"
chmod +x "$RUN"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok $*"; }

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/run-loop.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

detect() {
  RUN_LOOP_DIR="$1" "$RUN" --detect
}

expect_detect() {
  local dir="$1" want="$2"
  local got
  got="$(detect "$dir")"
  [[ "$got" == "$want" ]] || fail "detect in $dir: want $want, got $got"
  pass "detect $want"
}

expect_fail() {
  local dir="$1" needle="$2"
  local out rc=0
  out="$(RUN_LOOP_DIR="$dir" "$RUN" --detect 2>&1)" || rc=$?
  [[ "$rc" -ne 0 ]] || fail "expected failure in $dir, got: $out"
  [[ "$out" == *"$needle"* ]] || fail "expected '$needle' in: $out"
  pass "fail mentions $needle"
}

# Stub settings.json is not a plugin.
mkdir -p "$WORKDIR/stub/.claude"
echo '{}' > "$WORKDIR/stub/.claude/settings.json"
expect_fail "$WORKDIR/stub" "not a plugin"

# Empty folder.
mkdir -p "$WORKDIR/empty"
expect_fail "$WORKDIR/empty" "No enhancer-loop skill"

# Grok plugin tree (the real one, not a settings stub).
mkdir -p "$WORKDIR/grok/.grok/plugins/ticket-enhancer/skills/enhancer-loop"
expect_detect "$WORKDIR/grok" grok

# Grok via the skill symlink the solution folder uses.
mkdir -p "$WORKDIR/grok-link/.grok/skills"
ln -s "../plugins/ticket-enhancer/skills/enhancer-loop" "$WORKDIR/grok-link/.grok/skills/enhancer-loop"
# The symlink target does not exist here; -e is false. Also drop the plugin dir.
# Make the plugin dir so the primary check still works, then a link-only tree:
mkdir -p "$WORKDIR/grok-only-link/.grok/plugins/ticket-enhancer/skills/enhancer-loop"
mkdir -p "$WORKDIR/grok-only-link/.grok/skills"
ln -sfn "../plugins/ticket-enhancer/skills/enhancer-loop" "$WORKDIR/grok-only-link/.grok/skills/enhancer-loop"
expect_detect "$WORKDIR/grok-only-link" grok

# Claude skill tree.
mkdir -p "$WORKDIR/claude/.claude/skills/enhancer-loop"
expect_detect "$WORKDIR/claude" claude

# Codex.
mkdir -p "$WORKDIR/codex/.agents/skills/enhancer-loop"
expect_detect "$WORKDIR/codex" codex

# OpenCode.
mkdir -p "$WORKDIR/opencode/.opencode/skills/enhancer-loop"
expect_detect "$WORKDIR/opencode" opencode

# Multiple trees: AGENT wins.
mkdir -p "$WORKDIR/both/.claude/skills/enhancer-loop"
mkdir -p "$WORKDIR/both/.grok/plugins/ticket-enhancer/skills/enhancer-loop"
out="$(AGENT=grok RUN_LOOP_DIR="$WORKDIR/both" "$RUN" --detect)"
[[ "$out" == grok ]] || fail "AGENT=grok should win, got $out"
pass "AGENT=grok overrides"

out="$(AGENT=claude RUN_LOOP_DIR="$WORKDIR/both" "$RUN" --detect)"
[[ "$out" == claude ]] || fail "AGENT=claude should win, got $out"
pass "AGENT=claude overrides"

# Multiple trees, neither CLI installed, no AGENT: honest error.
out="$(RUN_LOOP_DIR="$WORKDIR/both" "$RUN" --detect 2>&1)" && rc=0 || rc=$?
[[ "$rc" -ne 0 ]] || fail "multiple plugins should fail without AGENT"
[[ "$out" == *"Multiple plugins"* ]] || fail "expected Multiple plugins, got $out"
pass "multiple plugins need AGENT"

# Missing CLI names the binary and does not fall back to claude.
out="$(RUN_LOOP_DIR="$WORKDIR/grok" "$RUN" --dry-run /tmp/repo 2>&1)" && rc=0 || rc=$?
[[ "$rc" -eq 127 ]] || fail "missing grok should exit 127, got $rc"
[[ "$out" == *'"grok": executable file not found'* ]] || fail "expected grok PATH error, got $out"
[[ "$out" != *'claude -p'* ]] || fail "must not fall back to claude: $out"
pass "grok plugin does not call claude"

# Fake grok on PATH: dry-run should invoke grok, not claude.
FAKE="$WORKDIR/fakebin"
mkdir -p "$FAKE"
cat > "$FAKE/grok" <<'EOF'
#!/usr/bin/env bash
echo "fake grok $*"
EOF
chmod +x "$FAKE/grok"
out="$(PATH="$FAKE:$PATH" RUN_LOOP_DIR="$WORKDIR/grok" "$RUN" --dry-run /tmp/northwind --ticket T001 2>&1)"
[[ "$out" == *"using grok"* ]] || fail "expected using grok, got $out"
[[ "$out" == *"--always-approve"* ]] || fail "expected grok flags, got $out"
[[ "$out" == *"-p"* ]] || fail "expected -p last, got $out"
[[ "$out" == *"enhancer-loop"* ]] || fail "expected enhancer-loop, got $out"
[[ "$out" == *"northwind"* ]] || fail "expected repo path, got $out"
[[ "$out" == *"T001"* ]] || fail "expected T001, got $out"
[[ "$out" != *"claude"* ]] || fail "dry-run leaked claude: $out"
pass "dry-run grok command"

echo "all tests passed"
