#!/usr/bin/env python3
"""Write and read the local-test receipt.

The push gate reads only this file. It is the evidence that the suite ran
green against exactly the tree you are about to push.

A receipt proves three things or it proves nothing:

1. The suite passed.
2. It ran against this tree, not an older one.
3. It ran after the newest source edit.

Usage:
    python scripts/receipt.py write <repo> <exit_code> [failed_id ...]
    python scripts/receipt.py check <repo>
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

RECEIPT = ".harness/receipt.json"
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "reports", ".harness", ".pytest_cache"}


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    return out.stdout.strip()


def tracked_files(repo: Path) -> list[Path]:
    """Tracked files, plus untracked ones git does not ignore."""
    listed = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard")
    paths = []
    for line in listed.splitlines():
        path = repo / line
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.relative_to(repo).parts):
            continue
        paths.append(path)
    return sorted(paths)


def tree_hash(repo: Path) -> tuple[str, float]:
    """Hash the working tree's content, and find the newest edit time.

    Content, not `git status`. A change that is staged, unstaged, or untracked
    all count the same, because all three reach the remote on a push.
    """
    digest = hashlib.sha256()
    newest = 0.0
    for path in tracked_files(repo):
        digest.update(str(path.relative_to(repo)).encode())
        digest.update(path.read_bytes())
        newest = max(newest, path.stat().st_mtime)
    return digest.hexdigest(), newest


def read_junit_failures(repo: Path) -> tuple[list[str], bool]:
    """Read failed ids from the repo's junit report.

    Returns (failed_ids, usable). `usable` is False when there is no readable
    report, which the caller must treat as "no evidence", never as "clean".
    """
    path = repo / "reports" / "junit.xml"
    if not path.exists():
        return [], False
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return [], False
    failed = []
    seen_any = False
    for case in root.iter("testcase"):
        seen_any = True
        tags = {child.tag for child in case}
        if tags & {"failure", "error"} or case.get("failure") is not None:
            name = case.get("name", "")
            cls = case.get("classname", "")
            failed.append(f"{cls}::{name}" if cls else name)
    return failed, seen_any


def write(repo: Path, exit_code: int, failed_ids: list[str] | None = None) -> dict:
    """Record one test run. Green requires a zero exit AND a readable report."""
    tree, newest = tree_hash(repo)
    report_failures, report_usable = read_junit_failures(repo)
    if failed_ids is None:
        failed_ids = report_failures
    green = exit_code == 0 and report_usable and not report_failures
    payload = {
        "version": 1,
        "head": _git(repo, "rev-parse", "HEAD") or None,
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD") or None,
        "tree_hash": tree,
        "newest_source_mtime": newest,
        "written_at": time.time(),
        "exit_code": exit_code,
        "green": green,
        "report_usable": report_usable,
        "failed_ids": failed_ids,
    }
    target = repo / RECEIPT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def check(repo: Path) -> tuple[bool, str]:  # noqa: PLR0911
    """Return (allowed, reason). The reason is what the room reads.

    One return per way a receipt can fail to prove its case. Collapsing them
    would save a branch and cost the reader the reason.
    """
    target = repo / RECEIPT
    if not target.exists():
        return False, "No receipt. The test suite has not run against this tree."
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False, "The receipt is unreadable. Treating that as a failure, not a pass."

    if not payload.get("report_usable", True):
        return False, "No readable test report. No evidence is not the same as clean."

    if not payload.get("green"):
        failed = payload.get("failed_ids") or []
        count = len(failed) or "some"
        detail = f"\n  first failure: {failed[0]}" if failed else ""
        return False, f"Last run: FAILED ({count} tests).{detail}"

    tree, newest = tree_hash(repo)
    if payload.get("tree_hash") != tree:
        return False, "The tree changed after the last green run. The receipt is stale."
    if newest > payload.get("written_at", 0):
        return False, "A source file is newer than the receipt. Re-run the tests."
    return True, "Receipt is green and matches this tree."


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    action, repo = argv[1], Path(argv[2]).resolve()
    if action == "write":
        exit_code = int(argv[3]) if len(argv) > 3 else 0
        payload = write(repo, exit_code, argv[4:] or None)
        state = "green" if payload["green"] else "red"
        print(f"receipt: {state} for {payload['tree_hash'][:12]} on {payload['branch']}")
        return 0
    if action == "check":
        allowed, reason = check(repo)
        print(reason)
        return 0 if allowed else 1
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
