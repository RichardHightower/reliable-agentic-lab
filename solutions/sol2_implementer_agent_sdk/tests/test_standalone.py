"""C2 (#443). The one check `tests/test_harness.py` does not already cover.

The Deep Agents port's `tests/test_standalone.py` pins nine behaviors. Eight
of them already have a same-named test in this folder: `test_no_two_modules_
are_byte_identical` and the `--cleanup` / exit-mapping / resume / planner /
nonexistent-repo tests live in `tests/test_harness.py`, `test_no_shared_loop_
imports` is this folder's `test_no_module_imports_a_shared_engine`, and the
four doc checks live in `tests/test_docs.py`. Only `--table-only` ignoring a
nonexistent `--repo` had no test here. This file is that one addition, not a
copy of the other eight.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]


def test_table_only_without_repo():
    """`harness.main` catches `ContractError` and still prints the declared
    role table when `--table-only` is set, even though `--repo` names nothing
    on disk (`harness.py`'s `try/except ContractError` around `Contract`)."""
    proc = subprocess.run(
        [sys.executable, "harness.py", "--table-only", "--repo", "/tmp/does-not-exist-crm"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "judge" in proc.stdout
