"""This folder is standalone. Copy it somewhere else and it runs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."


def test_no_shared_engine_imports():
    """CLAUDE.md forbids a shared library. Duplication is the point, because a
    five hour audience should not have to learn an abstraction first."""
    out = subprocess.run(
        ["grep", "-rnE", FORBIDDEN, "--include=*.py", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hits = [line for line in out.stdout.split("\n") if line and "/tests/" not in line]
    assert not hits, "\n".join(hits)


def test_every_module_imports_with_no_sdk():
    """No deepagents, no langchain, no key, no network."""
    names = sorted(path.stem for path in ROOT.glob("*.py") if path.stem != "__init__")
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import importlib\n"
        f"for name in {names!r}: importlib.import_module(name)\n"
        "assert 'deepagents' not in sys.modules\n"
        "assert 'langchain' not in sys.modules\n"
        "print('ok')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def _table(*args):
    return subprocess.run(
        [sys.executable, "loop.py", "--table-only", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_table_runs_with_no_clone_and_no_sdk():
    """SPEC.md tells a reader to run this before `task setup`, so it has to
    work before anything is installed or cloned."""
    out = _table("--repo", "/nope/no-such-crm")

    assert out.returncode == 0, out.stderr
    rows = {line.split()[0]: line for line in out.stdout.splitlines() if line and " " in line}
    assert set(rows) >= {"orchestrator", "code_implementer", "judge"}
    assert "planner" not in rows


def test_the_table_shows_the_judge_writing_nothing():
    """The one thing a reader checks by eye before building on this port."""
    out = _table("--repo", "/nope/no-such-crm")
    judge = next(line for line in out.stdout.splitlines() if line.startswith("judge"))
    assert judge.split()[1] == "no"
    assert "nothing" in judge


def test_the_table_imports_no_runtime():
    """`--table-only` must not drag in deepagents, langchain, or adapter."""
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import loop\n"
        "assert loop.main(['--table-only', '--repo', '/nope/no-such-crm']) == 0\n"
        "for name in ('deepagents', 'langchain', 'adapter'):\n"
        "    assert name not in sys.modules, name\n"
        "print('clean')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "clean" in out.stdout
