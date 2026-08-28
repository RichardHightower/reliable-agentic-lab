#!/usr/bin/env bash
# Fill solutions/sol1_enhancer/config.json from CRM_OWNER / CRM_REPO / GITHUB_REPO.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
SOL1="$ROOT/solutions/sol1_enhancer"
EXAMPLE="$SOL1/config.json.example"
OUT="$SOL1/config.json"

OWNER="${CRM_OWNER:-}"
REPO="${CRM_REPO:-northwind-field-crm}"
if [[ -z "$OWNER" && -n "${GITHUB_REPO:-}" ]]; then
  OWNER="${GITHUB_REPO%%/*}"
  REST="${GITHUB_REPO#*/}"
  if [[ -n "$REST" && "$REST" != "$GITHUB_REPO" ]]; then
    REPO="$REST"
  fi
fi
if [[ -z "$OWNER" || "$OWNER" == "your-github-username" ]]; then
  echo "set CRM_OWNER or GITHUB_REPO=owner/northwind-field-crm" >&2
  exit 1
fi

if [[ ! -f "$EXAMPLE" ]]; then
  echo "missing $EXAMPLE" >&2
  exit 1
fi

python3 - "$EXAMPLE" "$OUT" "$OWNER" "$REPO" <<'PY'
import json, sys
example, out, owner, repo = sys.argv[1:5]
data = json.loads(open(example, encoding="utf-8").read())
data["fork_owner"] = owner
data["repo_name"] = repo
data.setdefault("poll_interval", "10m")
data.setdefault("debug", False)
open(out, "w", encoding="utf-8").write(json.dumps(data, indent=2) + "\n")
print(f"wrote {out} fork_owner={owner} repo_name={repo}")
PY
