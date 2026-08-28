"""Extra credit. Event-driven wrappers. Not Saturday.

One assignment per `s_ext_<n>_<name>` folder. `github_api.py` and `fake_github.py`
stay here, because more than one assignment reads them.

These wrappers call the matching `solutions/solN_*` folder. They do not import
a shared engine.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The same default the lab CLIs use. `task setup` clones it here.
TARGET = ROOT / "work" / "northwind-field-crm"
