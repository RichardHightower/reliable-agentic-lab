from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import gates
import loop

ROOT = Path(__file__).resolve().parents[1]


def test_failure_summary_names_tests():
    run = SimpleNamespace(
        junit=SimpleNamespace(failed_ids={"tests.test_x::test_y"}),
        output="ValueError: boom",
    )
    text = loop.summarize_failure(run)
    assert "test_y" in text
    assert "ValueError" in text


def test_same_failing_ids_escalate():
    d = gates.decide(
        passed=False,
        iteration=2,
        budget=3,
        signature=("a",),
        previous_signature=("a",),
    )
    assert d.gate == gates.ESCALATE


FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."


def test_no_loops_import():
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


def test_table_only():
    proc = subprocess.run(
        ["python3", "loop.py", "--table-only", "--repo", "/tmp/no-such-crm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "judge" in proc.stdout
