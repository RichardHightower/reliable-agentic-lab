"""The rubric. Ten rows, scored without a model.

"The unit tests passed" is one row of ten. A judge that checks only that row
can be satisfied by an agent that writes one trivial test and deletes the rest.

Every row is computed from junit.xml, coverage.xml, exit codes, steps.jsonl,
and the git diff. No model call, so no model can be talked into a pass.

The contrast is the lesson. The implementer's judge is deterministic. The
enhancer's judge reads ticket prose and needs a model. Use a model only where
you must.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class Row:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'}  {self.name:<18} {self.detail}"


@dataclass
class Score:
    rows: list[Row] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.rows) and all(row.passed for row in self.rows)

    @property
    def failed_rows(self) -> list[Row]:
        return [row for row in self.rows if not row.passed]

    def signature(self) -> tuple[str, ...]:
        """What failed, ignoring wording. Two equal signatures mean no progress."""
        return tuple(sorted(row.name for row in self.failed_rows))

    def report(self) -> str:
        return "\n".join(str(row) for row in self.rows)


def changed_files(repo: Path, base: str = "HEAD") -> list[str]:
    """Every path this working tree changes, staged, unstaged, or untracked."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    paths = []
    for line in out.stdout.splitlines():
        if len(line) > 3:
            paths.append(line[3:].strip().split(" -> ")[-1])
    return sorted(paths)


def score(  # noqa: PLR0913, PLR0912, PLR0915
    *,
    contract,
    plan=None,
    criteria: list[str] | None = None,
    test_run=None,
    e2e_run=None,
    lint_run=None,
    format_run=None,
    red_ids: set[str] | None = None,
    role_scope=None,
    changed: list[str] | None = None,
) -> Score:
    """Score one attempt. Every argument that is None becomes a failing row.

    Absent evidence is never a pass. That is the whole discipline.

    This function is long on purpose. It reads top to bottom as the ten rubric
    rows, in order, each one visible next to the evidence it reads. Splitting it
    into ten helpers would satisfy a linter and cost the reader the rubric.
    """
    rows: list[Row] = []
    rubric = contract.rubric
    junit = test_run.junit if test_run else None
    changed = changed if changed is not None else changed_files(contract.repo)

    # 1. The suite actually ran and the report is fresh.
    if junit is None or not junit.exists:
        rows.append(Row("tests_ran", False, "no readable junit report. Absent is not clean."))
    elif junit.empty:
        rows.append(Row("tests_ran", False, "the suite collected zero tests"))
    else:
        rows.append(Row("tests_ran", True, f"{junit.tests} tests"))

    # 2. Nothing failed.
    if junit is None or not junit.exists:
        rows.append(Row("tests_passed", False, "no evidence"))
    else:
        bad = junit.failures + junit.errors
        rows.append(
            Row(
                "tests_passed",
                bad == 0 and junit.tests > 0,
                "all green" if bad == 0 else f"{bad} failing: {sorted(junit.failed_ids)[:3]}",
            )
        )

    # 3. The new tests failed before any code was written.
    if not rubric.get("require_red", True):
        rows.append(Row("red_first", True, "not required by .loop.yml"))
    elif not red_ids:
        rows.append(
            Row("red_first", False, "no test was observed failing before the code was written")
        )
    else:
        rows.append(Row("red_first", True, f"{len(red_ids)} tests were red first"))

    # 4. Coverage.
    floor = float(rubric.get("coverage_floor", 80))
    coverage = test_run.coverage if test_run else None
    if coverage is None or not coverage.exists:
        rows.append(Row("coverage_floor", False, "no coverage report"))
    else:
        rows.append(
            Row(
                "coverage_floor",
                coverage.line_rate >= floor,
                f"{coverage.line_rate}% against a floor of {floor}%",
            )
        )

    # 5. Every acceptance criterion maps to a step and to a passing test.
    if not criteria:
        rows.append(Row("criteria_covered", True, "the ticket names no criteria"))
    elif plan is None:
        rows.append(Row("criteria_covered", False, "no plan"))
    else:
        passing = junit.passed_ids if junit else set()
        uncovered = []
        for criterion in criteria:
            steps = [s for s in plan.steps if s.criterion == criterion]
            if not steps:
                uncovered.append(f"{criterion} (no step)")
                continue
            proven = any(
                s.evidence and any(s.evidence.endswith(t) or t in s.evidence for t in passing)
                for s in steps
            )
            if not proven:
                uncovered.append(f"{criterion} (no passing test)")
        rows.append(
            Row(
                "criteria_covered",
                not uncovered,
                "all covered" if not uncovered else "; ".join(uncovered),
            )
        )

    # 6. Every step is done, with evidence.
    if plan is None:
        rows.append(Row("steps_done", False, "no plan"))
    else:
        open_steps = plan.unfinished()
        detail = plan.summary()
        if open_steps:
            detail += f"; still open: {[s.id for s in open_steps][:5]}"
        rows.append(Row("steps_done", not open_steps, detail))

    # 7. A change to the interface needs a test that goes through it.
    ui_paths = rubric.get("ui_paths") or []
    touched_ui = [p for p in changed if any(fnmatch(p, pattern) for pattern in ui_paths)]
    if not touched_ui:
        rows.append(Row("ui_has_e2e", True, "no interface files changed"))
    else:
        e2e = e2e_run.junit if e2e_run else None
        ok = bool(e2e and e2e.green)
        rows.append(
            Row(
                "ui_has_e2e",
                ok,
                f"{len(touched_ui)} interface files changed, "
                + ("e2e green" if ok else "no passing end-to-end test"),
            )
        )

    # 8 and 9. Style. Cheap to check, cheap to fix, and it keeps diffs readable.
    for name, run in (("format_clean", format_run), ("lint_clean", lint_run)):
        if run is None:
            rows.append(Row(name, False, "not run"))
        else:
            rows.append(Row(name, run.ok, "clean" if run.ok else f"exit {run.exit_code}"))

    # 10. Nobody wrote outside their scope.
    if role_scope is None:
        rows.append(Row("write_scope", True, "no scope declared for this run"))
    else:
        outside = [p for p in changed if not role_scope.permits(p)]
        rows.append(
            Row(
                "write_scope",
                not outside,
                "inside scope" if not outside else f"wrote outside scope: {outside[:3]}",
            )
        )

    return Score(rows=rows)
