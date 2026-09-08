"""Drive implementer.run with a scripted backend. No model. No public CRM."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
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

NEEDS_TASK = pytest.mark.skipif(
    shutil.which("task") is None,
    reason="needs the task CLI, absent on the bare CI runner",
)

REAL_TEST_TASKFILE = """\
version: '3'
vars:
  PY: .venv/bin/python
tasks:
  setup:
    cmds: [echo setup]
  test:
    cmds:
      - mkdir -p reports
      - "{{.PY}} -m pytest tests -q --junitxml=reports/junit.xml"
  e2e:
    cmds: [echo e2e]
  lint:
    cmds: [echo lint]
  format-check:
    cmds: [echo format-check]
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
        if task != "test":
            return RunResult(
                task=task,
                exit_code=0,
                output="",
                junit=_suite(passed=("e2e::ok",)) if task == "e2e" else SuiteReport(),
                coverage=CoverageReport(),
            )
        if leftover:
            return leftover.pop(0)
        return _run(passed=("tests/test_health.py::test_health",), failed=())

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


def _seed_field_rename_ticket(repo: Path) -> tuple[Path, Path, Path]:
    ticket = """\
---
id: T002
title: Rename a task field
state: ready
---

# T002 Rename a task field

## Acceptance criteria

- (AC-1) The backend payload and task form both call the field `display_name`.
"""
    test_path = repo / "tests" / "test_task_fields.py"
    backend_path = repo / "app" / "task_fields.py"
    form_path = repo / "app" / "templates" / "task_form.html"
    test_path.write_text(
        'def test_task_uses_legacy_field_name():\n    assert "task_title" == "task_title"\n',
        encoding="utf-8",
    )
    backend_path.write_text(
        "def task_payload():\n    return {'task_title': 'Ada'}\n", encoding="utf-8"
    )
    form_path.parent.mkdir()
    form_path.write_text('<input name="taskTitle" data-field="task_title">\n', encoding="utf-8")
    (repo / "tickets" / "T002.md").write_text(ticket, encoding="utf-8")
    subprocess.run(
        [
            "git",
            "add",
            "app/task_fields.py",
            "app/templates/task_form.html",
            "tests/test_task_fields.py",
            "tickets/T002.md",
        ],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "seed rename ticket"], cwd=repo, check=True, capture_output=True
    )
    return test_path, backend_path, form_path


def test_red_gate_escalates_after_two_silent_test_turns(tmp_path, monkeypatch):
    """A3 (#436). A silent test phase retries inside the budget (here 3, from
    LOOP_YML), and two attempts that touch the same files never diverge, so
    the loop stops as a stable failure rather than spending the whole budget."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = ScriptedBackend([])
    trace = implementer.run(
        repo=repo,
        ticket_id="T001",
        doer=backend,
        write_trace=True,
    )

    assert trace["gate"] == "escalate"
    assert "not converging" in trace["reason"]
    assert trace["red_ids"] == []
    assert "test_phase" in trace
    assert backend.calls == 2
    assert (Path(trace["repo"]) / ".harness" / "last-implementer.json").exists()


def test_red_gate_escalates_with_the_old_wording_at_budget_one(tmp_path, monkeypatch):
    """A3 (#436). Budget 1 behaves exactly as it did before this unit: one
    silent attempt, the same gate, the same reason wording."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = ScriptedBackend([])
    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True
    )

    assert trace["gate"] == "escalate"
    assert "red gate: no new test was observed failing" in trace["reason"]
    assert trace["red_ids"] == []
    assert backend.calls == 1


class FailingBackend(doers.Backend):
    """#539. A backend that never answers: a timed-out query, a raised
    exception. Writes nothing and says so, `ok=False`, the way a live
    backend's own failure path now reports itself."""

    name = "failing"

    def __init__(self, message: str):
        self.message = message

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        return doers.DoerResult(ok=False, usd=None, output=self.message)


