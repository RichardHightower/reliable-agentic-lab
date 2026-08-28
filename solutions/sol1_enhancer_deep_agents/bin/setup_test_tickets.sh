#!/usr/bin/env bash
# Write a few draft tickets into a target repo's tickets/ dir, one per kind
# (bug, ui, feature), so the enhancer loop has more to chew on than the real
# T001 fixture. Idempotent: skips a ticket file that already exists.
set -euo pipefail

TARGET="${1:-work/northwind-field-crm}"
TICKETS="$TARGET/tickets"

if [ ! -d "$TARGET" ]; then
  echo "no target repo at $TARGET. Run task clone first." >&2
  exit 1
fi

mkdir -p "$TICKETS"

write() {
  local id="$1"
  local path="$TICKETS/$id.md"
  if [ -f "$path" ]; then
    echo "skip $path (already exists)"
    return
  fi
  cat > "$path"
  echo "wrote $path"
}

write T900 <<'EOF'
---
id: T900
state: draft
loop: enhancer
---

# Search crashes on an empty query

Typing nothing into search and hitting enter causes an error.
EOF

write T901 <<'EOF'
---
id: T901
state: draft
loop: enhancer
---

# Add a notes field to the customer page

Reps want to jot down notes on a customer. Add a box for that.
EOF

write T902 <<'EOF'
---
id: T902
state: draft
loop: enhancer
---

# Export tasks to CSV

Reps want to pull their task list into a spreadsheet.
EOF
