"""C2 (#443). The cross-port parity contract.

Every behavior this file pins already has a dedicated test in this same
folder, added by an earlier unit (A1 through A9, B1 through B5). This file
does not restate those tests. It is the second, independent check that both
`solutions/sol2_implementer_agent_sdk` and `solutions/sol2_implementer_deep_agents`
still agree on the four behaviors a mutation could break silently in only one
port: the exit mapping, the judge prompt naming a changed path, the
Bash-free cast, and the one-test-per-receipt-branch rule.

This file imports nothing from the sibling port and nothing from a shared
`loops` package. Its helpers are copied from `tests/test_implementer.py`, not
imported from it, the same way `tests/test_receipt.py` copies its own
`_git_repo` rather than reaching into a sibling file. A worker who edits one
port and paraphrases the other should see this file fail here, by name, in
whichever port fell behind.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import doers
import implementer
import roleplan
from contract import CoverageReport, RunResult, SuiteReport

FOLDER = Path(__file__).resolve().parent

# -- the seven receipt.check branches (B1, #427) ----------------------------
#
# Both ports' `tests/test_receipt.py` are independent copies of the same
# fixture file (`scripts/tests/test_receipt.py` is the pattern; neither port
# imports it). Naming the seven tests here, once per port, is what keeps a
# future edit from quietly dropping a branch in only one of them.
PINNED_RECEIPT_TESTS = (
    "test_no_receipt_denies",
    "test_unreadable_receipt_denies",
    "test_a_zero_exit_with_no_report_is_not_green",
    "test_a_red_run_denies_and_names_the_failure",
    "test_a_green_receipt_on_a_dirty_tree_is_denied",
    "test_a_source_edit_newer_than_the_receipt_denies",
    "test_a_green_receipt_matching_this_tree_is_allowed",
)


def test_receipt_check_has_one_test_per_pinned_branch():
    """Every `receipt.check` branch (`receipt.py:116-144`) has a named test in
    this port's own `tests/test_receipt.py`. A port that drops a branch's
    test, or renames it without renaming its twin, fails here by name."""
    tree = ast.parse((FOLDER / "test_receipt.py").read_text(encoding="utf-8"))
    defined = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    missing = [name for name in PINNED_RECEIPT_TESTS if name not in defined]
    assert not missing, f"tests/test_receipt.py dropped: {missing}"


# -- the Bash-free cast (B3, #440; already pinned at tests/test_roles.py:54) -


def test_the_implementer_cast_never_holds_bash(contract):
    """No role in the implementer cast may hold `Bash` (`roleplan.py`).
    Python runs the suite through `contract.run("test")`, so a role with a
    shell buys nothing and costs the whole PreToolUse fence."""
    cast = roleplan.plan(contract, "implementer")
    offenders = [name for name, role in cast.items() if "Bash" in role.tools]
    assert not offenders, f"these roles hold Bash, which the implementer cast may never grant: {offenders}"


# -- the exit mapping, through implementer.main (A5, #432 #434) -------------


def test_main_exit_codes_are_0_pass_2_escalate_1_crash(monkeypatch):
    """`implementer.main` maps a terminal gate to an exit code: 0 on pass, 2
    on escalate, 1 on a `ContractError`. `harness.main`'s own mirror of this
    mapping is pinned separately; this pins `implementer.main`'s own copy,
    monkeypatching only `run` so a broken mapping fails here even if the
    worktree and doer machinery around it are untouched."""
    monkeypatch.setattr(
        implementer, "run", lambda **_kw: {"rubric": "", "gate": "pass", "reason": "ok"}
    )
    assert implementer.main(["--repo", "unused", "--doer", "none"]) == 0, "gate pass must exit 0"

    monkeypatch.setattr(
        implementer,
        "run",
        lambda **_kw: {"rubric": "", "gate": "escalate", "reason": "red gate"},
    )
    assert implementer.main(["--repo", "unused", "--doer", "none"]) == 2, (
        "gate escalate must exit 2"
    )

    def fake_crash(**_kw):
        raise implementer.ContractError("boom")

    monkeypatch.setattr(implementer, "run", fake_crash)
    assert implementer.main(["--repo", "unused", "--doer", "none"]) == 1, (
        "a ContractError must exit 1"
    )


# -- the judge prompt names a changed path (A1, #429) ------------------------
#
# Helpers copied from `tests/test_implementer.py`, not imported from it.

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


class RecordingJudge(ScriptedBackend):
    def __init__(self, script):
        super().__init__(script)
        self.judge_prompts: list[str] = []

    def judge(self, *, repo: Path, prompt: str) -> doers.DoerResult:
        self.judge_prompts.append(prompt)
        return doers.DoerResult(output='{"done": true, "why": "looks right"}')


def _patch_runs(monkeypatch, runs: list[RunResult]):
    import contract as contract_mod  # noqa: PLC0415

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


def test_judge_prompt_names_a_changed_path_through_the_public_surface(tmp_path, monkeypatch):
    """`implementer.run` -> `_ask_judge` puts the code phase's own changed
    paths in the judge prompt, not just the rubric's word for it. Breaking
    that must fail here even though `test_implementer.py` also proves it,
    because this file is what both ports carry identically."""
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

    backend = RecordingJudge(
        [
            [("tests/test_greet.py", "def test_ac1():\n    assert False\n")],
            [("app/greet.py", "def greet():\n    return 'hello'\n")],
        ]
    )
    trace = implementer.run(repo=repo, ticket_id="T001", doer=backend, budget=1, write_trace=True)

    assert trace["gate"] == "pass"
    assert len(backend.judge_prompts) == 1
    assert "app/greet.py" in backend.judge_prompts[0], "the judge prompt dropped the changed path"