def test_a_backend_failure_names_itself_instead_of_the_generic_red_gate_wording(
    tmp_path, monkeypatch
):
    """#539. A backend that never answered must not read as an honest turn
    that just wrote a passing test. The judge of PR #537 found the two
    indistinguishable in both ports' traces."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = FailingBackend("agent sdk query timed out after 900 seconds (elapsed=900s)")
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "escalate"
    assert "the test implementer backend did not answer" in trace["reason"]
    assert "timed out after 900 seconds" in trace["reason"]
    assert trace["test_phase"]["ok"] is False
    assert trace["test_phase"]["usd"] is None
    assert trace["test_phase"]["output"] == backend.message
    # #539(e). The trace names the cap the code actually applied (the
    # fixture's own `.loop.yml` above), not a number invented after the run.
    assert trace["budget_usd"] == 2.00
    assert trace["spent_usd"] == 0.0


def test_a_silent_test_turn_then_a_failing_test_passes_the_red_gate(tmp_path, monkeypatch):
    """A3 (#436). Turn 1 is silent. Turn 2 writes a failing test. Budget 2 is
    enough to reach it, and the red gate is satisfied rather than escalated."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    backend = ScriptedBackend(
        [
            [],
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=2, write_trace=True)

    assert trace["gate"] == "pass"
    assert trace["red_ids"] == [new_test]
    assert backend.calls == 3


def test_code_budget_is_not_spent_by_test_phase_retries(tmp_path, monkeypatch):
    """A3 (#436). The test phase's attempt counter is local; `boss.start_iteration()`
    is never called there, so a two-turn test phase leaves the code loop with
    its full budget."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    still_red = _run(passed=(health,), failed=(new_test,))
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,)),
            still_red,
            still_red,
            still_red,
        ],
    )
    backend = ScriptedBackend(
        [
            [],
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [],
            [],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=2, write_trace=True)

    assert trace["gate"] == "escalate"
    assert len(trace["iterations"]) == 2
    assert backend.calls == 4


def test_red_gate_keeps_a_test_phase_scope_violation(tmp_path, monkeypatch):
    """A scope violation escalates on the turn it happens. Budget 3 is set so
    a retry would be possible if the gate did not stop it, but it must not."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = ScriptedBackend([[("app/leaked.py", "leaked = True\n")]])
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert trace["test_phase"]["violations"]
    assert any("app/leaked.py" in item for item in trace["scope_violations"])
    assert (Path(trace["repo"]) / "app" / "leaked.py").exists()
    assert backend.calls == 1


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
    assert trace["judge"]["done"] is True
    written = Path(trace["repo"])
    assert (written / "tests" / "test_greet.py").exists()
    assert (written / "app" / "greet.py").exists()
    assert "tests/test_greet.py" in trace["test_phase"]["files"]


def test_test_phase_prompt_carries_the_plan_steps(tmp_path, monkeypatch):
    """A2 (#435). The test implementer sees its own plan steps. The code
    implementer still does not see a test step."""
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

    class Recording(ScriptedBackend):
        def __init__(self, script):
            super().__init__(script)
            self.prompts: list[str] = []

        def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
            self.prompts.append(prompt)
            return super().run(repo=repo, prompt=prompt, allow=allow)

    backend = Recording(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "pass"
    test_prompt, code_prompt = backend.prompts[0], backend.prompts[1]
    assert "S1T" in test_prompt
    assert "Write a test that fails until this holds" in test_prompt
    assert "a test covering AC-1 exists and fails before any code" in test_prompt
    assert "T001 greet" in test_prompt
    assert "S1T" not in code_prompt


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


def test_simple_field_rename_stays_inside_the_loop(tmp_path, monkeypatch):
    """A tiny offline story: plan, change one test, rename backend/UI fields."""
    repo = _git_repo(tmp_path / "repo")
    test_path, backend_path, form_path = _seed_field_rename_ticket(repo)

    old_id = "tests.test_task_fields::test_task_uses_legacy_field_name"
    renamed_id = "tests.test_task_fields::test_AC-1_display_name"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(old_id,)),
            _run(passed=(old_id,), failed=(renamed_id,)),
            _run(passed=(renamed_id,)),
        ],
    )
    renamed_test = """\
from app.task_fields import task_payload


def test_ac_1_backend_and_ui_use_display_name():
    assert task_payload()["display_name"] == "Ada"
"""
    renamed_backend = "def task_payload():\n    return {'display_name': 'Ada'}\n"
    renamed_form = '<input name="display_name" data-field="display_name">\n'
    backend = ScriptedBackend(
        [
            [("tests/test_task_fields.py", renamed_test)],
            [
                ("app/task_fields.py", renamed_backend),
                ("app/templates/task_form.html", renamed_form),
            ],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T002", doer=backend, budget=1)

    assert trace["gate"] == "pass"
    assert trace["red_ids"] == [renamed_id]
    assert backend.calls == 2
    assert trace["test_phase"]["files"] == ["tests/test_task_fields.py"]
    assert len(trace["iterations"]) == 1
    iteration = trace["iterations"][0]
    assert iteration["iteration"] == 1
    assert iteration["wrote"] == ["app/task_fields.py", "app/templates/task_form.html"]
    assert all(iteration["rows"].values())
    assert iteration["failed"] == []
    assert iteration["gate"] == "pass"
    assert "the rubric is green" in iteration["reason"]
    assert iteration["judge_done"] is True
    written = Path(trace["repo"])
    plan = (written / "steps.jsonl").read_text(encoding="utf-8")
    assert "display_name" in plan
    assert '"role": "test_implementer"' in plan
    assert '"role": "code_implementer"' in plan
    written_test = written / "tests" / "test_task_fields.py"
    written_backend = written / "app" / "task_fields.py"
    written_form = written / "app" / "templates" / "task_form.html"
    assert written_test.read_text(encoding="utf-8") == renamed_test
    assert written_backend.read_text(encoding="utf-8") == renamed_backend
    assert written_form.read_text(encoding="utf-8") == renamed_form
    assert "task_title" not in written_backend.read_text(encoding="utf-8")
    assert "taskTitle" not in written_form.read_text(encoding="utf-8")
    # The original tree, still on its seed commit, never saw the rename.
    assert test_path.read_text(encoding="utf-8") != renamed_test


def test_a_retry_carries_the_failed_rows_and_test_ids(tmp_path, monkeypatch):
    """The second code turn must not see the same ticket prompt again."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )

    class Recording(ScriptedBackend):
        def __init__(self):
            super().__init__(
                [
                    [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
                    [("app/greet.py", "def greet():\n    return 'nope'\n")],
                    [("app/greet.py", "def greet():\n    return 'hello'\n")],
                ]
            )
            self.prompts: list[str] = []

        def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
            self.prompts.append(prompt)
            return super().run(repo=repo, prompt=prompt, allow=allow)

    backend = Recording()
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3)

    assert trace["gate"] == "pass"
    assert len(backend.prompts) == 3
    assert "These rubric rows failed" in backend.prompts[2]
    assert new_test in backend.prompts[2]
    assert "These rubric rows failed" not in backend.prompts[0]
    assert "These rubric rows failed" not in backend.prompts[1]


def test_a_judge_who_says_not_done_escalates(tmp_path, monkeypatch):
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

    class Disagreeing(ScriptedBackend):
        def judge(self, *, repo: Path, prompt: str) -> doers.DoerResult:
            return doers.DoerResult(output='{"done": false, "why": "greet never called"}')

    backend = Disagreeing(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1)

    assert trace["gate"] == "escalate"
    assert "final judge says the ticket is not done" in trace["reason"]
    assert trace["judge"]["done"] is False


def test_an_unparseable_verdict_is_a_fail(tmp_path, monkeypatch):
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

    class Gibberish(ScriptedBackend):
        def judge(self, *, repo: Path, prompt: str) -> doers.DoerResult:
            return doers.DoerResult(output="looks good to me")

    backend = Gibberish(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1)

    assert trace["gate"] == "escalate"
    assert "final judge says the ticket is not done" in trace["reason"]
    assert trace["judge"]["why"] == "unparseable verdict"


def test_judge_prompt_names_a_changed_path_and_a_plan_step_id(tmp_path, monkeypatch):
    """A1 (#429). The judge gets the code phase's own paths and the plan, not
    just the rubric's word for it."""
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

    class RecordingJudge(ScriptedBackend):
        def __init__(self, script):
            super().__init__(script)
            self.judge_prompts: list[str] = []

        def judge(self, *, repo: Path, prompt: str) -> doers.DoerResult:
            self.judge_prompts.append(prompt)
            return doers.DoerResult(output='{"done": true, "why": "looks right"}')

    backend = RecordingJudge(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "pass"
    assert len(backend.judge_prompts) == 1
    prompt = backend.judge_prompts[0]
    assert "app/greet.py" in prompt
    assert "S1C" in prompt


def test_build_judge_no_wraps_reference_backend():
    """A1 (#430). `--doer judge-no` is the classroom demo: a green rubric that
    still escalates because the judge refuses."""
    backend = doers.build("judge-no")

    assert isinstance(backend, doers.JudgeSaysNoBackend)
    assert isinstance(backend.inner, doers.ReferenceBackend)


def test_build_reference_is_unaffected_by_the_judge_no_wrapper():
    backend = doers.build("reference")

    assert isinstance(backend, doers.ReferenceBackend)
    assert not isinstance(backend, doers.JudgeSaysNoBackend)


def test_build_unknown_spec_raises_value_error_naming_the_valid_specs():
    """A8 (#441). CliBackend is gone; an unknown spec fails closed with a
    message a reader can act on, instead of shelling out to a bare word."""
    with pytest.raises(ValueError) as excinfo:
        doers.build("claude")

    message = str(excinfo.value)
    for valid in ("none", "reference", "judge-no"):
        assert valid in message


def test_doers_module_has_no_cli_backend_or_cli_commands():
    """A8 (#441). The fence-or-drop ticket resolved to drop."""
    assert not hasattr(doers, "CliBackend")
    assert not hasattr(doers, "CLI_COMMANDS")


def test_doers_docstring_names_the_real_backend_set_including_judge_no():
    """A8 (#441) plus the PR #485 judge follow-up: the docstring must not
    still claim three backends, and must name judge-no."""
    doc = doers.__doc__ or ""
    assert "judge-no" in doc
    for name in ("none", "reference"):
        assert name in doc


def test_no_source_file_in_this_port_names_clibackend():
    """A8 (#441). `grep -rn CliBackend` over this port's own files, skipping
    .venv, __pycache__, and this test file itself (which names the deleted
    class only to assert its absence), must find nothing. Each port carries
    this test for its own tree; together the two suites cover both port
    folders."""
    port_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            "grep",
            "-rn",
            "--exclude-dir=.venv",
            "--exclude-dir=__pycache__",
            "--exclude=test_implementer.py",
            "CliBackend",
            str(port_root),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"found CliBackend references:\n{result.stdout}"


def test_doer_help_names_no_cli_and_names_judge_no(capsys):
    """A8 (#441). The --doer help string must not advertise a CLI this build
    cannot fence, and must name judge-no."""
    with pytest.raises(SystemExit):
        implementer.main(["--help"])

    out = capsys.readouterr().out
    assert "judge-no" in out
    for cli in ("claude", "codex", "grok", "opencode"):
        assert cli not in out


def test_judge_says_no_backend_escalates_on_a_green_rubric(tmp_path, monkeypatch):
    """A1 (#430). Wrap a scripted backend in JudgeSaysNoBackend, not a live
    judge patch: the fixture backend is what a room can actually run."""
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
    inner = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    backend = doers.JudgeSaysNoBackend(inner)

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "escalate"
    assert trace["judge"]["done"] is False
    assert "final judge says the ticket is not done" in trace["reason"]


def test_due_date_in_a_passing_id_does_not_prove_every_step(tmp_path):
    """The old T001 leak. A passing test named due_date is not evidence for AC-9."""
    plan = implementer.plan_for(
        implementer.tickets.Ticket(
            id="T009",
            title="x",
            state="ready",
            criteria=[
                implementer.tickets.Criterion("AC-1", "has due_date"),
                implementer.tickets.Criterion("AC-9", "something else"),
            ],
        )
    )
    proven = implementer._mark_proven(
        plan, {"tests/test_due_date.py::test_model_has_optional_due_date"}, tmp_path
    )
    by_id = {step.id: step for step in proven.steps}
    assert by_id["S1T"].status == "todo"
    assert by_id["S2T"].status == "todo"


def test_a_passing_id_that_names_the_criterion_proves_the_step(tmp_path):
    plan = implementer.plan_for(
        implementer.tickets.Ticket(
            id="T001",
            title="x",
            state="ready",
            criteria=[implementer.tickets.Criterion("AC-1", "greet returns hello")],
        )
    )
    proven = implementer._mark_proven(plan, {"tests/test_greet.py::test_AC-1"}, tmp_path)
    assert proven.steps[0].status == "done"
    assert proven.steps[0].evidence == "tests/test_greet.py::test_AC-1"


def test_a_draft_with_criteria_is_not_ready():
    ticket = implementer.tickets.parse(
        "---\nid: T001\nstate: draft\n---\n# T001\n\n## Acceptance criteria\n\n- (AC-1) greet\n"
    )
    assert ticket.criteria
    assert ticket.state == "draft"
    assert ticket.ready is False


def test_happy_path_writes_the_three_claim_receipt(tmp_path, monkeypatch):
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
    path = Path(trace["repo"]) / ".harness" / "receipt.json"
    assert path.exists()
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert "tree_hash" in payload
    assert "green" in payload
    assert "written_at" in payload


# -- A4 (#431). Isolated git worktree -----------------------------------


@NEEDS_TASK
def test_worktree_runs_the_real_suite_and_parses_junit(tmp_path):
    """No monkeypatch: contract.run("test") against a fresh worktree proves
    the .venv bootstrap actually works, because the worktree's own linked
    interpreter has to run pytest and write a real junit.xml for this to
    pass."""
    repo = _git_repo(tmp_path / "repo")
    (repo / "Taskfile.yml").write_text(REAL_TEST_TASKFILE, encoding="utf-8")
    (repo / "tests" / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "Taskfile.yml", "tests/test_sample.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "a real test task"], cwd=repo, check=True, capture_output=True
    )
    # Untracked on purpose: the bootstrap step has to symlink this itself,
    # never one `git worktree add` happens to check out. Not .resolve(): a
    # venv's own python is a symlink chain down to the system interpreter,
    # and resolving it away would point at a plain install with no venv
    # structure at all.
    venv_root = Path(sys.executable).parent.parent
    (repo / ".venv").symlink_to(venv_root)

    worktree = implementer._worktree(repo, "T001")
    result = contract_mod.Contract(worktree).run("test")

    assert result.junit.exists
    assert result.junit.tests == 1
    assert result.junit.failures == 0
    assert (worktree / ".venv").exists()


def test_two_repos_named_repo_get_different_worktrees(tmp_path, monkeypatch):
    """Every fixture repo in this file is named "repo" with ticket T001, so a
    worktree keyed on repo.name alone collides. A sibling of the resolved
    repo does not: two repos under two different parents never share one."""
    repo_a = _git_repo(tmp_path / "a" / "repo")
    repo_b = _git_repo(tmp_path / "b" / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"

    def scripted_runs():
        return [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ]

    _patch_runs(monkeypatch, scripted_runs())
    backend_a = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'A'\n")],
        ]
    )
    trace_a = implementer.run(repo=repo_a, ticket_id="T001", doer=backend_a, budget=1)

    _patch_runs(monkeypatch, scripted_runs())
    backend_b = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'B'\n")],
        ]
    )
    trace_b = implementer.run(repo=repo_b, ticket_id="T001", doer=backend_b, budget=1)

    assert trace_a["gate"] == "pass"
    assert trace_b["gate"] == "pass"
    worktree_a, worktree_b = Path(trace_a["repo"]), Path(trace_b["repo"])
    assert worktree_a != worktree_b
    assert (worktree_a / "app" / "greet.py").read_text(encoding="utf-8") == (
        "def greet():\n    return 'A'\n"
    )
    assert (worktree_b / "app" / "greet.py").read_text(encoding="utf-8") == (
        "def greet():\n    return 'B'\n"
    )


def test_original_tree_stays_clean_and_gains_no_harness(tmp_path, monkeypatch):
    """Everything after the ticket read binds to the worktree. The original
    stays porcelain-clean and never grows a .harness of its own."""
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

    assert trace["gate"] == "pass"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True
    )
    assert status.stdout == ""
    assert not (repo / ".harness").exists()
    assert Path(trace["repo"]) != repo.resolve()


