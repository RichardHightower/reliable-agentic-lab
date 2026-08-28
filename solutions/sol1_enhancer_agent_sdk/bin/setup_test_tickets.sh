#!/usr/bin/env bash
# Seed draft tickets as GitHub issues.
#
# Writes markdown files under tickets/ AND opens a GitHub issue for each
# draft. Stamps github_issue into the file frontmatter.
#
# task run never creates issues. This task does.
#
# Idempotent: skips a file that already exists, reuses an existing issue
# whose title starts with [Txxx], reopens a closed issue for a still-draft
# ticket. Safe to run again.
set -euo pipefail

TARGET="${1:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$HERE/config.json"
TICKETS="${TARGET}/tickets"

if [ -z "$TARGET" ]; then
  echo "usage: setup_test_tickets.sh <target-repo-path>" >&2
  exit 1
fi
if [ ! -d "$TARGET/.git" ]; then
  echo "no target repo at $TARGET. Run task clone first." >&2
  exit 1
fi
if [ ! -f "$CONFIG" ]; then
  echo "copy config.json.example to config.json first, and fill in your GitHub username" >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "gh is required. Install the GitHub CLI and run gh auth login." >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to read config.json" >&2
  exit 1
fi

OWNER="$(jq -r .fork_owner "$CONFIG")"
REPO_NAME="$(jq -r .repo_name "$CONFIG")"
if [ -z "$OWNER" ] || [ "$OWNER" = "<your-github-username>" ] || [ "$OWNER" = "null" ]; then
  echo "set fork_owner in config.json to your GitHub username" >&2
  exit 1
fi
if [ -z "$REPO_NAME" ] || [ "$REPO_NAME" = "null" ]; then
  echo "set repo_name in config.json" >&2
  exit 1
fi
REPO="$OWNER/$REPO_NAME"

mkdir -p "$TICKETS"

write_file() {
  local id="$1"
  local path="$TICKETS/$id.md"
  if [ -f "$path" ]; then
    echo "skip $path (already exists)"
    return
  fi
  cat > "$path"
  echo "wrote $path"
}

stamp_issue() {
  local path="$1"
  local num="$2"
  local tmp
  tmp="$(mktemp)"
  if grep -q '^github_issue:' "$path"; then
    awk -v n="$num" '/^github_issue:/ {print "github_issue: " n; next} {print}' "$path" > "$tmp"
  else
    awk -v n="$num" '
      BEGIN {done=0}
      /^---$/ && NR>1 && done==0 {print "github_issue: " n; done=1}
      {print}
    ' "$path" > "$tmp"
  fi
  mv "$tmp" "$path"
}

ensure_labels() {
  gh label create enhanced --repo "$REPO" --color fbca04 --force >/dev/null
  gh label create ready --repo "$REPO" --color 0e8a16 --force >/dev/null
  gh label create needs-human --repo "$REPO" --color d93f0b --force >/dev/null
}

issue_state() {
  local num="$1"
  gh issue view "$num" --repo "$REPO" --json state --jq .state 2>/dev/null || true
}

find_issue() {
  local id="$1"
  local h1="$2"
  gh issue list --repo "$REPO" --state all --limit 100 --json number,title \
    | jq -r --arg id "$id" --arg h1 "$h1" '
        [ .[] | select((.title | startswith("[" + $id + "]")) or .title == $h1) | .number ]
        | first // empty
      '
}

open_issue_for() {
  local path="$1"
  local id title body num state url
  id="$(awk '/^id:/{print $2; exit}' "$path")"
  title="$(awk '/^# /{sub(/^# /,""); print; exit}' "$path")"
  body="$(awk '/^---$/{c++; next} c>=2' "$path")"
  num="$(awk '/^github_issue:/{print $2; exit}' "$path")"

  if [ -z "$num" ]; then
    num="$(find_issue "$id" "$title")"
  fi

  if [ -n "$num" ]; then
    state="$(issue_state "$num")"
    if [ "$state" = "CLOSED" ]; then
      gh issue reopen "$num" --repo "$REPO" >/dev/null
      echo "$id -> reopened #$num $REPO"
    else
      echo "$id -> existing #$num $REPO"
    fi
    stamp_issue "$path" "$num"
    return
  fi

  url="$(gh issue create --repo "$REPO" --title "[$id] $title" --body "$body")"
  num="${url##*/}"
  stamp_issue "$path" "$num"
  echo "$id -> created #$num $url"
}

write_file T900 <<'EOF'
---
id: T900
state: draft
loop: enhancer
---

# Search crashes on an empty query

Typing nothing into search and hitting enter causes an error.
EOF

write_file T901 <<'EOF'
---
id: T901
state: draft
loop: enhancer
---

# Add a notes field to the customer page

Reps want to jot down notes on a customer. Add a box for that.
EOF

write_file T902 <<'EOF'
---
id: T902
state: draft
loop: enhancer
---

# Export tasks to CSV

Reps want to pull their task list into a spreadsheet.
EOF

ensure_labels

shopt -s nullglob
for path in "$TICKETS"/T*.md; do
  case "$path" in
    *.ready.md|*.enhancer-candidate.md) continue ;;
  esac
  state="$(awk '/^state:/{print $2; exit}' "$path")"
  loop="$(awk '/^loop:/{print $2; exit}' "$path")"
  if [ "$state" != "draft" ] || [ "$loop" != "enhancer" ]; then
    echo "skip $path ($state / $loop)"
    continue
  fi
  open_issue_for "$path"
done

echo
echo "open issues on $REPO:"
gh issue list --repo "$REPO" --state open
