"""The entry point. `--table-only` has to run with no SDK and no clone."""

from __future__ import annotations

import dataclasses

import loop
import pytest
import roleplan
from contract import ContractError


def test_the_loop_names_itself():
    assert loop.LOOP == "enhancer"


def test_cast_restates_nothing(contract):
    got = {name: dataclasses.asdict(role) for name, role in loop.cast(contract).items()}
    want = {
        name: dataclasses.asdict(role) for name, role in roleplan.plan(contract, "enhancer").items()
    }
    assert got == want


def test_table_only_prints_the_cast_and_stops(target_repo, capsys):
    assert loop.main(["--table-only", "--repo", str(target_repo)]) == 0

    out = capsys.readouterr().out
    rows = {line.split()[0]: line.split()[1] for line in out.strip().splitlines()[1:]}
    assert rows == {"orchestrator": "no", "doer": "yes", "judge": "no"}


def test_table_only_falls_back_when_the_target_repo_is_missing(tmp_path, capsys):
    assert loop.main(["--table-only", "--repo", str(tmp_path / "gone")]) == 0

    captured = capsys.readouterr()
    assert "no target repo" in captured.err
    assert "tickets/**" in captured.out


def test_a_full_run_still_needs_the_target_repo(tmp_path):
    with pytest.raises(ContractError):
        loop.main(["--repo", str(tmp_path / "gone")])


def test_build_needs_the_sdk(contract):
    """`build()` is the line that pulls in LangChain. It is not on the table path."""
    with pytest.raises(ModuleNotFoundError):
        loop.build(contract)


def test_target_repo_env_var_sets_the_default(target_repo, monkeypatch, capsys):
    """`.env` carries TARGET_REPO. Task loads it, argparse reads it."""
    monkeypatch.setenv("TARGET_REPO", str(target_repo))

    assert loop.main(["--table-only"]) == 0

    assert "no target repo" not in capsys.readouterr().err


def test_an_explicit_repo_beats_the_env_var(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TARGET_REPO", str(tmp_path))

    assert loop.main(["--table-only", "--repo", str(tmp_path / "gone")]) == 0

    assert "no target repo" in capsys.readouterr().err
