from __future__ import annotations

import sys
from pathlib import Path

CRM_ROOT = Path(__file__).resolve().parents[2] / "crm"
if str(CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(CRM_ROOT))
