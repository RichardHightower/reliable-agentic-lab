from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_shared_loop_imports():
    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import\|^from \.\.", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []


def test_no_two_modules_are_byte_identical():
    seen: dict[bytes, str] = {}
    for path in sorted(ROOT.glob("*.py")):
        blob = path.read_bytes()
        assert blob not in seen, f"{path.name} is a byte copy of {seen[blob]}"
        seen[blob] = path.name


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
