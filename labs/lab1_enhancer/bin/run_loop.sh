#!/usr/bin/env bash
# Dispatch one poll to whichever plugin this folder actually holds.
#
# The lab ships a .claude/settings.json stub for the Claude path. That is not
# a plugin. A real plugin is an enhancer-loop skill tree. Saturday students
# may build Claude, Codex, Grok, or OpenCode here; task run used to call
# `claude` regardless, which is how a Grok student got exit 127.
#
# Detection looks at the skill tree, not at which CLI happens to be on PATH.
# AGENT=claude|codex|grok|opencode overrides when more than one tree is present.
set -euo pipefail

DIR="${RUN_LOOP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

DETECT=0
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --detect) DETECT=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --) shift; break ;;
    *) break ;;
  esac
done

has_claude() { [[ -d "$DIR/.claude/skills/enhancer-loop" ]]; }
has_codex()  { [[ -d "$DIR/.agents/skills/enhancer-loop" ]]; }
has_grok() {
  [[ -d "$DIR/.grok/plugins/ticket-enhancer/skills/enhancer-loop" ]] \
    || [[ -e "$DIR/.grok/skills/enhancer-loop" ]]
}
has_opencode() { [[ -d "$DIR/.opencode/skills/enhancer-loop" ]]; }

cli_for() {
  case "$1" in
    claude) echo claude ;;
    codex) echo codex ;;
    grok) echo grok ;;
    opencode) echo opencode ;;
    *) echo "$1" ;;
  esac
}

need_cli() {
  local bin="$1"
  if ! command -v "$bin" >/dev/null 2>&1; then
    cat >&2 <<EOF
"$bin": executable file not found in \$PATH

This folder's plugin is a $bin plugin. Install that CLI, then retry
\`task run --\`. A Grok build does not need Claude Code; a Codex build
does not need grok.

  Claude Code  npm install -g @anthropic-ai/claude-code
  Grok         install the grok CLI so \`which grok\` prints a path
  Codex        install the Codex CLI so \`which codex\` prints a path
  OpenCode     install the OpenCode CLI so \`which opencode\` prints a path

Override with AGENT=claude|codex|grok|opencode if more than one plugin
is present. See TROUBLESHOOTING.md and FALL-BEHIND.md.
EOF
    exit 127
  fi
}

found=()
has_claude && found+=(claude)
has_codex && found+=(codex)
has_grok && found+=(grok)
has_opencode && found+=(opencode)

pick="${AGENT:-}"
if [[ -z "$pick" ]]; then
  if [[ ${#found[@]} -eq 1 ]]; then
    pick="${found[0]}"
  elif [[ ${#found[@]} -eq 0 ]]; then
    cat >&2 <<EOF
No enhancer-loop skill in $DIR.

A .claude/settings.json stub is not a plugin. Build from prompts/, or
copy the answer for the tool you are running from FALL-BEHIND.md.

  Claude    .claude/skills/enhancer-loop
  Codex     .agents/skills/enhancer-loop
  Grok      .grok/plugins/ticket-enhancer/skills/enhancer-loop
  OpenCode  .opencode/skills/enhancer-loop
EOF
    exit 1
  else
    available=()
    for r in "${found[@]}"; do
      if command -v "$(cli_for "$r")" >/dev/null 2>&1; then
        available+=("$r")
      fi
    done
    if [[ ${#available[@]} -eq 1 ]]; then
      pick="${available[0]}"
    else
      echo "Multiple plugins in this folder: ${found[*]}" >&2
      echo "Set AGENT to one of: ${found[*]}" >&2
      exit 1
    fi
  fi
fi

case "$pick" in
  claude|codex|grok|opencode) ;;
  *)
    echo "Unknown AGENT='$pick'. Use claude, codex, grok, or opencode." >&2
    exit 1
    ;;
esac

if [[ $DETECT -eq 1 ]]; then
  echo "$pick"
  exit 0
fi

need_cli "$(cli_for "$pick")"

if [[ $# -lt 1 ]]; then
  echo "usage: bin/run_loop.sh [--detect] [--dry-run] <target-repo> [skill-args...]" >&2
  exit 1
fi

TARGET="$1"
shift
EXTRA=("$@")
PROMPT="/enhancer-loop --repo ${TARGET}"
if [[ ${#EXTRA[@]} -gt 0 ]]; then
  PROMPT+=" ${EXTRA[*]}"
fi

echo "using $pick" >&2

run() {
  if [[ $DRY -eq 1 ]]; then
    printf '%q ' "$@"
    printf '\n'
    exit 0
  fi
  exec "$@"
}

LAB_ROOT="$(cd "$DIR/../.." && pwd)"
CODEX_HOME="${CODEX_HOME:-${HOME:-/tmp}/.codex}"

cd "$DIR"

case "$pick" in
  claude)
    run claude -p "$PROMPT"
    ;;
  grok)
    # -p must be last. A flag after it makes grok error with
    # "a value is required for --single".
    run grok --always-approve \
      --deny "Edit(${LAB_ROOT}/scripts/**)" \
      --deny "Edit(${LAB_ROOT}/work/**/tests/**)" \
      -p "$PROMPT"
    ;;
  opencode)
    if [[ $DRY -eq 1 ]]; then
      printf 'opencode run --dir %q --auto --command enhancer-loop -- --repo %q' "$DIR" "$TARGET"
      if [[ ${#EXTRA[@]} -gt 0 ]]; then
        printf ' %q' "${EXTRA[@]}"
      fi
      printf '\n'
      exit 0
    fi
    exec opencode run \
      --dir "$DIR" \
      --auto \
      --command enhancer-loop \
      -- \
      --repo "$TARGET" \
      "${EXTRA[@]}" \
      < /dev/null
    ;;
  codex)
    # The leading $ is load-bearing. Codex resolves $enhancer-loop as a skill.
    # Unescaped, the shell expands $enhancer to nothing and the skill never
    # resolves.
    local_prompt="\$enhancer-loop --repo ${TARGET}"
    if [[ ${#EXTRA[@]} -gt 0 ]]; then
      local_prompt+=" ${EXTRA[*]}"
    fi
    if [[ $DRY -eq 1 ]]; then
      printf 'codex exec -s workspace-write -c sandbox_workspace_write.network_access=true --add-dir %q --add-dir %q %q\n' \
        "$TARGET" "$CODEX_HOME" "$local_prompt"
      exit 0
    fi
    exec codex exec \
      -s workspace-write \
      -c sandbox_workspace_write.network_access=true \
      --add-dir "$TARGET" \
      --add-dir "$CODEX_HOME" \
      "$local_prompt" \
      < /dev/null
    ;;
esac
