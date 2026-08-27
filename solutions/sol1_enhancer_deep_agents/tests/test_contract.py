"""What `.loop.yml` says, and what the contract does when it says nothing."""

from __future__ import annotations

import pytest
from contract import DEFAULTS, Contract, ContractError


def test_missing_repo_raises(tmp_path):
    with pytest.raises(ContractError, match="does not exist"):
        Contract(tmp_path / "gone")


def test_loop_yml_overrides_the_defaults(contract):
    assert contract.rubric["coverage_floor"] == 78
    assert contract.role("code_implementer")["write_allow"] == ["app/**"]


def test_untouched_defaults_survive_the_merge(contract):
    assert contract.rubric["ui_paths"] == DEFAULTS["rubric"]["ui_paths"]
    assert contract.role("planner")["write_allow"] == ["steps.jsonl"]


def test_a_repo_without_loop_yml_gets_the_defaults(tmp_path):
    (tmp_path / "Taskfile.yml").write_text("version: '3'\n", encoding="utf-8")
    contract = Contract(tmp_path)
    assert contract.rubric == DEFAULTS["rubric"]
    assert contract.budget == DEFAULTS["budget"]
    assert contract.tickets == DEFAULTS["tickets"]


def test_an_unknown_role_fails_closed(contract):
    assert contract.role("nobody") == {"write_allow": [], "write_deny": ["**"]}


def test_the_judge_is_declared_with_no_write_path(contract):
    assert contract.role("judge")["write_allow"] == []


def test_missing_tasks_is_empty_for_a_full_taskfile(contract):
    assert contract.missing_tasks() == []
    assert contract.validate() is None


def test_missing_tasks_names_what_the_taskfile_omits(tmp_path):
    (tmp_path / "Taskfile.yml").write_text(
        "version: '3'\ntasks:\n  test:\n    cmds: [echo test]\n", encoding="utf-8"
    )
    missing = Contract(tmp_path).missing_tasks()
    assert "test" not in missing
    assert "e2e" in missing
    assert "lint" in missing


def test_validate_raises_without_a_taskfile(tmp_path):
    with pytest.raises(ContractError, match="Not a valid target repo"):
        Contract(tmp_path).validate()
