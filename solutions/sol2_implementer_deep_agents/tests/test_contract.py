"""#576, #585. `rubric.ui_has_e2e` demands a suite no role was ever asked to write.

`ui_has_e2e` (`rubric.py`) demands a green `tests/e2e` suite whenever a
changed file matches `.loop.yml`'s `rubric.ui_paths`. A live round-5 trace
found a target repo whose code implementer is denied `tests/**` and whose
test implementer runs once, before the code phase, and is never asked for
an e2e suite: nine of ten rubric rows passed, the loop retried, and it
escalated after spending a turn on an attempt no scoped role could have
satisfied.

Judge of PR #582: the defect is temporal, not scope-shaped. `tests/**`
already permits `tests/e2e/**` (fnmatch's `*` has no notion of a path
separator), so a role able to write there always existed; the gap is that
nothing in the loop ever asks it to.

Two things pin the fix: `Contract.validate` still refuses a `.loop.yml`
that makes `ui_has_e2e` structurally unsatisfiable (no role able to write
`tests/e2e/**` at all), naming the row and the path; and `plan_for` /
`_test_prompt` now ask the test implementer for an e2e suite, only when
`ui_paths` are declared, so a test implementer that reads its own prompt
writes it on the first pass.

#585, judge of PR #582: PR #582's own fix folded the instruction into
`plan_for` alone, so `--planner sdk` and `--planner deep`
(`_plan_from_backend`, which never calls `plan_for`) reintroduced the same
dead end on a backend-planned run with declared `ui_paths`.
`_fold_ui_e2e_instruction` now applies it once, in `run()`, after any
planner has produced a plan, so `derived`, `sdk`, and `deep` all agree.

Helpers are copied from `tests/test_implementer.py`, not imported, the same
way `tests/test_parity.py` copies its own fixtures.
"""

from __future__ import annotations

import json
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

# #585. The same fixture, minus `rubric.ui_paths`: the negative half of the
# backend-planner test needs a target that never declares it, the same way
# the derived planner's own negative case never declares it.
NO_UI_LOOP_YML = UI_LOOP_YML.replace('  ui_paths: ["app/templates/**"]\n', "")

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


def _git_repo(path: Path, *, loop_yml: str = UI_LOOP_YML) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "lab@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "lab"], cwd=path, check=True)
    (path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (path / ".loop.yml").write_text(loop_yml, encoding="utf-8")
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


class PromptFollowingBackend(doers.Backend):
    """Writes the e2e suite only when its own prompt actually asks for one.

    Not `ScriptedBackend`, which hands the test phase `tests/e2e/test_ui.py`
    to write unconditionally -- judge of PR #582: that proves the rubric row
    can go green when the suite exists, never that the loop asked for it.
    This one reads the prompt the way a real model would.
    """

    name = "prompt-following"

    def __init__(self):
        self.test_prompt = ""

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        wrote: list[str] = []
        if any(pattern.startswith("tests/") for pattern in allow):
            self.test_prompt = prompt
            unit = repo / "tests" / "test_greet.py"
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text("def test_ac_1_greets():\n    assert True\n", encoding="utf-8")
            wrote.append("tests/test_greet.py")
            if "tests/e2e/" in prompt:
                e2e = repo / "tests" / "e2e" / "test_ui.py"
                e2e.parent.mkdir(parents=True, exist_ok=True)
                e2e.write_text("def test_ui():\n    assert True\n", encoding="utf-8")
                wrote.append("tests/e2e/test_ui.py")
        elif any(pattern.startswith("app/") for pattern in allow):
            template = repo / "app" / "templates" / "greet.html"
            template.parent.mkdir(parents=True, exist_ok=True)
            template.write_text("<p>hello</p>\n", encoding="utf-8")
            wrote.append("app/templates/greet.html")
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


def test_the_test_implementer_is_asked_for_an_e2e_suite_only_when_ui_paths_are_declared(
    tmp_path, monkeypatch
):
    """#576, judge of PR #582. Round 5's defect was temporal, not scope-shaped:
    the only role permitted to write `tests/e2e/**` runs once, before the red
    gate, and was never asked to use that permission. `plan_for` now folds
    `UI_E2E_INSTRUCTION` into a test step's own action when `.loop.yml`
    declares `rubric.ui_paths`, and `_test_prompt` surfaces it; a test
    implementer that actually reads its own prompt (`PromptFollowingBackend`,
    not one handed the answer regardless) writes the e2e suite the row
    demands on the first pass, against a repo that ships no `tests/e2e/` of
    its own, and the loop does not escalate on `ui_has_e2e` alone.

    The negative half lives in the same test: a ticket whose `.loop.yml`
    declares no `ui_paths` gets no e2e instruction in its plan or its prompt
    at all.
    """
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

    backend = PromptFollowingBackend()

    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, write_trace=True)

    assert "tests/e2e/" in backend.test_prompt, backend.test_prompt
    assert "ui_has_e2e" not in (trace.get("scope_violations") or [])
    assert "PASS  ui_has_e2e" in trace["rubric"], trace["rubric"]
    assert trace["gate"] == "pass", trace.get("reason")

    # Negative: no `ui_paths`, no instruction, anywhere the prompt reads it.
    plain_ticket = implementer.tickets.Ticket(
        id="T002",
        title="x",
        state="ready",
        criteria=[implementer.tickets.Criterion("AC-1", "greet returns hello")],
    )
    plain_plan = implementer._fold_ui_e2e_instruction(
        implementer.plan_for(plain_ticket), None
    )
    assert "tests/e2e/" not in implementer._test_prompt(plain_ticket, plain_plan)


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


