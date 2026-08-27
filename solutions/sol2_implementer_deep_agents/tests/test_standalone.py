from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_shared_loop_imports():
    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []


def test_table_only_without_repo():
    proc = subprocess.run(
        ["python3", "harness.py", "--table-only", "--repo", "/tmp/does-not-exist-crm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "judge" in proc.stdout
    assert "no" in proc.stdout.lower() or "writes" in proc.stdout.lower() or "judge" in proc.stdout
