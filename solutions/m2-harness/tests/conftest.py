from __future__ import annotations

import sys
from pathlib import Path

M2_ROOT = Path(__file__).resolve().parents[1]
if str(M2_ROOT) not in sys.path:
    sys.path.insert(0, str(M2_ROOT))
