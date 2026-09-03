"""The entry point, and the separation that lets it run with no SDK."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import harness
import load_agents
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
    for name in ("SPEC.md", "HOW_TO_RUN.md"):
        prose = (FOLDER / name).read_text(encoding="utf-8")
        for named in re.findall(r"task ([a-z][a-z0-9-]*)", prose):
            assert named in declared, f"{name} names `task {named}`, the Taskfile does not"


def test_setup_creates_a_local_venv_and_how_to_run_exists():
    """Homebrew Python is PEP 668. pip into the activated venv is how a live
    demo died. task setup creates .venv in this folder."""
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    how = FOLDER / "HOW_TO_RUN.md"
    assert ".venv" in taskfile
    assert "venv you activated" not in taskfile
    assert how.is_file()
    text = how.read_text(encoding="utf-8")
    assert "venv you activated" not in text
    assert "task setup" in text
    assert "--doer sdk" in text or "this folder owns the loop" in text.lower()


def test_the_judge_schema_does_not_name_a_gate():
    """Python owns gates.decide. A schema that names a gate invites the model
    to pick one."""
    blob = json.dumps(load_agents.JUDGE_SCHEMA).lower()
    for banned in ("gate", "pass", "retry", "escalate", "rubric", "score"):
        assert banned not in blob, banned
    props = load_agents.JUDGE_SCHEMA["schema"]["properties"]
    assert "done" in props
    assert "issues" in props


def test_the_planner_prompt_matches_the_steps_schema():
    """kind/path/goal would be rejected the day the planner runs."""
    text = (FOLDER / "plugin" / "agents" / "implementer-planner.md").read_text(encoding="utf-8")
    assert '"role": "test_implementer"' in text
    assert '"role": "code_implementer"' in text
    assert "kind" not in text.split("Output contract", 1)[-1] or '"kind"' not in text
    body = text.split("Output contract", 1)[-1]
    assert '"kind"' not in body
    assert '"goal"' not in body
    assert "validation" in body


def test_the_judge_prompt_matches_the_schema():
    text = (FOLDER / "plugin" / "agents" / "implementer-judge.md").read_text(encoding="utf-8")
    body = text.split("Output contract", 1)[-1]
    assert '"rows"' not in body
    assert '"done"' in body
    assert '"issues"' in body


def test_no_two_modules_are_byte_identical():
    seen: dict[bytes, str] = {}
    for path in sorted(FOLDER.glob("*.py")):
        blob = path.read_bytes()
        assert blob not in seen, f"{path.name} is a byte copy of {seen[blob]}"
        seen[blob] = path.name


def test_the_e2e_path_does_not_import_the_sibling_folder():
    text = (FOLDER / "e2e_t001.py").read_text(encoding="utf-8")
    assert "sol2_implementer_deep_agents" not in text
    assert "sys.path" not in text or "_flat_modules" not in text
