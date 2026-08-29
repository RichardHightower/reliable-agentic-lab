"""Drive implementer.run with a scripted backend. No model. No public CRM."""

from __future__ import annotations

import subprocess
from pathlib import Path

import contract as contract_mod
import doers
import implementer
from contract import CoverageReport, RunResult, SuiteReport

TASKFILE = """\
version: '3'
tasks:
  setup:
    cmds: [echo setup]
  test:
    cmds: [echo test]
  e2e:
    cmds: [echo e2e]
  lint:
    cmds: [echo lint]
  format-check:
    cmds: [echo format-check]
"""

LOOP_YML = """\
version: 1
roles:
  planner:
    write_allow: ["steps.jsonl"]
  test_implementer:
    write_allow: ["tests/**"]
    write_deny: ["app/**"]
  code_implementer:
    write_allow: ["app/**"]
    write_deny: ["tests/**"]
  judge:
    write_allow: []
rubric:
  coverage_floor: 80
  require_red: true
tickets:
  source: local
  path: tickets
budget:
  iterations: 3
  usd: 2.00
"""

TICKET = """\
---
id: T001
title: greet
state: ready
---

# T001 greet

## Acceptance criteria

- (AC-1) greet() returns hello
"""


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (path / "tickets").mkdir()
    (path / "app").mkdir()
    (path / "tests").mkdir()
    (path / "tickets" / "T001.md").write_text(TICKET, encoding="utf-8")
    (path / "app" / "health.py").write_text("ok = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)
    return path


def _suite(*, passed=(), failed=()) -> SuiteReport:
    passed_ids = set(passed)
    failed_ids = set(failed)
    return SuiteReport(
        exists=True,
        tests=len(passed_ids) + len(failed_ids),
        failures=len(failed_ids),
        passed_ids=passed_ids,
        failed_ids=failed_ids,
    )


def _run(*, passed=(), failed=(), coverage=True, ok=True) -> RunResult:
    return RunResult(
        task="test",
        exit_code=0 if ok and not failed else 1,
        output="",
        junit=_suite(passed=passed, failed=failed),
        coverage=CoverageReport(exists=coverage, line_rate=100.0 if coverage else 0.0),
    )


class ScriptedBackend(doers.Backend):
    """Writes the files for this call, then stops. Call 1 is tests. Call 2 is app."""

    name = "scripted"

    def __init__(self, script: list[list[tuple[str, str]]]):
        self.script = script
        self.calls = 0

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        files = self.script[self.calls] if self.calls < len(self.script) else []
        self.calls += 1
        wrote = []
        for relative, text in files:
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            wrote.append(relative)
        return doers.DoerResult(wrote=wrote, output=f"wrote {wrote}", usd=0.0)


def _patch_runs(monkeypatch, runs: list[RunResult]):
    leftover = list(runs)

    def fake_run(self, task: str, timeout: int = 900) -> RunResult:
        if leftover:
            result = leftover.pop(0)
        else:
            result = _run(passed=("tests/test_health.py::test_health",), failed=())
        if task != "test":
            result = RunResult(
                task=task,
                exit_code=0,
                output="",
                junit=_suite(passed=("e2e::ok",)) if task == "e2e" else SuiteReport(),
                coverage=CoverageReport(),
            )
        return result

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


def test_red_gate_escalates_when_nothing_new_fails(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    trace = implementer.run(
        repo=repo,
        ticket_id="T001",
        doer=ScriptedBackend([]),
        write_trace=True,
    )

    assert trace["gate"] == "escalate"
    assert "red gate" in trace["reason"]
    assert trace["red_ids"] == []
    assert "test_phase" in trace
    assert (repo / ".harness" / "last-implementer.json").exists()


def test_red_gate_keeps_a_test_phase_scope_violation(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = ScriptedBackend([[("app/leaked.py", "leaked = True\n")]])
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, write_trace=True)

    assert trace["gate"] == "escalate"
    assert trace["test_phase"]["violations"]
    assert any("app/leaked.py" in item for item in trace["scope_violations"])
    assert (repo / "app" / "leaked.py").exists()


def test_happy_path_passes_the_rubric(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert backend.calls == 2
    assert trace["gate"] == "pass"
    assert "the rubric is green" in trace["reason"]
    assert (repo / "tests" / "test_greet.py").exists()
    assert (repo / "app" / "greet.py").exists()
    assert "tests/test_greet.py" in trace["test_phase"]["files"]


def test_code_phase_cannot_hide_a_test_write(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("tests/test_cheat.py", "def test_cheat():\n    assert True\n")],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] != "pass"
    report = trace.get("rubric", "")
    assert "write_scope" in report
    assert "FAIL" in report
