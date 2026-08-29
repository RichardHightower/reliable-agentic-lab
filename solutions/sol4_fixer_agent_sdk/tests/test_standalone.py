"""Folder hygiene. This folder is standalone or it is not."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import load_agents
import pytest

FOLDER = Path(__file__).resolve().parents[1]


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


def test_the_table_prints_as_a_subprocess_with_no_sdk():
    proc = subprocess.run(
        [sys.executable, "loop.py", "--table-only", "--repo", "/nope/no-such-crm"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "judge             no" in proc.stdout
    assert "planner" not in proc.stdout, "the fixer cast has three roles, not five"


def test_no_module_imports_a_shared_engine():
    for path in FOLDER.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("from loops", "import loops")), path.name
            assert not stripped.startswith(("from solutions", "import solutions")), path.name
            assert not stripped.startswith("from .."), path.name


def test_no_two_modules_are_byte_identical():
    """`loop_roles.py` and `write_scope.py` were the same 180 lines, reached
    through three import names."""
    seen: dict[bytes, str] = {}
    for path in sorted(FOLDER.glob("*.py")):
        blob = path.read_bytes()
        assert blob not in seen, f"{path.name} is a byte copy of {seen[blob]}"
        seen[blob] = path.name


def test_the_docs_name_only_tasks_that_exist():
    import re  # noqa: PLC0415

    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    declared = set(re.findall(r"^  (\w[\w-]*):$", taskfile, re.M))
    for name in ("SPEC.md", "HOW_TO_RUN.md"):
        prose = (FOLDER / name).read_text(encoding="utf-8")
        for named in re.findall(r"task ([a-z][a-z-]*)", prose):
            assert named in declared, f"{name} names `task {named}`, the Taskfile does not"


def test_asking_for_a_missing_fixture_says_which_file():
    """`--research` defaulted to `fixture` and pointed at
    `fixtures/research.json`, a file this folder has never had, so the
    documented default could not run. The default is `off` now, and asking for
    the fixture names the file rather than failing somewhere deeper."""
    if (FOLDER / "fixtures" / "research.json").exists():
        pytest.skip("a fixture exists, so the guard has nothing to report")
    proc = subprocess.run(
        [sys.executable, "fixer.py", "--research", "fixture", "--repo", "/nope/no-such-crm"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "research.json" in proc.stderr
    assert "--research off" in proc.stderr


def test_setup_creates_a_local_venv_and_how_to_run_exists():
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    how = FOLDER / "HOW_TO_RUN.md"
    assert ".venv" in taskfile
    assert "venv you activated" not in taskfile
    assert how.is_file()
    text = how.read_text(encoding="utf-8")
    assert "venv you activated" not in text
    assert "task setup" in text
    assert "task clone" in text
    assert "task reset" in text


def test_the_judge_schema_does_not_name_a_gate():
    blob = json.dumps(load_agents.JUDGE_SCHEMA).lower()
    for banned in ("gate", "pass", "retry", "escalate", "rubric", "score"):
        assert banned not in blob, banned
    props = load_agents.JUDGE_SCHEMA["schema"]["properties"]
    assert "done" in props
    assert "issues" in props
