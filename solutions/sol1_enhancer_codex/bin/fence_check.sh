#!/usr/bin/env bash
# Is the orchestrator's sandbox real?
#
# `codex exec -s workspace-write` normally refuses a write outside the
# workspace. It stops refusing when the project is marked
# `trust_level = "trusted"` in ~/.codex/config.toml. A trusted project turns
# the fence off silently: no warning, no log line, the write just works.
#
# That does not weaken the judge and the doer. Those run `-s read-only`
# through bin/role.sh, and read-only holds either way. It does mean the
# orchestrator is unfenced, so run this once before you demo the sandbox.
set -euo pipefail

CONFIG="${CODEX_HOME:-$HOME/.codex}/config.toml"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$CONFIG" ]; then
  echo "no $CONFIG. Nothing marks this project trusted. The fence is on."
  exit 0
fi

python3 - "$CONFIG" "$HERE" <<'PY'
import re, sys
from pathlib import Path

config, here = Path(sys.argv[1]).read_text(), Path(sys.argv[2]).resolve()

# [projects."<path>"] followed, before the next section, by a trust_level.
trusted = {
    Path(path)
    for path, body in re.findall(
        r'^\[projects\."([^"]+)"\]\n(.*?)(?=^\[|\Z)', config, re.M | re.S
    )
    if re.search(r'^\s*trust_level\s*=\s*"trusted"', body, re.M)
}

hits = [p for p in (here, *here.parents) if p in trusted]
if hits:
    print(f"TRUSTED: {hits[0]}")
    print("The orchestrator's workspace-write fence is OFF for this project.")
    print("Codex will let it write anywhere. The judge and the doer are")
    print("still jailed: bin/role.sh runs them -s read-only, which holds.")
    print("")
    print("To demo a real orchestrator fence, drop that [projects] block")
    print("from your config, or add --ignore-user-config to the run task.")
    sys.exit(1)

print("The fence is on. No trusted [projects] entry covers this folder.")
PY