def test_rerun_without_resume_starts_from_a_reset_tree(tmp_path, monkeypatch):
    """There is no --resume flag yet (A6 adds one). A second run of the same
    ticket resets the reused worktree before its own baseline: a file only
    the first run wrote is gone before the second run does anything."""
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
    first_backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [
                ("app/greet.py", "def greet():\n    return 'hello'\n"),
                ("app/leftover.txt", "from the first run\n"),
            ],
        ]
    )
    first = implementer.run(repo=repo, ticket_id="T001", doer=first_backend, budget=1)
    worktree = Path(first["repo"])
    assert (worktree / "app" / "leftover.txt").exists()

    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    second_backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    second = implementer.run(repo=repo, ticket_id="T001", doer=second_backend, budget=1)

    assert Path(second["repo"]) == worktree
    assert not (worktree / "app" / "leftover.txt").exists()


def test_non_git_target_raises_contract_error(repo):
    """git worktree add fails on a plain directory. The `repo` fixture
    (conftest.py) builds exactly that: a Taskfile and a role table, no .git."""
    with pytest.raises(implementer.ContractError, match="not a git repository"):
        implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend())


def test_leftover_worktree_directory_raises_contract_error(tmp_path):
    """A path that exists but is not a registered git worktree is a
    leftover, never something `git worktree add` runs on top of."""
    repo = _git_repo(tmp_path / "repo")
    leftover = repo.parent / f"{repo.name}.worktrees" / "T001"
    leftover.mkdir(parents=True)
    (leftover / "junk.txt").write_text("not a worktree\n", encoding="utf-8")

    with pytest.raises(implementer.ContractError, match="not a registered git worktree"):
        implementer._worktree(repo, "T001")


