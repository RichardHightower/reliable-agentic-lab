"""#576. `rubric.ui_has_e2e` and the role write scopes must agree.

`ui_has_e2e` (`rubric.py`) demands a green `tests/e2e` suite whenever a
changed file matches `.loop.yml`'s `rubric.ui_paths`. A live round-5 trace
found a target repo whose code implementer is denied `tests/**` and whose
test implementer runs once, before the code phase, so no role in the cast
ever got a second chance to write the suite the row was about to demand:
nine of ten rubric rows passed, the loop retried, and it escalated after
spending a turn on an attempt no scoped role could have satisfied.

Two things pin the fix: `Contract.validate` refuses a `.loop.yml` that makes
`ui_has_e2e` structurally unsatisfiable, naming the row and the path; and a
test implementer that actually writes the e2e suite the row wants does not
escalate on that row alone.

Helpers are copied from `tests/test_implementer.py`, not imported, the same
way `tests/test_parity.py` copies its own fixtures.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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

# A UI-touching ticket: AC-1's only reasonable implementation is a template
# edit, which is what makes `touched_ui` non-empty for the code phase below.
UI_LOOP_YML = """\
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
  ui_paths: ["app/templates/**"]
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

- (AC-1) The greeting page shows a friendly message.
"""


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (path / ".loop.yml").write_text(UI_LOOP_YML, encoding="utf-8")
    (path / "tickets").mkdir()
    (path / "app").mkdir()
    (path / "tests").mkdir()
    (path / "tickets" / "T001.md").write_text(TICKET, encoding="utf-8")
    (path / "app" / "health.py").write_text("ok = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)
    return path


def _suite(*, passed=(), failed=()) -> SuiteReport:
    passed_ids, failed_ids = set(passed), set(failed)
    return SuiteReport(
        exists=True,
        tests=len(passed_ids) + len(failed_ids),
        failures=len(failed_ids),
        passed_ids=passed_ids,
        failed_ids=failed_ids,
    )


def _run(*, passed=(), failed=()) -> RunResult:
    return RunResult(
        task="test",
        exit_code=0 if not failed else 1,
        output="",
        junit=_suite(passed=passed, failed=failed),
        coverage=CoverageReport(exists=True, line_rate=100.0),
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


def _patch_ui_runs(monkeypatch, test_runs: list[RunResult]):
    """`test` is scripted turn by turn. `e2e` reads the real worktree: green
    only once `tests/e2e/test_ui.py` actually exists, so a passing
    `ui_has_e2e` row here is caused by the scripted write below, not by an
    unconditional fake."""
    leftover = list(test_runs)

    def fake_run(self, task: str, timeout: int = 900) -> RunResult:
        if task == "test":
            if leftover:
                return leftover.pop(0)
            return _run(passed=("tests/test_health.py::test_health",))
        if task == "e2e":
            e2e_file = self.repo / "tests" / "e2e" / "test_ui.py"
            if e2e_file.is_file():
                return RunResult(
                    task="e2e",
                    exit_code=0,
                    output="",
                    junit=_suite(passed=("tests/e2e/test_ui.py::test_ui",)),
                    coverage=CoverageReport(),
                )
            return RunResult(
                task="e2e",
                exit_code=0,
                output="no e2e tests yet",
                junit=SuiteReport(exists=True, tests=0),
                coverage=CoverageReport(),
            )
        return RunResult(
            task=task, exit_code=0, output="", junit=SuiteReport(), coverage=CoverageReport()
        )

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


def test_t001_does_not_escalate_on_ui_has_e2e_when_the_test_implementer_writes_the_suite(
    tmp_path, monkeypatch
):
    """The offline loop, against a fixture shaped like the round-5 target
    (a UI-touching AC, a code implementer denied `tests/**`, `ui_paths`
    declared): a test implementer that writes `tests/e2e/test_ui.py` in the
    same call it writes the unit test gives the code phase's later UI edit
    something to be judged green against. The run must not escalate on
    `ui_has_e2e` alone."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    red = _run(
        passed=("tests/test_health.py::test_health",),
        failed=("tests/test_greet.py::test_ac_1_greets",),
    )
    green = _run(
        passed=(
            "tests/test_health.py::test_health",
            "tests/test_greet.py::test_ac_1_greets",
        )
    )
    _patch_ui_runs(monkeypatch, [baseline, red, green])

    backend = ScriptedBackend(
        script=[
            [
                ("tests/test_greet.py", "def test_ac_1_greets():\n    assert True\n"),
                ("tests/e2e/test_ui.py", "def test_ui():\n    assert True\n"),
            ],
            [("app/templates/greet.html", "<p>hello</p>\n")],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, write_trace=True)

    assert "ui_has_e2e" not in (trace.get("scope_violations") or [])
    assert "PASS  ui_has_e2e" in trace["rubric"], trace["rubric"]
    assert trace["gate"] == "pass", trace.get("reason")


def test_a_rubric_declaring_ui_paths_with_no_writable_e2e_path_fails_validate(tmp_path):
    """A `.loop.yml` that declares `ui_paths` but narrows every role's scope
    away from `contract.UI_E2E_PATH` asks the loop to satisfy a row nothing
    in the cast may write. `Contract.validate` must refuse it up front,
    naming the row and the path, rather than let three turns of retry
    discover it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (repo / ".loop.yml").write_text(
        """\
version: 1
roles:
  test_implementer:
    write_allow: ["tests/unit/**"]
  code_implementer:
    write_allow: ["app/**"]
    write_deny: ["tests/**"]
rubric:
  ui_paths: ["app/templates/**"]
""",
        encoding="utf-8",
    )

    target = contract_mod.Contract(repo)
    with pytest.raises(contract_mod.ContractError, match="ui_has_e2e") as excinfo:
        target.validate()
    assert contract_mod.UI_E2E_PATH in str(excinfo.value)


def test_a_rubric_with_no_ui_paths_never_needs_the_e2e_scope_check(tmp_path):
    """The check is conditional: a target that never declares `ui_paths`
    (the default) has nothing for `ui_has_e2e` to demand, so a narrow
    test-implementer scope is never a validation failure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (repo / ".loop.yml").write_text(
        """\
version: 1
roles:
  test_implementer:
    write_allow: ["tests/unit/**"]
""",
        encoding="utf-8",
    )

    contract_mod.Contract(repo).validate()  # must not raise
