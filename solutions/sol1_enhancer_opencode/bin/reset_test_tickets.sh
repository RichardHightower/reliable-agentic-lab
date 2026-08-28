#!/usr/bin/env bash
# Forget test tickets so the next create-test-tickets makes new GitHub issues.
#
# create-test-tickets reopens an issue whose title starts with [Txxx] OR whose
# title equals the ticket H1. Closing is not enough. This script rewrites
# every matching title, open or closed, to [retired-Txxx-<timestamp>] ...,
# then closes it. It also drops github_issue from the ticket files, deletes
# enhancer state, restores tracked tickets from git, and removes T900/T901/T902
# so they get rewritten as fresh drafts.
set -euo pipefail

TARGET="${1:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$HERE/config.json"
TICKETS="${TARGET}/tickets"

if [ -z "$TARGET" ]; then
  echo "usage: reset_test_tickets.sh <target-repo-path>" >&2
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
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$TICKETS"

unstamp() {
  local path="$1"
  local tmp
  tmp="$(mktemp)"
  awk '/^github_issue:/ {next} {print}' "$path" > "$tmp"
  mv "$tmp" "$path"
}

id_of() {
  local path="$1"
  awk '/^id:/{print $2; exit}' "$path"
}

h1_of() {
  local path="$1"
  awk '/^# /{sub(/^# /,""); print; exit}' "$path"
}

retire() {
  local num="$1"
  local id="$2"
  local raw title state new
  raw="$(gh issue view "$num" --repo "$REPO" --json title,state --jq '[.title, .state] | @tsv' 2>/dev/null || true)"
  if [ -z "$raw" ]; then
    echo "skip #$num (gone)"
    return
  fi
  title="${raw%%$'\t'*}"
  state="${raw#*$'\t'}"
  case "$title" in
    "[retired-"*)
      if [ "$state" != "CLOSED" ]; then
        gh issue close "$num" --repo "$REPO" --reason "not planned" >/dev/null || true
        echo "$id -> closed already-retired #$num"
      else
        echo "$id -> already retired #$num"
      fi
      return
      ;;
  esac
  if [ -z "$id" ]; then
    id="$(printf '%s' "$title" | sed -n 's/^\[\(T[0-9]\{1,\}\)\] .*/\1/p')"
  fi
  if [ -z "$id" ]; then
    id="ticket"
  fi
  new="[retired-${id}-${STAMP}] ${title}"
  gh issue edit "$num" --repo "$REPO" --title "$new" \
    --remove-label enhanced --remove-label ready --remove-label needs-human \
    >/dev/null 2>&1 || gh issue edit "$num" --repo "$REPO" --title "$new" >/dev/null
  if [ "$state" != "CLOSED" ]; then
    gh issue close "$num" --repo "$REPO" --reason "not planned" >/dev/null
  fi
  echo "$id -> retired #$num as $new"
}

collect_h1s() {
  local path h1
  shopt -s nullglob
  for path in "$TICKETS"/T*.md; do
    case "$path" in
      *.ready.md|*.enhancer-candidate.md) continue ;;
    esac
    h1="$(h1_of "$path")"
    if [ -n "$h1" ]; then
      printf '%s\n' "$h1"
    fi
  done
  # Seed titles, in case the files are not on disk yet.
  printf '%s\n' \
    "Search crashes on an empty query" \
    "Add a notes field to the customer page" \
    "Export tasks to CSV" \
    "Sales tasks need due dates"
}

echo "retiring test issues on $REPO"

H1S="$(collect_h1s | awk 'NF && !seen[$0]++')"
H1_JSON="$(printf '%s\n' "$H1S" | jq -R . | jq -s .)"

# 1. Numbers stamped on local files.
shopt -s nullglob
for path in "$TICKETS"/T*.md; do
  case "$path" in
    *.ready.md|*.enhancer-candidate.md) continue ;;
  esac
  num="$(awk '/^github_issue:/{print $2; exit}' "$path")"
  id="$(id_of "$path")"
  if [ -n "$num" ]; then
    retire "$num" "$id"
  fi
done

# 2. Every GitHub issue create-test-tickets could reopen: title starts with
#    [Txxx] OR title equals a ticket H1. Closed ones too. Same matcher.
MATCHES="$(mktemp)"
{
  gh issue list --repo "$REPO" --state open --limit 500 --json number,title
  gh issue list --repo "$REPO" --state closed --limit 500 --json number,title
} | jq -s -r --argjson h1s "$H1_JSON" '
      add
      | unique_by(.number)
      | .[]
      | .title |= gsub("^\\s+|\\s+$";"")
      | select(.title | startswith("[retired-") | not)
      | select(
          (.title | test("^\\[T[0-9]+\\] "))
          or (.title as $t | $h1s | index($t) != null)
        )
      | [.number, .title]
      | @tsv
    ' > "$MATCHES"
while IFS=$'\t' read -r num title; do
  [ -n "$num" ] || continue
  id="$(printf '%s' "$title" | sed -n 's/^\[\(T[0-9]\{1,\}\)\] .*/\1/p')"
  case "$title" in
    "Search crashes on an empty query"|\[T900\]*) id="${id:-T900}" ;;
    "Add a notes field to the customer page"|\[T901\]*) id="${id:-T901}" ;;
    "Export tasks to CSV"|\[T902\]*) id="${id:-T902}" ;;
    "Sales tasks need due dates"|\[T001\]*) id="${id:-T001}" ;;
  esac
  if [ -z "$id" ]; then
    for path in "$TICKETS"/T*.md; do
      case "$path" in *.ready.md|*.enhancer-candidate.md) continue ;; esac
      if [ "$(h1_of "$path")" = "$title" ]; then
        id="$(id_of "$path")"
        break
      fi
    done
  fi
  retire "$num" "${id:-ticket}"
done < "$MATCHES"
rm -f "$MATCHES"

# Local files: drop the stamped issue number and enhancer state.
for path in "$TICKETS"/T*.md; do
  case "$path" in
    *.ready.md|*.enhancer-candidate.md) continue ;;
  esac
  id="$(id_of "$path")"
  if grep -q '^github_issue:' "$path"; then
    unstamp "$path"
    echo "$id -> dropped github_issue from $path"
  fi
  rm -f "$TARGET/.harness/last-enhancer-${id}.json"
done
rm -f "$TARGET/.harness"/last-enhancer-*.json

# Restore tracked tickets, then drop github_issue again. git checkout would
# otherwise put the stamped number back and the next seed would reopen it.
if git -C "$TARGET" ls-files --error-unmatch tickets >/dev/null 2>&1; then
  git -C "$TARGET" checkout -- tickets >/dev/null
  echo "restored tickets/ from git"
fi
for path in "$TICKETS"/T*.md; do
  case "$path" in
    *.ready.md|*.enhancer-candidate.md) continue ;;
  esac
  if grep -q '^github_issue:' "$path"; then
    unstamp "$path"
    echo "$(id_of "$path") -> dropped github_issue after git restore"
  fi
done

for id in T900 T901 T902; do
  rm -f "$TICKETS/${id}.md" "$TICKETS/${id}.enhancer-candidate.md"
done

echo
echo "retired. Next: task create-test-tickets"
echo "open issues on $REPO:"
gh issue list --repo "$REPO" --state open