@NEEDS_TASK
def test_uncommitted_ticket_and_never_committed_loop_yml_reach_the_worktree(tmp_path):
    """The enhancer's ticket edit is often uncommitted, and a target repo's
    own .loop.yml may never be tracked at all. Both still have to reach the
    worktree, or a live doer reading its own cwd never sees them."""
    repo = _git_repo(tmp_path / "repo")
    uncommitted_ticket = TICKET.replace(
        "greet() returns hello", "greet() returns hi, uncommitted"
    )
    (repo / "tickets" / "T001.md").write_text(uncommitted_ticket, encoding="utf-8")

    # .loop.yml was committed by _git_repo. Simulate a target repo where it
    # was never tracked at all, without touching the file on disk.
    subprocess.run(
        ["git", "rm", "--cached", ".loop.yml"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "stop tracking .loop.yml"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    worktree = implementer._worktree(repo, "T001")

    copied_ticket = (worktree / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert "uncommitted" in copied_ticket
    assert (worktree / ".loop.yml").read_text(encoding="utf-8") == LOOP_YML


def test_cleanup_flag_removes_the_worktree_and_prints_the_path_without_it(
    tmp_path, monkeypatch, capsys
):
    """Open decision 2: the worktree is never removed automatically. Without
    --cleanup the path and the removal command print; --cleanup actually
    runs `git worktree remove`."""
    repo = _git_repo(tmp_path / "repo")
    resolved_repo = repo.resolve()
    worktree_path = resolved_repo.parent / f"{resolved_repo.name}.worktrees" / "T001"
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    implementer.main(["--repo", str(repo), "--ticket", "T001", "--doer", "none", "--budget", "1"])
    out = capsys.readouterr().out
    assert worktree_path.exists()
    assert f"worktree: {worktree_path}" in out
    assert f"git -C {resolved_repo} worktree remove {worktree_path}" in out
    # #539. A failed run's own raw turn records are the evidence a trace
    # cites; they must still be sitting in the worktree, not just the
    # worktree's path.
    assert (worktree_path / ".harness" / "last-implementer.json").exists()
    assert (worktree_path / ".harness" / "state.json").exists()

    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    implementer.main(
        [
            "--repo", str(repo), "--ticket", "T001", "--doer", "none",
            "--budget", "1", "--cleanup",
        ]
    )
    out2 = capsys.readouterr().out
    assert f"worktree removed: {worktree_path}" in out2
    assert not worktree_path.exists()


def test_a_symlink_at_the_worktree_path_is_refused(tmp_path):
    """Judge's blocker on PR #495. A symlink at <repo>.worktrees/<ticket>
    used to pass the registration guard whenever it pointed at any
    registered worktree, and reset --hard / clean -fd then ran through it.
    is_symlink() is checked before anything else, so this never gets there:
    the source repo's uncommitted edit and untracked file both survive."""
    repo = _git_repo(tmp_path / "repo")
    (repo / "app" / "health.py").write_text("ok = True  # uncommitted edit\n", encoding="utf-8")
    (repo / "app" / "untracked.txt").write_text("keep me\n", encoding="utf-8")

    resolved_repo = repo.resolve()
    worktrees_dir = resolved_repo.parent / f"{resolved_repo.name}.worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    (worktrees_dir / "T001").symlink_to(resolved_repo)

    with pytest.raises(implementer.ContractError, match="refusing to use it as a worktree path"):
        implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend())

    assert "uncommitted edit" in (repo / "app" / "health.py").read_text(encoding="utf-8")
    assert (repo / "app" / "untracked.txt").exists()


@NEEDS_TASK
def test_a_symlink_to_another_tickets_worktree_is_refused(tmp_path):
    """Same guard, a different target: the symlink points at a real,
    registered worktree that just is not this ticket's."""
    repo = _git_repo(tmp_path / "repo")
    other_worktree = implementer._worktree(repo, "T002")

    resolved_repo = repo.resolve()
    worktrees_dir = resolved_repo.parent / f"{resolved_repo.name}.worktrees"
    (worktrees_dir / "T001").symlink_to(other_worktree)

    with pytest.raises(implementer.ContractError, match="refusing to use it as a worktree path"):
        implementer._worktree(repo, "T001")


def test_nested_non_git_target_raises_contract_error_and_creates_no_worktree(tmp_path):
    """implementer.py used to detect "not a git repository" only by
    `git worktree list`'s exit code, which succeeds for a plain directory
    nested inside any git repo and names the outer repo, so a worktree of
    the outer repo got created before _bootstrap ever failed."""
    outer = tmp_path / "outer"
    outer.mkdir()
    subprocess.run(["git", "init"], cwd=outer, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=outer, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=outer, check=True)
    (outer / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=outer, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=outer, check=True, capture_output=True)

    nested = outer / "nested"
    nested.mkdir()
    (nested / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (nested / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (nested / "tickets").mkdir()

    with pytest.raises(implementer.ContractError, match="not a git repository"):
        implementer.run(repo=nested, ticket_id="T001", doer=doers.NoneBackend())

    assert not any(p.name.endswith(".worktrees") for p in tmp_path.rglob("*") if p.is_dir())


def test_worktree_plumbing_without_the_task_binary(tmp_path):
    """CI's bare `folders` job installs pytest only (no `task` CLI). This is
    the one test that proves the worktree setup itself -- bootstrap, ticket
    copy, .loop.yml, Taskfile -- without ever shelling to `task`: a
    gitignored .venv in the source repo sends _bootstrap down the symlink
    branch, never the `task setup` fallback, and this must run in CI."""
    repo = _git_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "gitignore .venv"], cwd=repo, check=True, capture_output=True
    )
    (repo / ".venv").mkdir()
    (repo / ".venv" / "marker.txt").write_text("fake venv\n", encoding="utf-8")

    worktree = implementer._worktree(repo, "T001")

    assert (worktree / ".venv").is_symlink()
    assert (worktree / ".venv" / "marker.txt").read_text(encoding="utf-8") == "fake venv\n"
    assert (worktree / "tickets" / "T001.md").read_text(encoding="utf-8") == TICKET
    assert (worktree / ".loop.yml").read_text(encoding="utf-8") == LOOP_YML
    assert (worktree / "Taskfile.yml").read_text(encoding="utf-8") == TASKFILE
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True
    )
    assert status.stdout == ""


# -- A5 (#432 #434). state.json and exit codes 0, 2, 1 --------------------


def test_state_json_has_ten_keys_and_runs_increments(tmp_path, monkeypatch):
    """Fields the Module 4 slides already name, plus the five A6 (#433) adds
    for --resume. `runs` accumulates across two runs of the same ticket,
    which reuse the same worktree."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    first = implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)
    state_path = Path(first["repo"]) / ".harness" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(state) == {
        "runs", "last_gate", "last_reason", "last_run_at", "loop",
        "phase", "red_ids", "preexisting", "test_phase_files", "test_phase_attempts",
    }
    assert state["runs"] == 1
    assert state["last_gate"] == "escalate"
    assert state["loop"] == "implementer"
    # NoneBackend never reaches the code loop: the red gate never sees a new
    # failing test, so the run escalates from inside the test phase and the
    # checkpoint never flips to "code".
    assert state["phase"] == "test"
    assert state["red_ids"] == []

    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)
    state2 = json.loads(state_path.read_text(encoding="utf-8"))
    assert state2["runs"] == 2


def test_corrupt_state_json_exits_before_any_work(tmp_path, monkeypatch):
    """#432. A truncated state.json is never a fresh start: it raises before
    the baseline test runs, and the backend is never called."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    first = implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)
    state_path = Path(first["repo"]) / ".harness" / "state.json"
    state_path.write_text('{"runs": 1, "last_g', encoding="utf-8")

    def _no_baseline(self, task: str, timeout: int = 900) -> RunResult:
        # Bootstrap's own `task setup` call (implementer.py's `_bootstrap`)
        # still has to succeed; only the baseline `task test` is forbidden.
        if task == "test":
            raise AssertionError("no baseline test run may happen once state.json is corrupt")
        return RunResult(task=task, exit_code=0, output="", junit=SuiteReport(), coverage=CoverageReport())

    monkeypatch.setattr(contract_mod.Contract, "run", _no_baseline)
    monkeypatch.setattr(implementer.Contract, "run", _no_baseline)
    backend = ScriptedBackend([])

    with pytest.raises(implementer.ContractError, match="corrupt"):
        implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1)

    assert backend.calls == 0


