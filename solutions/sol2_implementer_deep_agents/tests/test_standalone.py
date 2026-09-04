from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."


def test_no_shared_loop_imports():
    """CLAUDE.md forbids a shared library. Duplication is the point, because a
    five hour audience should not have to learn an abstraction first.

    Scope matters as much as the pattern. `task setup` builds a `.venv` in
    this folder, and an unscoped walk reads every installed package, where
    `from ..` is an ordinary relative import. That made this assertion fail
    on the dependencies rather than on this folder's own source.
    """
    out = subprocess.run(
        ["grep", "-rnE", FORBIDDEN, "--include=*.py",
         "--exclude-dir=.venv", "--exclude-dir=.cache", "--exclude-dir=work", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hits = [line for line in out.stdout.split("\n") if line and "/tests/" not in line]
    assert not hits, "\n".join(hits)


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
