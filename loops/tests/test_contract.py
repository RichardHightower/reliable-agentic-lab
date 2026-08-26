"""Checks for the repo contract. Run with: python -m pytest loops/tests -q"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from loops.contract import (
    Contract,
    ContractError,
    _mini_yaml,
    parse_coverage,
    parse_junit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_crm() -> Path | None:
    """Locate a target repo to check against. Never import it."""
    candidates = []
    if os.environ.get("LOOP_TEST_REPO"):
        candidates.append(Path(os.environ["LOOP_TEST_REPO"]))
    candidates.append(REPO_ROOT / "work" / "northwind-field-crm")
    candidates.append(REPO_ROOT.parent / "northwind-field-crm")
    for path in candidates:
        if (path / "Taskfile.yml").is_file():
            return path
    return None


CRM = _find_crm()
has_crm = pytest.mark.skipif(CRM is None, reason="no target repo found; run `task setup`")


def test_mini_yaml_reads_the_loop_file_shape():
    parsed = _mini_yaml(
        "version: 1\n"
        "roles:\n"
        "  code_implementer:\n"
        '    write_allow: ["app/**"]\n'
        '    write_deny: ["tests/**", "Taskfile.yml"]\n'
        "rubric:\n"
        "  coverage_floor: 78\n"
        "  require_red: true\n"
        "budget:\n"
        "  iterations: 3\n"
        "  usd: 2.00\n"
    )
    assert parsed["version"] == 1
    assert parsed["roles"]["code_implementer"]["write_allow"] == ["app/**"]
    assert parsed["roles"]["code_implementer"]["write_deny"] == ["tests/**", "Taskfile.yml"]
    assert parsed["rubric"]["coverage_floor"] == 78
    assert parsed["rubric"]["require_red"] is True
    assert parsed["budget"]["usd"] == 2.0


def test_missing_junit_is_not_a_pass(tmp_path: Path):
    report = parse_junit(tmp_path / "nope.xml")
    assert report.exists is False
    assert report.green is False


def test_empty_suite_is_not_green(tmp_path: Path):
    path = tmp_path / "junit.xml"
    path.write_text(
        '<testsuites><testsuite name="pytest" tests="0" failures="0" errors="0"/></testsuites>'
    )
    report = parse_junit(path)
    assert report.empty is True
    assert report.green is False


def test_failed_ids_are_separated_from_passed(tmp_path: Path):
    path = tmp_path / "junit.xml"
    path.write_text(
        '<testsuites><testsuite name="pytest" tests="2" failures="1" errors="0">'
        '<testcase classname="tests.t" name="ok"/>'
        '<testcase classname="tests.t" name="bad"><failure>boom</failure></testcase>'
        "</testsuite></testsuites>"
    )
    report = parse_junit(path)
    assert report.passed_ids == {"tests.t::ok"}
    assert report.failed_ids == {"tests.t::bad"}
    assert report.green is False


def test_coverage_is_a_percentage(tmp_path: Path):
    path = tmp_path / "coverage.xml"
    path.write_text('<coverage line-rate="0.8042" lines-valid="189" lines-covered="152"/>')
    cov = parse_coverage(path)
    assert cov.line_rate == 80.42
    assert cov.lines_covered == 152


def test_a_repo_with_no_taskfile_is_rejected(tmp_path: Path):
    with pytest.raises(ContractError):
        Contract(tmp_path).validate()


def test_a_repo_missing_tasks_is_rejected(tmp_path: Path):
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  test:\n    cmds:\n      - echo hi\n"
    )
    contract = Contract(tmp_path)
    assert set(contract.missing_tasks()) == {"setup", "e2e", "lint", "format-check"}
    with pytest.raises(ContractError):
        contract.validate()


def test_defaults_apply_when_there_is_no_loop_yml(tmp_path: Path):
    contract = Contract(tmp_path)
    assert contract.role("judge")["write_allow"] == []
    assert contract.role("nonsense")["write_deny"] == ["**"]
    assert contract.budget["iterations"] == 3


@has_crm
def test_the_crm_satisfies_the_contract():
    contract = Contract(CRM)
    contract.validate()
    assert contract.rubric["coverage_floor"] == 78
    assert contract.role("code_implementer")["write_deny"] == [
        "tests/**",
        ".loop.yml",
        "Taskfile.yml",
    ]


@has_crm
def test_known_good_is_green_and_main_is_not():
    def on(branch: str):
        subprocess.run(["git", "checkout", "-q", branch], cwd=CRM, check=True)
        contract = Contract(CRM)
        result = contract.run("test")
        return result

    try:
        good = on("known-good")
        assert good.junit.green, "known-good must be green"
        assert good.coverage.line_rate >= 78, good.coverage.line_rate

        start = on("main")
        assert start.junit.green, "the starter's own tests still pass"
        assert start.coverage.line_rate < 78, "the starter must sit below the floor"
        assert not any("due_date" in i for i in start.junit.passed_ids)
    finally:
        subprocess.run(["git", "checkout", "-q", "main"], cwd=CRM, check=False)


# --- the genericity proof -------------------------------------------------

NODE_TARGET = REPO_ROOT / "loops" / "tests" / "fixtures" / "node-target"
has_node = pytest.mark.skipif(
    shutil.which("node") is None or not NODE_TARGET.is_dir(),
    reason="node is not installed",
)


@has_node
def test_the_engine_drives_a_javascript_repo():
    """The engine must run a repo written in another language, unchanged.

    This is the whole claim. If it fails, the engine is not generic.
    """
    contract = Contract(NODE_TARGET)
    contract.validate()

    result = contract.run("test")
    assert result.junit.green, result.output
    assert result.junit.tests == 3
    assert result.junit.passed_ids == {
        "test::add sums two numbers",
        "test::div divides",
        "test::div rejects zero",
    }
    assert result.coverage.line_rate == 100.0


@has_node
def test_a_failing_javascript_test_is_reported_as_failing():
    """A red suite in another language must read as red, not as missing."""
    broken = NODE_TARGET / "test" / "broken.test.js"
    broken.write_text(
        'import { test } from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'test("this one fails", () => assert.equal(1, 2));\n'
    )
    try:
        result = Contract(NODE_TARGET).run("test")
        assert not result.junit.green
        assert any("this one fails" in i for i in result.junit.failed_ids), result.junit.failed_ids
    finally:
        broken.unlink(missing_ok=True)
