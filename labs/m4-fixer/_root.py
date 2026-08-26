"""Put the repo root on sys.path.

Your coding agent runs with its working directory set to one lab folder, so
`loops` is not importable. This file walks up until it finds the repo and fixes
that. A copy sits in every lab folder, because a copy needs no PYTHONPATH and a
shared import would need one.

    import _root  # noqa: F401
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "Taskfile.yml"


def find_root(start: Path | None = None) -> Path:
    """Walk up until a folder holds both the marker and the loop engine."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / MARKER).is_file() and (candidate / "loops").is_dir():
            return candidate
    raise RuntimeError(f"no repo root above {here}. Is {MARKER} missing?")


ROOT = find_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