def test_doer_none_on_t001_exits_2_with_red_gate_reason(tmp_path, monkeypatch, capsys):
    """#434, offline verification. --doer none writes nothing, so the red
    gate never sees a new failing test and the run escalates."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    exit_code = implementer.main(
        ["--repo", str(repo), "--ticket", "T001", "--doer", "none", "--budget", "1"]
    )

    assert exit_code == 2
    out = capsys.readouterr().out
    assert "gate: escalate" in out
    assert "red gate: no new test was observed failing" in out


def test_doer_reference_happy_path_exits_0(tmp_path, monkeypatch, capsys):
    """#434. --doer reference is the classroom demo, no model and no key. A
    clean run of it passes the rubric and exits 0."""
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
    (repo / "tests" / "test_greet.py").write_text(
        "def test_ac1():\n    assert False\n", encoding="utf-8"
    )
    (repo / "app" / "greet.py").write_text(
        "def greet():\n    return 'hello'\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "tests/test_greet.py", "app/greet.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "known good answer"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(["git", "branch", "known-good"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "reset", "--hard", "HEAD~1"], cwd=repo, check=True, capture_output=True
    )

    exit_code = implementer.main(
        ["--repo", str(repo), "--ticket", "T001", "--doer", "reference", "--budget", "1"]
    )

    assert exit_code == 0
    assert "gate: pass" in capsys.readouterr().out


def test_contract_error_exits_1_with_one_line_and_no_traceback(tmp_path, capsys):
    """#434. A ContractError -- here, a non-git target from A4 -- prints one
    line and returns 1. It must never surface as a traceback."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (plain / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (plain / "tickets").mkdir()

    exit_code = implementer.main(["--repo", str(plain), "--ticket", "T001", "--doer", "none"])

    assert exit_code == 1
    out = capsys.readouterr().out.strip()
    assert out.count("\n") == 0
    assert "not a git repository" in out


def test_test_phase_money_exhaustion_keeps_the_money_reason(tmp_path, monkeypatch):
    """Folded finding, judge of PR #490. `gates.decide` can name the money
    budget from inside the test-phase retry loop too. The `else` branch used
    to overwrite that reason with the red-gate wording; it must not."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    class BrokeBackend(ScriptedBackend):
        def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
            result = super().run(repo=repo, prompt=prompt, allow=allow)
            result.usd = 2.0  # LOOP_YML's whole budget, spent on the first turn
            return result

    backend = BrokeBackend([])
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert trace["reason"] == "the money budget is spent"
    assert backend.calls == 1
    state_path = Path(trace["repo"]) / ".harness" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_reason"] == "the money budget is spent"


# -- A6 (#433). --resume ---------------------------------------------------


class RecordingScriptedBackend(ScriptedBackend):
    """ScriptedBackend that also records the `allow` scope of every call, so
    a resumed run can be proven to reach only the code implementer's scope."""

    def __init__(self, script):
        super().__init__(script)
        self.allows: list[list[str]] = []

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        self.allows.append(list(allow))
        return super().run(repo=repo, prompt=prompt, allow=allow)


