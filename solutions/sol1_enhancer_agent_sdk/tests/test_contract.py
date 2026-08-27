"""The repo contract, and the two report formats every language emits.

A missing report is not a pass. A stale report is not a pass. Those two facts
are the silent-skip bug this workshop is about, so they get direct checks rather
than being inferred from a green run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import contract as contract_mod
import pytest
from contract import Contract, ContractError, parse_coverage, parse_junit

# -- construction and validation -------------------------------------------


def test_a_missing_target_repo_is_rejected(tmp_path):
    with pytest.raises(ContractError, match="target repo does not exist"):
        Contract(tmp_path / "nope")


def test_a_file_is_not_a_target_repo(tmp_path):
    (tmp_path / "a-file").write_text("", encoding="utf-8")
    with pytest.raises(ContractError, match="target repo does not exist"):
        Contract(tmp_path / "a-file")


def test_the_repo_path_is_resolved(repo):
    assert Contract(repo).repo == Path(repo).resolve()


def test_a_valid_target_passes_validation(contract):
    assert contract.validate() is None
    assert contract.missing_tasks() == []


def test_a_missing_taskfile_reports_every_required_task(tmp_path):
    assert Contract(tmp_path).missing_tasks() == list(contract_mod.REQUIRED_TASKS)


def test_a_missing_taskfile_is_rejected_by_name(tmp_path):
    with pytest.raises(ContractError, match="Not a valid target repo"):
        Contract(tmp_path).validate()


def test_validate_names_the_tasks_the_target_is_missing(repo):
    text = (repo / "Taskfile.yml").read_text(encoding="utf-8")
    (repo / "Taskfile.yml").write_text(text.replace("  e2e:\n    cmds: [echo e2e]\n", ""))
    with pytest.raises(ContractError, match="missing required tasks: e2e"):
        Contract(repo).validate()


# -- config ----------------------------------------------------------------


def test_loop_yml_merges_over_the_defaults_instead_of_replacing_them(contract):
    """`.loop.yml` sets `iterations` and `usd`, and says nothing about tickets.

    A shallow overwrite would drop every default the file did not mention, which
    is how a target repo silently loses its ticket source.
    """
    assert contract.budget == {"iterations": 5, "usd": 4.0}
    assert contract.tickets == contract_mod.DEFAULTS["tickets"]


def test_a_nested_key_merges_rather_than_replacing_its_siblings(contract):
    """`.loop.yml` sets `coverage_floor` and `require_red`, never `ui_paths`."""
    assert contract.rubric["coverage_floor"] == 75.0
    assert contract.rubric["ui_paths"] == []


def test_a_declared_role_wins_over_the_default(contract):
    assert contract.role("code_implementer")["write_deny"] == ["tests/**"]


def test_an_unknown_role_gets_no_write_path(contract):
    """Fail closed. A role the contract has never heard of writes nothing."""
    assert contract.role("nobody") == {"write_allow": [], "write_deny": ["**"]}


def test_a_repo_with_no_loop_yml_keeps_every_default(tmp_path):
    (tmp_path / "Taskfile.yml").write_text("version: '3'\n", encoding="utf-8")
    assert Contract(tmp_path).config == contract_mod.DEFAULTS


def test_the_mini_yaml_fallback_reads_the_same_loop_yml(repo, monkeypatch):
    """PyYAML is optional. A target repo must stay readable without it.

    Setting the module to None makes `import yaml` raise ImportError, which is
    the branch `_load_yaml` catches.
    """
    monkeypatch.setitem(sys.modules, "yaml", None)
    fallback = Contract(repo)
    monkeypatch.undo()
    assert fallback.config == Contract(repo).config


def test_the_mini_yaml_parser_reads_inline_lists_and_scalars():
    parsed = contract_mod._mini_yaml(
        "roles:\n"
        "  doer:\n"
        "    write_allow: [tickets/**, 'docs/*.md']\n"
        "    write_deny: []\n"
        "budget:\n"
        "  iterations: 3\n"
        "  usd: 2.5\n"
        "  strict: true\n"
        "  note: null\n"
        "# a comment line\n"
    )
    assert parsed["roles"]["doer"]["write_allow"] == ["tickets/**", "docs/*.md"]
    assert parsed["roles"]["doer"]["write_deny"] == []
    assert parsed["budget"] == {"iterations": 3, "usd": 2.5, "strict": True, "note": None}


def test_the_mini_yaml_parser_skips_a_line_that_is_not_a_key_or_a_bullet():
    """A stray word is not a mapping. Guessing at one invents config."""
    assert contract_mod._mini_yaml("budget:\n  iterations: 3\nstray\n") == {
        "budget": {"iterations": 3}
    }


def test_the_mini_yaml_parser_folds_a_block_list():
    parsed = contract_mod._mini_yaml("paths:\n  - app\n  - src\n")
    assert parsed["paths"] == ["app", "src"]


def test_the_mini_yaml_parser_reads_a_negative_number_and_a_false():
    parsed = contract_mod._mini_yaml("floor: -12\nrate: -0.5\nred: no\n")
    assert parsed == {"floor": -12, "rate": -0.5, "red": False}


# -- junit -----------------------------------------------------------------


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_a_missing_junit_file_is_not_a_pass(tmp_path):
    report = parse_junit(tmp_path / "junit.xml")
    assert report.exists is False
    assert report.green is False


def test_a_pytest_shaped_junit_file_is_read_from_its_test_cases(tmp_path):
    path = _write(
        tmp_path,
        "junit.xml",
        '<testsuites><testsuite name="pytest" tests="3" failures="1">'
        '<testcase classname="tests.test_a" name="test_ok"/>'
        '<testcase classname="tests.test_a" name="test_bad"><failure>boom</failure></testcase>'
        '<testcase classname="tests.test_a" name="test_skip"><skipped/></testcase>'
        "</testsuite></testsuites>",
    )
    report = parse_junit(path)
    assert report.tests == 3
    assert report.failures == 1
    assert report.skipped == 1
    assert report.failed_ids == {"tests.test_a::test_bad"}
    assert report.passed_ids == {"tests.test_a::test_ok"}
    assert report.green is False


def test_a_node_shaped_junit_file_with_no_counts_is_still_read(tmp_path):
    """Node's runner puts <testcase> straight under <testsuites> with no counts.

    Reading the suite attributes as the source of truth would report zero tests
    here, and zero tests reads as "nothing ran" rather than "two passed".
    """
    path = _write(
        tmp_path,
        "junit.xml",
        '<testsuites><testcase name="adds"/><testcase name="subtracts"/></testsuites>',
    )
    report = parse_junit(path)
    assert report.tests == 2
    assert report.passed_ids == {"adds", "subtracts"}
    assert report.green is True


def test_a_counts_only_suite_is_believed_when_it_emits_no_cases(tmp_path):
    path = _write(
        tmp_path,
        "junit.xml",
        '<testsuites><testsuite tests="7" failures="2" errors="1" skipped="1"/></testsuites>',
    )
    report = parse_junit(path)
    assert (report.tests, report.failures, report.errors, report.skipped) == (7, 2, 1, 1)
    assert report.green is False


def test_an_error_counts_separately_from_a_failure(tmp_path):
    path = _write(
        tmp_path,
        "junit.xml",
        '<testsuites><testsuite><testcase name="broken"><error>raised</error></testcase>'
        "</testsuite></testsuites>",
    )
    report = parse_junit(path)
    assert report.errors == 1
    assert report.failures == 0
    assert report.green is False


def test_a_suite_that_ran_nothing_is_empty_and_not_green(tmp_path):
    path = _write(tmp_path, "junit.xml", "<testsuites></testsuites>")
    report = parse_junit(path)
    assert report.empty is True
    assert report.green is False


def test_a_green_suite_needs_a_file_a_test_and_no_failure(tmp_path):
    path = _write(
        tmp_path,
        "junit.xml",
        '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
    )
    assert parse_junit(path).green is True


# -- coverage --------------------------------------------------------------


def test_a_missing_coverage_file_reports_nothing(tmp_path):
    report = parse_coverage(tmp_path / "coverage.xml")
    assert report.exists is False
    assert report.line_rate == 0.0


def test_a_cobertura_file_reports_a_line_rate_as_a_percentage(tmp_path):
    path = _write(
        tmp_path,
        "coverage.xml",
        '<coverage line-rate="0.8342" lines-valid="200" lines-covered="167"/>',
    )
    report = parse_coverage(path)
    assert report.exists is True
    assert report.line_rate == 83.42
    assert (report.lines_valid, report.lines_covered) == (200, 167)


def test_a_cobertura_file_with_no_attributes_reads_as_zero(tmp_path):
    assert parse_coverage(_write(tmp_path, "coverage.xml", "<coverage/>")).line_rate == 0.0


def test_the_contract_reads_reports_from_the_reports_directory(repo, contract):
    _write(
        repo / "reports",
        "junit.xml",
        '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
    )
    _write(repo / "reports", "coverage.xml", '<coverage line-rate="0.5"/>')
    assert contract.reports_dir == repo.resolve() / "reports"
    assert contract.junit().green is True
    assert contract.coverage().line_rate == 50.0


# -- running ---------------------------------------------------------------


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_reads_the_reports_the_task_wrote(repo, contract, monkeypatch):
    def fake_run(argv, **kwargs):
        assert argv == ["task", "test"]
        _write(
            repo / "reports",
            "junit.xml",
            '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
        )
        _write(repo / "reports", "coverage.xml", '<coverage line-rate="0.91"/>')
        return _Proc(stdout="ran\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = contract.run("test")
    assert result.ok is True
    assert result.no_tests is False
    assert result.junit.green is True
    assert result.coverage.line_rate == 91.0
    assert result.output == "ran\n"


def test_run_reports_a_red_suite_as_data_rather_than_raising(repo, contract, monkeypatch):
    def fake_run(argv, **kwargs):
        _write(
            repo / "reports",
            "junit.xml",
            '<testsuites><testsuite><testcase name="bad"><failure/></testcase></testsuite></testsuites>',
        )
        return _Proc(returncode=1, stderr="failed\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = contract.run("test")
    assert result.ok is False
    assert result.junit.green is False


def test_a_report_that_did_not_move_is_not_believed(repo, contract, monkeypatch):
    """Saying "green" off a file from a previous run is the silent-skip bug.

    The task here writes nothing, so the stale junit.xml keeps its mtime and the
    contract must refuse to count it.
    """
    _write(
        repo / "reports",
        "junit.xml",
        '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
    )
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: _Proc())
    result = contract.run("test")
    assert result.junit.exists is False, "a stale report must not read as a passing one"
    assert result.junit.green is False


def test_an_empty_suite_reports_no_tests(repo, contract, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: _Proc(returncode=5))
    assert contract.run("test").no_tests is True


def test_the_e2e_task_reads_its_own_junit_file(repo, contract, monkeypatch):
    def fake_run(argv, **kwargs):
        assert argv == ["task", "e2e"]
        _write(
            repo / "reports",
            "junit-e2e.xml",
            '<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>',
        )
        return _Proc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = contract.run("e2e")
    assert result.junit.green is True
    assert result.coverage.exists is False, "only `task test` produces coverage"
