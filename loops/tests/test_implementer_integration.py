"""End-to-end checks for the implementer against a real target repo.

These are the checks that prove the design rather than the code. Each one is an
attack the harness has to survive.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from loops import doers, gates
from loops.contract import Contract
from loops.implementer import run
from loops.roles import ScopeViolation, build

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_crm() -> Path | None:
    candidates = [
        Path(os.environ["LOOP_TEST_REPO"]) if os.environ.get("LOOP_TEST_REPO") else None,
        REPO_ROOT / "work" / "northwind-field-crm",
        REPO_ROOT.parent / "northwind-field-crm",
    ]
    for path in candidates:
        if path and (path / ".loop.yml").is_file():
            return path
    return None


CRM = _find_crm()
has_crm = pytest.mark.skipif(CRM is None, reason="no target repo; run `task setup`")


@pytest.fixture()
def clean_crm():
    """Reset the target before and after. The loop leaves it dirty on purpose."""

    def reset():
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
        subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
        subprocess.run(["git", "checkout", "-q", "main"], cwd=CRM, check=False)
        (CRM / "steps.jsonl").unlink(missing_ok=True)

    reset()
    yield CRM
    reset()


@has_crm
def test_the_reference_run_passes_every_rubric_row(clean_crm):
    trace = run(repo=clean_crm, ticket_id="T001", doer="reference", write_trace=False)
    assert trace["gate"] == gates.PASS, trace.get("rubric")
    assert trace["red_ids"], "the new tests must have been red before the code was written"


@has_crm
def test_a_doer_that_writes_nothing_is_stopped_by_the_red_gate(clean_crm):
    """No test was ever red, so nothing has been proven. Refuse to continue."""
    trace = run(repo=clean_crm, ticket_id="T001", doer="none", write_trace=False)
    assert trace["gate"] == gates.ESCALATE
    assert "red gate" in trace["reason"]


@has_crm
def test_the_reference_doer_obeys_the_role_write_scope(clean_crm):
    """Even the offline stand-in is bound by scope, or the split is cosmetic."""
    backend = doers.ReferenceBackend("known-good")
    result = backend.run(repo=clean_crm, prompt="", allow=["tests/**"])
    assert result.wrote, "it should have written the tests"
    assert all(path.startswith("tests/") for path in result.wrote), result.wrote

    result = backend.run(repo=clean_crm, prompt="", allow=["app/**"])
    assert all(path.startswith("app/") for path in result.wrote), result.wrote


@has_crm
def test_a_code_implementer_cannot_write_a_test(clean_crm):

    coder = build(Contract(clean_crm))["code_implementer"]
    coder.write("app/scratch.py", "x = 1\n")
    with pytest.raises(ScopeViolation):
        coder.write("tests/test_smoke.py", "def test_x():\n    assert True\n")
    (clean_crm / "app" / "scratch.py").unlink(missing_ok=True)


@has_crm
def test_weakening_a_test_after_the_fact_is_caught_by_write_scope(clean_crm):
    """The realistic cheat: a CLI agent edits a test to reach green.

    In-process scope cannot stop a subprocess. The rubric's write_scope row can,
    because it reads the diff. One gate is never enough.
    """

    coder = build(Contract(clean_crm))["code_implementer"]
    # Simulate the subprocess doing it behind the role's back.
    (clean_crm / "tests" / "test_smoke.py").write_text("def test_nothing():\n    assert True\n")
    changed = ["app/models.py", "tests/test_smoke.py"]
    assert coder.violations(changed) == ["tests/test_smoke.py"]
