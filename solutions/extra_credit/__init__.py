"""Extra credit. Event-driven wrappers around the PRD loops. Not Saturday.

One assignment per `s_ext_<n>_<name>` folder. `github_api.py` and `fake_github.py`
stay here, because more than one assignment reads them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The same default the loop CLIs use. `task setup` clones it here.
TARGET = ROOT / "work" / "northwind-field-crm"
