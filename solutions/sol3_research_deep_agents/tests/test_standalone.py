"""This folder is standalone. Copy it somewhere else and it runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."


def test_no_shared_engine_imports():
    """CLAUDE.md forbids a shared library. Duplication is the point, because a
    five hour audience should not have to learn an abstraction first."""
    out = subprocess.run(
        ["grep", "-rnE", FORBIDDEN, "--include=*.py", "--exclude-dir=.venv", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hits = [line for line in out.stdout.split("\n") if line and "/tests/" not in line]
    assert not hits, "\n".join(hits)


def test_every_module_imports_with_no_sdk():
    """No deepagents, no langchain, no key, no network."""
    names = sorted(path.stem for path in ROOT.glob("*.py") if path.stem not in ("__init__",))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import importlib\n"
        f"for name in {names!r}: importlib.import_module(name)\n"
        "assert 'deepagents' not in sys.modules\n"
        "assert 'langchain' not in sys.modules\n"
        "print('ok')"
    )
    out = subprocess.run(
        ["python3", "-c", code], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_the_check_scripts_pass_their_own_assertions():
    """`task checks` runs these. A demo that drifts from the code is worse than
    no demo."""
    for module in ("evidence", "paper_check", "publish", "diagrams", "mcp_tools", "charts"):
        out = subprocess.run(
            ["python3", f"{module}.py", "--demo"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert out.returncode == 0, f"{module}: {out.stderr}"
        assert "passed" in out.stdout, module


def test_the_folder_carries_its_own_theme():
    """It copies the theme rather than reaching up two levels, or it is not
    standalone."""
    assert (ROOT / "themes" / "spillwave-light.yaml").exists()
    assert (ROOT / "themes" / "mermaid.json").exists()


def test_every_model_facing_role_has_a_skill():
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    for name, role in roleplan.plan(None, "paper").items():
        if name == "orchestrator":
            continue
        assert (ROOT / "skills" / name / "SKILL.md").exists(), name
        assert role.purpose
