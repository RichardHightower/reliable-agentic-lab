"""The entry point. `--table-only` has to run with no SDK and no clone."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import loop
import pytest
import roleplan
from contract import ContractError
from enhancer import EnhancerError, Outcome

FOLDER = Path(__file__).resolve().parents[1]


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


# -- the separation, checked in a clean interpreter -------------------------


def test_importing_loop_does_not_pull_in_the_adapter():
    """`backend()` imports `adapter` lazily, and that is what keeps
    `--table-only` runnable with no `deepagents` installed.

    A fresh interpreter is the only honest place to check this. The rest of this
    suite has already imported `adapter` by the time any test runs.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, loop; assert 'adapter' not in sys.modules; print('ok')",
        ],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "ok" in done.stdout


def test_the_table_prints_from_the_command_line_with_nothing_installed(target_repo):
    """The one command SPEC.md tells a reader to run first."""
    done = subprocess.run(
        [sys.executable, "loop.py", "--table-only", "--repo", str(target_repo)],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "judge" in done.stdout


# -- config.json and the poll entry point ----------------------------------


def test_config_reads_the_file_next_to_this_module(tmp_path):
    (tmp_path / "config.json").write_text('{"fork_owner": "me", "repo_name": "crm"}')
    assert loop.config(tmp_path)["fork_owner"] == "me"


def test_a_missing_config_tells_you_exactly_what_to_copy(tmp_path):
    """This runs headlessly. It cannot stop and wait for a username."""
    with pytest.raises(SystemExit, match=r"config\.json\.example"):
        loop.config(tmp_path)


@pytest.fixture
def polling(monkeypatch):
    """`--once` with the config, the runtime, and GitHub all stubbed out."""
    monkeypatch.setattr(
        loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm", "poll_interval": "5m"}
    )
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    return monkeypatch


def test_once_polls_and_prints_one_line_per_ticket(target_repo, polling, capsys):
    """The report is the only user-facing narration the loop produces."""
    polling.setattr(
        "enhancer.Enhancer.poll", lambda self, t=None, **kw: [Outcome("T001", "passed", "green")]
    )
    assert loop.main(["--once", "--repo", str(target_repo)]) == 0

    out = capsys.readouterr().out
    assert "T001" in out
    assert "passed" in out


def test_a_waiting_ticket_names_the_command_to_poll_again(target_repo, polling, capsys):
    polling.setattr(
        "enhancer.Enhancer.poll", lambda self, t=None, **kw: [Outcome("T001", "waiting", "round 1")]
    )
    loop.main(["--once", "--repo", str(target_repo)])

    assert "poll-forever" in capsys.readouterr().out


def test_no_open_tickets_says_so_rather_than_printing_nothing(target_repo, polling, capsys):
    polling.setattr("enhancer.Enhancer.poll", lambda self, t=None, **kw: [])
    loop.main(["--once", "--repo", str(target_repo)])

    assert "no open enhancer tickets" in capsys.readouterr().out


def test_naming_a_ticket_implies_once_and_carries_the_simulated_comment(target_repo, polling):
    seen = {}
    polling.setattr(
        "enhancer.Enhancer.poll",
        lambda self, t=None, **kw: (seen.update(ticket=t, kw=kw), [Outcome("T001", "passed")])[1],
    )
    loop.main(["--ticket", "T001", "--simulate-comment", "hi", "--repo", str(target_repo)])

    assert seen["ticket"] == "T001"
    assert seen["kw"]["simulate_comment"] == "hi"


def test_an_enhancer_error_reports_and_exits_nonzero(target_repo, polling, capsys):
    """A loop that dies has to say why, not just exit."""

    def boom(self, t=None, **kw):
        raise EnhancerError("no tickets/ directory")

    polling.setattr("enhancer.Enhancer.poll", boom)
    assert loop.main(["--once", "--repo", str(target_repo)]) == 1
    assert "enhancer stopped: no tickets/ directory" in capsys.readouterr().out


def test_a_missing_deepagents_install_has_a_setup_command(target_repo, monkeypatch, capsys):
    """A live run should not expose an import traceback to an attendee."""

    monkeypatch.setattr(
        loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm"}
    )

    def missing_runtime(_contract):
        raise ModuleNotFoundError("No module named 'deepagents'", name="deepagents")

    monkeypatch.setattr(loop, "backend", missing_runtime)

    assert loop.main(["--once", "--repo", str(target_repo)]) == 1

    out = capsys.readouterr().out
    assert "Deep Agents is not installed" in out
    assert "pip install -r ../../requirements-takehome.txt" in out


def test_the_entry_point_names_its_own_loop():
    """A bare `roleplan.plan(contract)` must build this folder's own cast.

    This copy inherited `DEFAULT_LOOP = "implementer"` from the shared
    `roleplan.py` the repo deleted, and never changed it. Every caller named its
    loop, so nothing misbehaved, and an earlier version of this test asserted
    the mismatch was harmless. That made the footgun permanent: the one call
    site that forgot would build the wrong cast with the wrong write scopes.

    The default now agrees with the loop, which is a stronger claim than the one
    this test used to make.
    """
    assert roleplan.DEFAULT_LOOP == loop.LOOP
    assert set(loop.cast(None)) == set(roleplan.LOOPS[loop.LOOP])
    assert set(roleplan.plan(None)) == set(roleplan.LOOPS[loop.LOOP])
