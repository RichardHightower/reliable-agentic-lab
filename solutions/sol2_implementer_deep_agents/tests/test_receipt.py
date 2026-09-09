"""One test per branch of receipt.check.

The push gate trusts this file's verdict and nothing else, so every way it
can be wrong needs a test: no receipt, a receipt that will not parse, a run
with no evidence, a run that failed, a receipt for a different tree, a
receipt older than the source, and the one true green path.

Copied from `scripts/tests/test_receipt.py`, not imported. `receipt.py` is a
flat module duplicated in every `solutions/sol2_*` port, and this port's
tests must not reach into a sibling folder.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from receipt import check, write


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)
    return path


def _put_junit(repo: Path, *, failed: list[str] | None = None) -> None:
    """Write a junit report a real run would have produced.

    `receipt.write` reads this to decide `report_usable` and `failed_ids`.
    """
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
    return _git_repo(tmp_path / "repo")


def test_no_receipt_denies(repo: Path):
    allowed, reason = check(repo)
    assert allowed is False
    assert "No receipt" in reason


def test_unreadable_receipt_denies(repo: Path):
    _put_junit(repo)
    write(repo, 0)
    (repo / ".harness" / "receipt.json").write_text("{ not json")
    allowed, reason = check(repo)
    assert allowed is False
    assert "unreadable" in reason


def test_a_zero_exit_with_no_report_is_not_green(repo: Path):
    """A command that exits 0 without running tests is the silent-skip bug."""
    write(repo, 0)
    allowed, reason = check(repo)
    assert allowed is False
    assert "No readable test report" in reason


def test_a_red_run_denies_and_names_the_failure(repo: Path):
    _put_junit(repo, failed=["test_thing"])
    write(repo, 1)
    allowed, reason = check(repo)
    assert allowed is False
    assert "FAILED (1 tests)" in reason
    assert "test_thing" in reason


def test_a_green_receipt_on_a_dirty_tree_is_denied(repo: Path):
    """The tree changed after the last green run. Stale evidence is a denial."""
    _put_junit(repo)
    write(repo, 0)
    time.sleep(0.01)
    (repo / "sneaky.py").write_text("import os\n", encoding="utf-8")
    allowed, reason = check(repo)
    assert allowed is False
    assert "changed after the last green run" in reason


def test_a_source_edit_newer_than_the_receipt_denies(repo: Path):
    """Same content, new mtime. The tree hash still matches, so this is the
    one case that proves the receipt checks mtime and not only content.
    """
    _put_junit(repo)
    write(repo, 0)
    time.sleep(0.01)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    allowed, reason = check(repo)
    assert allowed is False
    assert "newer than the receipt" in reason


def test_a_green_receipt_matching_this_tree_is_allowed(repo: Path):
    _put_junit(repo)
    write(repo, 0)
    allowed, reason = check(repo)
    assert allowed is True, reason
    assert "green" in reason
