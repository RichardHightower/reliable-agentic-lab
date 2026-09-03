"""Drive implementer.run with a scripted backend. No model. No public CRM."""

from __future__ import annotations

import subprocess
from pathlib import Path

import contract as contract_mod
import doers
import implementer
import roles
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
    assert trace["judge"]["done"] is True
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


def test_simple_field_rename_reaches_a_read_only_judge(
    tmp_path, monkeypatch, fake_langchain, fake_deepagents
):
    """A tiny offline story: plan, change one test, rename backend/UI fields,
    then enter a judge-only graph that has no way to weaken that test.

    This must stay entirely scripted. It is the fast regression for the phase
    boundary, not a live-model proxy that can hang or spend a token.
    """
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
    plan = (repo / "steps.jsonl").read_text(encoding="utf-8")
    assert "display_name" in plan
    assert '"role": "test_implementer"' in plan
    assert '"role": "code_implementer"' in plan
    assert test_path.read_text(encoding="utf-8") == renamed_test
    assert backend_path.read_text(encoding="utf-8") == renamed_backend
    assert form_path.read_text(encoding="utf-8") == renamed_form
    assert "task_title" not in backend_path.read_text(encoding="utf-8")
    assert "taskTitle" not in form_path.read_text(encoding="utf-8")

    # Judge mode is a separate graph: it admits only the read-only judge. The
    # former code doer is absent, and its scoped writer still refuses tests.
    contract = contract_mod.Contract(repo)
    assert roles.build_agent(contract, subagent_names=frozenset({"judge"})) == "agent"
    judge_specs = fake_deepagents["subagents"]
    assert [spec["name"] for spec in judge_specs] == ["judge"]
    assert [tool.__name__ for tool in judge_specs[0]["tools"]] == ["read_file"]

    code_spec = next(
        spec for spec in roles.subagents_for(contract) if spec["name"] == "code-implementer"
    )
    refused = code_spec["tools"][1]("tests/test_task_fields.py", "def test_weakened(): pass\n")
    assert refused.startswith("REFUSED")
    assert test_path.read_text(encoding="utf-8") == renamed_test


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
    implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)
    path = repo / ".harness" / "receipt.json"
    assert path.exists()
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert "tree_hash" in payload
    assert "green" in payload
    assert "written_at" in payload
