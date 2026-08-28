#!/usr/bin/env bash
# Forget test tickets so the next create-test-tickets makes new GitHub issues.
#
# create-test-tickets reopens an issue whose title still starts with [Txxx].
# Closing is not enough. This script rewrites each matching title to
# [retired-Txxx-<timestamp>] ... and then closes it, so a later seed cannot
# find it. It also drops github_issue from the ticket files, deletes enhancer
# state, restores tracked tickets from git, and removes the T900/T901/T902
# seed files so they get rewritten as fresh drafts.
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

unstamp() {
  local path="$1"
  local tmp
  tmp="$(mktemp)"
  awk '/^github_issue:/ {next} {print}' "$path" > "$tmp"
  mv "$tmp" "$path"
}

retire() {
  local num="$1"
  local id="$2"
  local old new state
  old="$(gh issue view "$num" --repo "$REPO" --json title,state --jq '.title + "\t" + .state' 2>/dev/null || true)"
  if [ -z "$old" ]; then
    echo "skip #$num (gone)"
    return
  fi
  state="${old##*$'\t'}"
  old="${old%$'\t'*}"
  case "$old" in
    "[retired-"*)
      if [ "$state" != "CLOSED" ]; then
        gh issue close "$num" --repo "$REPO" --reason "not planned" >/dev/null
        echo "$id -> closed already-retired #$num"
      else
        echo "$id -> already retired #$num"
      fi
      return
      ;;
  esac
  if [ -z "$id" ]; then
    id="$(printf '%s' "$old" | sed -n 's/^\[\([^]]\{1,\}\)\] .*/\1/p')"
  fi
  if [ -z "$id" ]; then
    id="ticket"
  fi
  new="[retired-${id}-${STAMP}] ${old}"
  gh issue edit "$num" --repo "$REPO" --title "$new" >/dev/null
  if [ "$state" != "CLOSED" ]; then
    gh issue close "$num" --repo "$REPO" --reason "not planned" >/dev/null
  fi
  echo "$id -> retired #$num as $new"
}

echo "retiring test issues on $REPO"

# Every open or closed issue whose title still starts with [T<digits>].
while IFS=$'\t' read -r num title; do
  [ -n "$num" ] || continue
  id="$(printf '%s' "$title" | sed -n 's/^\[\(T[0-9]\{1,\}\)\] .*/\1/p')"
  retire "$num" "$id"
done < <(
  gh issue list --repo "$REPO" --state all --limit 200 --json number,title \
    | jq -r '.[] | select(.title | test("^\\[T[0-9]+\\] ")) | [.number, .title] | @tsv'
)

# Local files: drop the stamped issue number and enhancer state.
shopt -s nullglob
for path in "$TICKETS"/T*.md; do
  case "$path" in
    *.ready.md|*.enhancer-candidate.md) continue ;;
  esac
  id="$(awk '/^id:/{print $2; exit}' "$path")"
  if grep -q '^github_issue:' "$path"; then
    unstamp "$path"
    echo "$id -> dropped github_issue from $path"
  fi
  rm -f "$TARGET/.harness/last-enhancer-${id}.json"
done
rm -f "$TARGET/.harness"/last-enhancer-*.json

# Restore tracked tickets (T001 and any others in git) to their last commit.
if git -C "$TARGET" ls-files --error-unmatch tickets >/dev/null 2>&1; then
  git -C "$TARGET" checkout -- tickets >/dev/null
  echo "restored tickets/ from git"
fi

# Seed files are written by create-test-tickets. Delete them so the next
# seed rewrites fresh drafts even if git did not know about them.
for id in T900 T901 T902; do
  rm -f "$TICKETS/${id}.md" "$TICKETS/${id}.enhancer-candidate.md"
done

echo
echo "retired. Next: task create-test-tickets"
echo "open issues on $REPO:"
gh issue list --repo "$REPO" --state open