class ScriptedPlannerBackend(PromptFollowingBackend):
    """Stands in for `--planner sdk` or `--planner deep`: writes its own
    `steps.jsonl` from `plan()`, the exact shape `_plan_from_backend` reads
    back through `steps.Plan.load`. Test and code turns are inherited from
    `PromptFollowingBackend` unchanged.

    #585. This planner's own steps never carry `UI_E2E_INSTRUCTION` -- the
    point of the test that uses it is that `run()`'s shared fold-in has to
    add it before the test phase ever reads the prompt, the same as it does
    for the derived planner's own steps.
    """

    name = "scripted-planner"

    def plan(self, *, repo: Path, prompt: str) -> doers.DoerResult:
        lines = [
            json.dumps(
                {
                    "id": "S1T",
                    "ticket": "T001",
                    "role": "test_implementer",
                    "action": "Write a test that fails until this holds: AC-1.",
                    "validation": "a test covering AC-1 exists and fails before any code",
                    "criterion": "AC-1",
                    "status": "todo",
                }
            ),
            json.dumps(
                {
                    "id": "S1C",
                    "ticket": "T001",
                    "role": "code_implementer",
                    "action": "Implement AC-1.",
                    "validation": "the test covering AC-1 passes",
                    "criterion": "AC-1",
                    "status": "todo",
                }
            ),
        ]
        (repo / "steps.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return doers.DoerResult(output="wrote a plan")


@pytest.mark.parametrize("planner", ["sdk", "deep"])
def test_a_backend_planned_run_is_also_asked_for_an_e2e_suite(tmp_path, monkeypatch, planner):
    """#585. PR #582 folded `UI_E2E_INSTRUCTION` into `plan_for`, the derived
    planner alone; `_plan_from_backend` (`--planner sdk` or `--planner deep`)
    produces its own steps and never calls `plan_for`, so a backend-planned
    run with declared `ui_paths` reintroduced the `ui_has_e2e` dead end.
    `run()` now folds the instruction in once, after any planner has
    produced a plan (`_fold_ui_e2e_instruction`), so `sdk` and `deep` reach
    the test phase with the same instruction the derived planner carries,
    named exactly once."""
    repo = _git_repo(tmp_path / f"repo-{planner}")
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

    backend = ScriptedPlannerBackend()

    trace = implementer.run(
        repo=repo, ticket_id="T001", doer=backend, planner=planner, write_trace=True
    )

    assert backend.test_prompt.count("tests/e2e/") == 1, backend.test_prompt
    assert "PASS  ui_has_e2e" in trace["rubric"], trace["rubric"]
    assert trace["gate"] == "pass", trace.get("reason")


@pytest.mark.parametrize("planner", ["sdk", "deep"])
def test_a_backend_planned_run_gets_no_e2e_instruction_when_ui_paths_are_empty(
    tmp_path, monkeypatch, planner
):
    """The negative half for the backend planner: a `.loop.yml` that never
    declares `rubric.ui_paths` gets no instruction folded into any planner's
    steps, backend-planned included."""
    repo = _git_repo(tmp_path / f"repo-no-ui-{planner}", loop_yml=NO_UI_LOOP_YML)
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

    backend = ScriptedPlannerBackend()

    implementer.run(repo=repo, ticket_id="T001", doer=backend, planner=planner, write_trace=True)

    assert "tests/e2e/" not in backend.test_prompt, backend.test_prompt


def test_fold_ui_e2e_instruction_never_appears_more_than_once():
    """#585. `_fold_ui_e2e_instruction` is the one place the instruction is
    added, and it has to stay a no-op on a step that already carries it --
    called twice (the shape a `--resume` run takes: once when a plan is
    first produced and saved, once again if anything ever re-ran the
    fold-in against the same loaded plan), the instruction still appears
    exactly once."""
    plan = implementer.plan_for(
        implementer.tickets.Ticket(
            id="T001",
            title="x",
            state="ready",
            criteria=[implementer.tickets.Criterion("AC-1", "greet returns hello")],
        )
    )
    once = implementer._fold_ui_e2e_instruction(plan, ["app/templates/**"])
    twice = implementer._fold_ui_e2e_instruction(once, ["app/templates/**"])
    assert twice.steps[0].action.count("tests/e2e/") == 1