def test_a_planted_file_under_harness_is_a_scope_violation(tmp_path, monkeypatch):
    """Judge's blocker on PR #500. The loop's own bookkeeping exclusion is
    exactly four named files (steps.jsonl, state.json, last-implementer.json,
    receipt.json), not the whole .harness/ directory. A doer planting
    anything else there is still a write outside its declared scope."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    backend = ScriptedBackend([[(".harness/planted.py", "pwned = True\n")]])
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert any(".harness/planted.py" in v for v in trace["scope_violations"])


def test_a_doer_that_overwrites_steps_jsonl_is_a_scope_violation(tmp_path, monkeypatch):
    """#501. `steps.jsonl` is one of the loop's own named outputs, excluded
    by name from every changed-files scan -- so an overwrite of it used to
    match the same exclusion as the loop's own write, regardless of who made
    it. A doer scoped to tests/** that plants a new steps.jsonl is still a
    write outside its declared scope, the same as `.harness/planted.py`
    above."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = ScriptedBackend([[("steps.jsonl", '{"id": "evil"}\n')]])
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert "steps.jsonl" in trace["scope_violations"]
    assert backend.calls == 1


def test_a_code_turn_overwrite_of_steps_jsonl_stays_a_scope_violation(tmp_path, monkeypatch):
    """#501, judge of PR #527, blocking finding. The test above only drove
    the overwrite through the test phase. On a code turn, `_mark_proven`'s
    own rewrite of steps.jsonl erased the doer's overwrite one line after
    the scan that caught it, and the tamper baseline refreshed right after
    -- so the next iteration's scan read clean and the run could gate
    `pass`, the same as if nothing had happened. `code_scope_violations`
    keeps the violation flagged for the rest of the run, matching how
    `.harness/planted.py` stays in `changed_files` for as long as it sits on
    disk."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
            _run(passed=(health, new_test)),
        ],
    )
    backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [
                ("app/greet.py", "def greet():\n    return 'hello'\n"),
                ("steps.jsonl", '{"id": "evil"}\n'),
            ],
            [],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] != "pass"
    assert "steps.jsonl" in trace["scope_violations"]
    # A second, clean code turn must not wash the violation away: every
    # iteration this run recorded still names write_scope as a failed row.
    assert trace["iterations"], "the code loop never recorded an iteration"
    assert all("write_scope" in it["failed"] for it in trace["iterations"])


class DeletingBackend(doers.Backend):
    """Deletes one path instead of writing to it, on its one scripted call."""

    name = "scripted"

    def __init__(self, relative: str):
        self.relative = relative
        self.calls = 0

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        self.calls += 1
        target = repo / self.relative
        if target.exists():
            target.unlink()
        return doers.DoerResult(wrote=[], output=f"deleted {self.relative}", usd=0.0)


def test_a_doer_that_deletes_steps_jsonl_is_a_scope_violation(tmp_path, monkeypatch):
    """#501, judge of PR #527, follow-up 1. `_loop_output_tampered` treats a
    missing file the same as changed bytes. Before this, `_mark_proven`
    would have recreated a deleted steps.jsonl on the next code turn without
    anyone ever having flagged the deletion itself."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = DeletingBackend("steps.jsonl")
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert "steps.jsonl" in trace["scope_violations"]
    assert backend.calls == 1


class SymlinkForgeryBackend(doers.Backend):
    """Copies one path's own current bytes elsewhere, then replaces the
    original with a symlink to that copy: a byte-identical forgery a plain
    content comparison cannot see, because the bytes read through the link
    are exactly the bytes `last_output_bytes` already expects. Only an
    explicit `is_symlink()` check catches this; a dangling symlink would
    already read as tampered through the plain "file is gone" branch, so it
    would not by itself prove the `is_symlink()` check earns its place."""

    name = "scripted"

    def __init__(self, relative: str):
        self.relative = relative
        self.calls = 0

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        self.calls += 1
        target = repo / self.relative
        copy_path = repo / "app" / "steps_copy.jsonl"
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        copy_path.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(copy_path)
        return doers.DoerResult(wrote=[], output=f"symlinked {self.relative}", usd=0.0)


def test_a_doer_that_symlinks_steps_jsonl_is_a_scope_violation(tmp_path, monkeypatch):
    """#501, judge of PR #527, follow-up 2. A symlink swap is not a content
    change a bytes comparison that reads through the link would ever catch:
    the forged file here reads back byte-identical to the loop's own last
    write. `_loop_output_tampered` checks `is_symlink()` first, the same
    guard `_worktree` already uses to refuse a symlinked worktree path.
    Before this, the loop's own `plan.save` would have written straight
    through the link on the next legitimate write."""
    repo = _git_repo(tmp_path / "repo")
    baseline = _run(passed=("tests/test_health.py::test_health",))
    still_green = _run(passed=("tests/test_health.py::test_health",))
    _patch_runs(monkeypatch, [baseline, still_green])

    backend = SymlinkForgeryBackend("steps.jsonl")
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "escalate"
    assert "steps.jsonl" in trace["scope_violations"]
    assert backend.calls == 1


def _patch_runs_and_lint(monkeypatch, test_runs: list[RunResult], lint_oks: list[bool]):
    """Like `_patch_runs`, plus a scripted `lint` result per call. Used only
    by `test_the_loops_own_plan_write_is_bookkeeping`, to force a second code
    iteration after `_mark_proven` has already rewritten steps.jsonl once."""
    leftover_tests = list(test_runs)
    leftover_lint = list(lint_oks)

    def fake_run(self, task: str, timeout: int = 900) -> RunResult:
        if task == "lint":
            ok = leftover_lint.pop(0) if leftover_lint else True
            return RunResult(
                task=task, exit_code=0 if ok else 1, output="",
                junit=SuiteReport(), coverage=CoverageReport(),
            )
        if task != "test":
            return RunResult(
                task=task,
                exit_code=0,
                output="",
                junit=_suite(passed=("e2e::ok",)) if task == "e2e" else SuiteReport(),
                coverage=CoverageReport(),
            )
        if leftover_tests:
            return leftover_tests.pop(0)
        return _run(passed=("tests/test_health.py::test_health",), failed=())

    monkeypatch.setattr(contract_mod.Contract, "run", fake_run)
    monkeypatch.setattr(implementer.Contract, "run", fake_run)


def test_the_loops_own_plan_write_is_bookkeeping(tmp_path, monkeypatch):
    """#501. `plan.save` writes steps.jsonl once before the test phase, and
    `_mark_proven` rewrites it again on every code turn to record which
    steps a passing test proved. Both are this loop's own writes, and
    neither may read back as a scope violation.

    AC-1 already has a passing test on the first code turn here, so
    `_mark_proven` changes steps.jsonl's bytes on iteration 1, not the last
    iteration. Lint fails once, forcing a second code turn: without
    refreshing `last_steps_bytes` right after that first `_mark_proven`
    write, iteration 2's scan would compare against the stale,
    pre-iteration-1 bytes and read the loop's own iteration-1 write as a
    doer's."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs_and_lint(
        monkeypatch,
        test_runs=[
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
            _run(passed=(health, new_test)),
        ],
        lint_oks=[False, True],
    )
    backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
            [],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=3, write_trace=True)

    assert trace["gate"] == "pass"
    assert not trace.get("scope_violations")
    assert len(trace["iterations"]) == 2
    assert (Path(trace["repo"]) / "steps.jsonl").exists()


def test_a_doer_that_rewrites_the_finish_files_on_resume_is_a_scope_violation(tmp_path, monkeypatch):
    """#501, judge of PR #527, follow-up 3. `.harness/last-implementer.json`
    and `.harness/receipt.json` are normally written only once, by
    `_finish`, after this run's last scan -- a fresh run's own scans never
    see them at all. A resumed run is different: both files are already on
    disk before this run's first scan, left there by the run being resumed,
    and used to stay in the blanket bookkeeping exclusion for every scan of
    this run too. `last_output_bytes` now captures both at the top of
    `run`, the same way `state.json`'s bytes are captured, so a doer that
    rewrites either mid-resume reads as a scope violation, not bookkeeping."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health,), failed=(new_test,)),  # code iteration 1: still red
        ],
    )
    first_backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [],  # the code turn writes nothing: the run is killed before a fix lands
        ]
    )
    first = implementer.run(
        repo=repo, ticket_id="T001", doer=first_backend, budget=1, write_trace=True
    )
    assert first["gate"] == "escalate"
    worktree = Path(first["repo"])
    state = json.loads((worktree / ".harness" / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "code"  # resume_into_code, or this test proves nothing

    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,), failed=(new_test,)),  # baseline of the resumed run
            _run(passed=(health, new_test)),              # code iteration 1: now green
        ],
    )
    second_backend = ScriptedBackend(
        [
            [
                ("app/greet.py", "def greet():\n    return 'hello'\n"),
                (".harness/last-implementer.json", '{"evil": true}'),
                (".harness/receipt.json", '{"evil": true}'),
            ],
        ]
    )
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=3, resume=True, write_trace=True,
    )

    assert second["gate"] != "pass"
    assert ".harness/last-implementer.json" in second["scope_violations"]
    assert ".harness/receipt.json" in second["scope_violations"]


def test_a_forged_state_json_overwrite_is_overwritten_back_by_the_loop(tmp_path, monkeypatch):
    """Judge's blocker on PR #500, second half. state.json is one of the
    loop's own named outputs, so a doer overwriting it mid-test-phase is not
    itself flagged as a scope violation. The smallest correct rule: the
    loop's own next checkpoint always wins, because it reads the file back
    and only ever sets the five keys it manages to values it just computed
    itself, never the doer's. A forged phase/red_ids/preexisting/
    test_phase_files/test_phase_attempts never survives past that write."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(
        monkeypatch,
        [_run(passed=(health,)), _run(passed=(health,)), _run(passed=(health,))],
    )
    forged = json.dumps(
        {
            "phase": "code",
            "red_ids": ["evil"],
            "preexisting": ["haha"],
            "test_phase_files": ["nope"],
            "test_phase_attempts": 999,
        }
    )
    backend = ScriptedBackend([[(".harness/state.json", forged)], []])

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=2, write_trace=True)

    assert trace["gate"] == "escalate"
    state = json.loads(
        (Path(trace["repo"]) / ".harness" / "state.json").read_text(encoding="utf-8")
    )
    assert state["test_phase_attempts"] == 2
    assert state["red_ids"] == []
    assert state["preexisting"] == []
    assert state["phase"] == "test"


def test_a_forged_state_json_during_the_code_phase_escalates_at_finish(tmp_path, monkeypatch):
    """Judge's second blocker on PR #500. The code loop has no per-attempt
    checkpoint, so a doer that forges state.json on a code turn is only
    caught when `_finish` reads the file back before its own terminal
    write, comparing against the "code" checkpoint's own bytes from just
    before the code loop started. The forged bytes never survive to disk,
    and the escalate names the tampered path."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health,), failed=(new_test,)),  # code turn: still red, doer forges instead
        ],
    )
    forged = json.dumps(
        {
            "phase": "test",
            "red_ids": ["evil"],
            "preexisting": ["haha"],
            "test_phase_files": [],
            "test_phase_attempts": 999,
        }
    )
    backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [(".harness/state.json", forged)],
        ]
    )

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "escalate"
    assert ".harness/state.json" in trace["scope_violations"]
    state = json.loads(
        (Path(trace["repo"]) / ".harness" / "state.json").read_text(encoding="utf-8")
    )
    assert state["red_ids"] == [new_test]
    assert state["preexisting"] == []
    assert state["phase"] == "code"


def test_resume_after_a_killed_code_phase_reenters_the_code_loop(tmp_path, monkeypatch):
    """A killed code phase checkpoints state.json at phase="code". --resume
    must not call the test-implementer backend again -- it must not rewrite
    tests/test_greet.py -- must keep the checkpointed `preexisting`, and must
    reuse the stored `red_ids` rather than a freshly computed red gate."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),                      # baseline
            _run(passed=(health,), failed=(new_test,)),   # after the test-phase attempt
            _run(passed=(health,), failed=(new_test,)),   # code iteration 1: still red
        ],
    )
    first_backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [],  # the code turn writes nothing: the run is killed before a fix lands
        ]
    )
    first = implementer.run(
        repo=repo, ticket_id="T001", doer=first_backend, budget=1, write_trace=True
    )
    assert first["gate"] == "escalate"
    worktree = Path(first["repo"])
    state = json.loads((worktree / ".harness" / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "code"
    assert state["red_ids"] == [new_test]
    assert state["preexisting"] == []
    test_file = worktree / "tests" / "test_greet.py"
    written_before_resume = test_file.read_text(encoding="utf-8")

    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,), failed=(new_test,)),  # baseline of the resumed run
            _run(passed=(health, new_test)),              # code iteration 1: now green
        ],
    )
    second_backend = RecordingScriptedBackend(
        [[("app/greet.py", "def greet():\n    return 'hello'\n")]]
    )
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=2, resume=True, write_trace=True,
    )

    assert second["gate"] == "pass"
    assert second["red_ids"] == [new_test]
    assert second_backend.calls == 1
    assert second_backend.allows == [["app/**"]]  # never the test implementer's scope
    assert test_file.read_text(encoding="utf-8") == written_before_resume


def test_resume_after_a_killed_test_phase_replays_the_test_phase(tmp_path, monkeypatch):
    """Two silent test turns leave state.json checkpointed at phase="test",
    never "code". --resume must call the test-implementer backend again
    rather than jump straight to the code loop."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    first = implementer.run(
        repo=repo, ticket_id="T001", doer=ScriptedBackend([]), budget=2, write_trace=True
    )
    assert first["gate"] == "escalate"
    worktree = Path(first["repo"])
    state = json.loads((worktree / ".harness" / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "test"

    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),                       # baseline of the resumed run
            _run(passed=(health,), failed=(new_test,)),    # the replayed test-phase attempt
            _run(passed=(health, new_test)),               # code iteration 1
        ],
    )
    second_backend = RecordingScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=1, resume=True, write_trace=True,
    )

    assert second["gate"] == "pass"
    assert second["red_ids"] == [new_test]
    assert second_backend.calls == 2
    assert second_backend.allows[0] == ["tests/**"]
    assert (worktree / "tests" / "test_greet.py").exists()


def test_empty_resume_exits_1_with_one_line(tmp_path, capsys):
    """No worktree has ever run for this ticket, so there is no state.json
    to resume from. A resume must never create one on its way to failing:
    that would be a side effect the caller never asked for."""
    repo = _git_repo(tmp_path / "repo")
    resolved_repo = repo.resolve()
    worktree_path = resolved_repo.parent / f"{resolved_repo.name}.worktrees" / "T001"

    exit_code = implementer.main(
        ["--repo", str(repo), "--ticket", "T001", "--doer", "none", "--resume"]
    )

    assert exit_code == 1
    out = capsys.readouterr().out.strip()
    assert out.count("\n") == 0
    assert "nothing to resume" in out
    assert not worktree_path.exists()


def test_resume_with_a_worktree_but_no_state_json_exits_1(tmp_path, monkeypatch):
    """A worktree can exist with no state.json at all: nothing ever
    checkpointed, or a kill before the very first attempt did. --resume must
    still refuse, distinctly from the no-worktree-at-all case above."""
    repo = _git_repo(tmp_path / "repo")
    _patch_runs(monkeypatch, [])  # _bootstrap's `task setup` fallback needs no real task CLI
    implementer._worktree(repo, "T001")  # a plain, non-resume worktree: no run() yet

    with pytest.raises(implementer.ContractError, match="nothing to resume"):
        implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), resume=True)


def test_resume_after_a_passed_run_exits_1_with_one_line(tmp_path, monkeypatch, capsys):
    """A run that already passed has nothing left to resume."""
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
    implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    exit_code = implementer.main(
        ["--repo", str(repo), "--ticket", "T001", "--doer", "none", "--resume"]
    )

    assert exit_code == 1
    out = capsys.readouterr().out.strip()
    assert out.count("\n") == 0
    assert "nothing to resume" in out
    assert "already passed" in out


def test_resume_does_not_reset_the_worktree(tmp_path, monkeypatch):
    """A5's `test_rerun_without_resume_starts_from_a_reset_tree` proves the
    opposite: a fresh, non-resume run resets the worktree. --resume must
    not, or a killed run's own code would be thrown away exactly when
    resuming needs it most."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    first = implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)
    worktree = Path(first["repo"])
    (worktree / "app" / "leftover.txt").write_text("from the killed run\n", encoding="utf-8")

    resumed = implementer._worktree(repo, "T001", resume=True)

    assert resumed == worktree
    assert (worktree / "app" / "leftover.txt").exists()


def test_trace_carries_test_phase_attempts_and_a_resume_continues_the_count(
    tmp_path, monkeypatch
):
    """Folded finding, judge of PR #490. `trace["test_phase"]` used to be
    overwritten every attempt, so a retry never showed up in the trace. It
    now carries an `attempts` count, and a resumed replay continues counting
    rather than starting back at 1."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    first = implementer.run(
        repo=repo, ticket_id="T001", doer=ScriptedBackend([]), budget=2, write_trace=True
    )
    assert first["test_phase"]["attempts"] == 2
    worktree = Path(first["repo"])
    state = json.loads((worktree / ".harness" / "state.json").read_text(encoding="utf-8"))
    assert state["test_phase_attempts"] == 2

    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
        ],
    )
    second_backend = ScriptedBackend(
        [[("tests/test_greet.py", "def test_ac1():\n    assert False\n")]]
    )
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=1, resume=True, write_trace=True,
    )

    assert second["test_phase"]["attempts"] == 3


def test_empty_test_phase_signature_has_its_own_wording(tmp_path, monkeypatch):
    """Folded finding, judge of PR #490. `gates.decide`'s generic repeat-
    failure wording names an empty signature as "unknown", which reads as a
    bug report. The test phase names it plainly instead."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=ScriptedBackend([]), budget=2, write_trace=True
    )

    assert trace["gate"] == "escalate"
    assert trace["reason"] == "two test turns wrote nothing. The loop is not converging."
    assert "unknown" not in trace["reason"]


def test_state_json_with_a_string_runs_is_corrupt(tmp_path, monkeypatch):
    """Folded finding, judge of PR #497 (A5). A `runs` that parses as JSON
    but is not an int used to reach `previous_runs + 1` and raise
    `TypeError` well after the corrupt-state guard was supposed to catch
    it. It must raise `ContractError` instead, same as a truncated file."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    first = implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)
    state_path = Path(first["repo"]) / ".harness" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["runs"] = "1"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(implementer.ContractError, match="corrupt"):
        implementer.run(repo=repo, ticket_id="T001", doer=doers.NoneBackend(), budget=1)


def test_resume_does_not_recopy_an_edited_ticket(tmp_path, monkeypatch):
    """Judge's blocker on PR #500. A resume must not re-copy the ticket: an
    enhancer edit made in the source repo between the kill and the resume
    must not reach the worktree, or it would show up as an untracked diff
    to tickets/T001.md, a path neither role's scope covers."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health,), failed=(new_test,)),
        ],
    )
    first_backend = ScriptedBackend(
        [[("tests/test_greet.py", "def test_ac1():\n    assert False\n")], []]
    )
    first = implementer.run(
        repo=repo, ticket_id="T001", doer=first_backend, budget=1, write_trace=True
    )
    assert first["gate"] == "escalate"
    worktree = Path(first["repo"])
    ticket_before_resume = (worktree / "tickets" / "T001.md").read_text(encoding="utf-8")

    # The enhancer edits the source repo's ticket, uncommitted, while the
    # killed run's worktree sits untouched.
    (repo / "tickets" / "T001.md").write_text(
        ticket_before_resume.replace("hello", "hello, edited after the kill"),
        encoding="utf-8",
    )

    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    second_backend = ScriptedBackend([[("app/greet.py", "def greet():\n    return 'hello'\n")]])
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=2, resume=True, write_trace=True,
    )

    assert second["gate"] == "pass"
    assert (worktree / "tickets" / "T001.md").read_text(encoding="utf-8") == ticket_before_resume
    assert not any("tickets/" in v for v in second.get("scope_violations", []))


# -- A9 (#437 #422): --planner derived|sdk|deep ------------------------------


def _step_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line)["id"] for line in text.splitlines() if line.strip()]


class PlanningScriptedBackend(ScriptedBackend):
    """A `ScriptedBackend` with a `plan()` that must never be called under
    the default planner. Calling it fails the test that holds it, not the
    run: `run()` itself has no assertion that would turn this into a
    trace."""

    def plan(self, *, repo: Path, prompt: str) -> doers.DoerResult:
        raise AssertionError("the derived planner must not call backend.plan")


def test_default_planner_never_calls_backend_plan(tmp_path, monkeypatch):
    """A9 (#437 #422), test 1 of 5. --planner defaults to derived: plan_for,
    no model, and backend.plan is never even asked for."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=PlanningScriptedBackend([]), budget=2, write_trace=True
    )

    # A silent doer still escalates on the red gate, exactly as it did before
    # this unit. The interesting assertion is that PlanningScriptedBackend's
    # own plan() never raised its AssertionError getting here.
    assert trace["gate"] == "escalate"


def test_a_kind_path_goal_payload_never_becomes_a_plan_and_escalates(tmp_path, monkeypatch):
    """A9 (#437 #422), test 3 of 5. The planner's only contract is
    id/ticket/role/action/validation. A payload shaped like a different
    schema must never become steps.jsonl: Plan.load rejects it, and the run
    ends in an escalate trace, never an uncaught error."""
    repo = _git_repo(tmp_path / "repo")
    _patch_runs(monkeypatch, [])

    class BadPlanBackend(doers.Backend):
        name = "bad-planner"

        def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
            raise AssertionError("a rejected plan must never reach the test or code phase")

        def plan(self, *, repo: Path, prompt: str) -> doers.DoerResult:
            (repo / "steps.jsonl").write_text(
                json.dumps({"kind": "feature", "path": "app/x.py", "goal": "do it"}) + "\n",
                encoding="utf-8",
            )
            return doers.DoerResult(output="wrote a plan")

    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=BadPlanBackend(), planner="sdk", budget=1,
    )

    assert trace["gate"] == "escalate"
    assert "the planner produced an unusable plan" in trace["reason"]
    # Not just the generic prefix: this must be Plan.load's own missing-field
    # message, or this assertion would pass just as well if plan.validate had
    # fired instead, and the two failure modes would be indistinguishable.
    assert "is missing: id, ticket, role, action, validation" in trace["reason"]


def test_plan_validate_still_refuses_a_plan_that_covers_no_criterion(tmp_path, monkeypatch):
    """#422. `plan.validate` must run after `Plan.load`'s schema check, not
    only be implied by it: a payload can satisfy `Plan.load` (every field
    present, every role known) and still be unusable because no step's
    `criterion` covers the ticket's acceptance criteria. Deleting the
    `plan.validate(criteria=...)` call in `run()` leaves this green, so this
    is the test #422 names for that revert."""
    repo = _git_repo(tmp_path / "repo")
    _patch_runs(monkeypatch, [])

    class NoCriterionPlanBackend(doers.Backend):
        name = "no-criterion-planner"

        def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
            raise AssertionError("a rejected plan must never reach the test or code phase")

        def plan(self, *, repo: Path, prompt: str) -> doers.DoerResult:
            lines = [
                json.dumps(
                    {
                        "id": "S1",
                        "ticket": "T001",
                        "role": "test_implementer",
                        "action": "write a test",
                        "validation": "it fails",
                        "status": "todo",
                    }
                ),
                json.dumps(
                    {
                        "id": "S2",
                        "ticket": "T001",
                        "role": "code_implementer",
                        "action": "write the code",
                        "validation": "the test passes",
                        "status": "todo",
                    }
                ),
            ]
            (repo / "steps.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            return doers.DoerResult(output="wrote a plan")

    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=NoCriterionPlanBackend(), planner="sdk", budget=1,
    )

    assert trace["gate"] == "escalate"
    assert "the planner produced an unusable plan" in trace["reason"]
    assert "these acceptance criteria map to no step" in trace["reason"]
    assert "AC-1" in trace["reason"]


def test_doer_none_and_reference_force_derived_regardless_of_planner_flag(
    tmp_path, monkeypatch, capsys
):
    """A9 (#437 #422), test 4 of 5. A live planner with no live doer produces
    a plan nothing can execute, so --doer none and --doer reference force
    derived even when --planner names a live one."""
    health = "tests/test_health.py::test_health"

    none_repo = _git_repo(tmp_path / "none-repo")
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])
    exit_code = implementer.main(
        ["--repo", str(none_repo), "--ticket", "T001", "--doer", "none",
         "--planner", "sdk", "--budget", "1"]
    )
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "gate: escalate" in out
    assert "red gate: no new test was observed failing" in out
    assert "planner produced an unusable plan" not in out

    ref_repo = _git_repo(tmp_path / "ref-repo")
    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    (ref_repo / "tests" / "test_greet.py").write_text(
        "def test_ac1():\n    assert False\n", encoding="utf-8"
    )
    (ref_repo / "app" / "greet.py").write_text(
        "def greet():\n    return 'hello'\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "tests/test_greet.py", "app/greet.py"], cwd=ref_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "known good answer"], cwd=ref_repo, check=True, capture_output=True
    )
    subprocess.run(["git", "branch", "known-good"], cwd=ref_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "reset", "--hard", "HEAD~1"], cwd=ref_repo, check=True, capture_output=True
    )

    exit_code = implementer.main(
        ["--repo", str(ref_repo), "--ticket", "T001", "--doer", "reference",
         "--planner", "deep", "--budget", "1"]
    )
    assert exit_code == 0
    assert "gate: pass" in capsys.readouterr().out


def test_resume_loads_the_saved_plan_and_never_replans(tmp_path, monkeypatch):
    """A9 (#437 #422), test 5 of 5. A regenerated plan after a killed code
    phase would renumber the steps the stored red_ids were proven against, so
    --resume must Plan.load steps.jsonl rather than call plan_for again."""
    repo = _git_repo(tmp_path / "repo")
    health = "tests/test_health.py::test_health"
    _patch_runs(monkeypatch, [_run(passed=(health,)), _run(passed=(health,))])

    first = implementer.run(
        repo=repo, ticket_id="T001", doer=ScriptedBackend([]), budget=2, write_trace=True
    )
    assert first["gate"] == "escalate"
    worktree = Path(first["repo"])
    saved_ids = _step_ids(worktree / "steps.jsonl")

    calls: list[int] = []
    real_plan_for = implementer.plan_for

    def spy_plan_for(*args, **kwargs):
        calls.append(1)
        return real_plan_for(*args, **kwargs)

    monkeypatch.setattr(implementer, "plan_for", spy_plan_for)

    new_test = "tests/test_greet.py::test_AC-1"
    _patch_runs(
        monkeypatch,
        [
            _run(passed=(health,)),
            _run(passed=(health,), failed=(new_test,)),
            _run(passed=(health, new_test)),
        ],
    )
    second_backend = ScriptedBackend(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    second = implementer.run(
        repo=repo, ticket_id="T001", doer=second_backend, budget=1, resume=True, write_trace=True,
    )

    assert second["gate"] == "pass"
    assert calls == []
    # Not a byte-for-byte compare: the code phase marks a step done with
    # evidence and re-saves. The ids proving no renumbering happened are
    # what a resume actually has to protect.
    assert _step_ids(worktree / "steps.jsonl") == saved_ids
