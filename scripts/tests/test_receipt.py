"""Checks for the local-test receipt.

The push gate trusts this file and nothing else, so every way it can lie needs
a check.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.receipt import check, write


def put_junit(repo: Path, *, failed: list[str] | None = None) -> None:
    """Write a junit report into the repo. Evidence the receipt can read."""
    failed = failed or []
    cases = (
        "".join(
            f'<testcase classname="tests.t" name="{n}"><failure>boom</failure></testcase>'
            for n in failed
        )
        + '<testcase classname="tests.t" name="ok"/>'
    )
    out = repo / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "junit.xml").write_text(
        f'<testsuites><testsuite name="pytest" tests="{len(failed) + 1}" '
        f'failures="{len(failed)}" errors="0" skipped="0">{cases}</testsuite></testsuites>'
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def test_no_receipt_blocks(repo: Path):
    allowed, reason = check(repo)
    assert allowed is False
    assert "No receipt" in reason


def test_a_green_receipt_allows(repo: Path):
    put_junit(repo)
    write(repo, 0)
    allowed, reason = check(repo)
    assert allowed is True, reason


def test_a_red_receipt_blocks_and_names_the_failure(repo: Path):
    put_junit(repo, failed=["test_model_has_optional_due_date"])
    write(repo, 1)
    allowed, reason = check(repo)
    assert allowed is False
    assert "FAILED (1 tests)" in reason
    assert "test_model_has_optional_due_date" in reason


def test_editing_a_file_after_a_green_run_blocks(repo: Path):
    put_junit(repo)
    write(repo, 0)
    assert check(repo)[0] is True
    time.sleep(0.01)
    (repo / "app.py").write_text("x = 2\n")
    allowed, reason = check(repo)
    assert allowed is False
    assert "stale" in reason or "newer" in reason


def test_a_new_untracked_file_blocks(repo: Path):
    """An untracked file still reaches the remote on a push. It must count."""
    put_junit(repo)
    write(repo, 0)
    (repo / "sneaky.py").write_text("import os\n")
    allowed, _ = check(repo)
    assert allowed is False


def test_an_unreadable_receipt_blocks(repo: Path):
    put_junit(repo)
    write(repo, 0)
    (repo / ".harness" / "receipt.json").write_text("{ not json")
    allowed, reason = check(repo)
    assert allowed is False
    assert "unreadable" in reason


def test_the_receipt_records_the_branch_and_head(repo: Path):
    put_junit(repo)
    payload = write(repo, 0)
    assert payload["green"] is True
    assert payload["head"]
    assert payload["tree_hash"]
    stored = json.loads((repo / ".harness" / "receipt.json").read_text())
    assert stored["tree_hash"] == payload["tree_hash"]


def test_a_zero_exit_with_no_report_is_not_green(repo: Path):
    """A command that exits 0 without running tests is the silent-skip bug."""
    payload = write(repo, 0)
    assert payload["green"] is False
    allowed, reason = check(repo)
    assert allowed is False
    assert "No readable test report" in reason
