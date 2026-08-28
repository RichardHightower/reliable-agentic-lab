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


def test_no_loops_import():
    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []


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
