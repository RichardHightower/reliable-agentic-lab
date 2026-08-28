"""The entry point, and the separation that lets it run with no SDK."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import harness
import roleplan

FOLDER = Path(__file__).resolve().parents[1]


def test_the_table_prints_as_a_subprocess_with_no_sdk():
    """A fresh interpreter, so an SDK imported by another test cannot help."""
    proc = subprocess.run(
        [sys.executable, "harness.py", "--table-only"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "code_implementer" in proc.stdout
    assert "judge             no" in proc.stdout


def test_importing_harness_pulls_in_neither_the_adapter_nor_the_sdk():
    """The lazy imports are load-bearing, not tidiness."""
    proc = subprocess.run(
        [sys.executable, "-c", "import harness, sys; print(sorted(sys.modules))"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "'claude_agent_sdk'" not in proc.stdout


def test_every_module_imports_with_no_sdk():
    """A folder that needs the SDK to import is not standalone."""
    names = sorted(p.stem for p in FOLDER.glob("*.py"))
    script = "import sys; " + "; ".join(f"import {n}" for n in names) + "; print('ok')"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_the_cast_is_read_from_the_table_not_restated(contract):
    assert harness.cast(contract) == roleplan.plan(contract, "implementer")


def test_no_module_imports_a_shared_engine():
    """The repo rule. Copy the file, do not reach for a package."""
    for path in FOLDER.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("from loops", "import loops")), path.name
            assert not stripped.startswith(("from solutions", "import solutions")), path.name
            assert not stripped.startswith("from .."), path.name


def test_the_docs_do_not_promise_a_task_that_does_not_exist():
    """SPEC.md told the reader to run `task setup` when the Taskfile had no
    such target, and called `task test` a set of assertions when it printed a
    table."""
    import re  # noqa: PLC0415

    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    declared = set(re.findall(r"^  (\w[\w-]*):$", taskfile, re.M))
    spec = (FOLDER / "SPEC.md").read_text(encoding="utf-8")
    for named in re.findall(r"task ([a-z][a-z-]*)", spec):
        assert named in declared, f"SPEC.md names `task {named}`, the Taskfile does not"
