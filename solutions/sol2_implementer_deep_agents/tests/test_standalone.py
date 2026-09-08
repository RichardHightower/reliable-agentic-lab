from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."


def test_no_shared_loop_imports():
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


def test_no_two_modules_are_byte_identical():
    seen: dict[bytes, str] = {}
    for path in sorted(ROOT.glob("*.py")):
        blob = path.read_bytes()
        assert blob not in seen, f"{path.name} is a byte copy of {seen[blob]}"
        seen[blob] = path.name


def test_table_only_without_repo():
    proc = subprocess.run(
        ["python3", "harness.py", "--table-only", "--repo", "/tmp/does-not-exist-crm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "judge" in proc.stdout
    assert "no" in proc.stdout.lower() or "writes" in proc.stdout.lower() or "judge" in proc.stdout


def test_cleanup_flag_reaches_implementer_run(monkeypatch, target_repo):
    """A4 (#431). The worktree mechanics are implementer.py's; this only
    proves harness.py's own --cleanup flag is not dropped on the way to it."""
    import harness
    import implementer

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"rubric": "", "gate": "pass", "reason": "ok"}

    monkeypatch.setattr(implementer, "run", fake_run)

    exit_code = harness.main(["--repo", str(target_repo), "--doer", "none", "--cleanup"])

    assert captured.get("cleanup") is True
    assert exit_code == 0


def test_main_maps_gate_to_exit_code(monkeypatch, target_repo):
    """A5 (#432 #434). 0 pass, 2 escalate, 1 crash. harness.main mirrors
    implementer.main's mapping exactly, without repeating implementer.run's
    own worktree mechanics."""
    import harness
    import implementer

    monkeypatch.setattr(
        implementer, "run", lambda **_kw: {"rubric": "", "gate": "pass", "reason": "ok"}
    )
    assert harness.main(["--repo", str(target_repo), "--doer", "none"]) == 0

    monkeypatch.setattr(
        implementer,
        "run",
        lambda **_kw: {"rubric": "", "gate": "escalate", "reason": "red gate"},
    )
    assert harness.main(["--repo", str(target_repo), "--doer", "none"]) == 2

    def fake_crash(**_kw):
        raise implementer.ContractError("boom")

    monkeypatch.setattr(implementer, "run", fake_crash)
    assert harness.main(["--repo", str(target_repo), "--doer", "none"]) == 1
