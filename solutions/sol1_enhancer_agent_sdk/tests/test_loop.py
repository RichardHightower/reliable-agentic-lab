"""The entry point, and the separation that lets it run with no SDK installed.

`python loop.py --table-only` must print the role table and exit 0 on a machine
that has never installed `claude-agent-sdk`. Losing that means the first thing a
reader does with this folder is read a traceback.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import loop
import pytest
import roleplan
from adapter import AgentSdkBackend
from contract import ContractError
from enhancer import EnhancerError, Outcome

FOLDER = Path(__file__).resolve().parents[1]


def test_this_port_names_the_loop_it_runs():
    assert loop.LOOP == "enhancer"


def test_cast_returns_the_shared_table_rather_than_a_local_restatement(contract):
    """A port that writes its own scopes drifts from the loop it claims to be."""
    got = {name: dataclasses.asdict(plan) for name, plan in loop.cast(contract).items()}
    want = {
        name: dataclasses.asdict(plan) for name, plan in roleplan.plan(contract, "enhancer").items()
    }
    assert got == want


def test_cast_returns_the_three_enhancer_roles(contract):
    assert list(loop.cast(contract)) == ["orchestrator", "doer", "judge"]


def test_the_judge_in_the_cast_holds_no_write_tool(contract):
    assert loop.cast(contract)["judge"].can_write is False


def test_table_only_prints_the_table_and_exits_zero(repo, capsys):
    assert loop.main(["--table-only", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "role" in out
    for name in ("orchestrator", "doer", "judge"):
        assert name in out


def test_table_only_prints_no_in_the_judges_writes_column(repo, capsys):
    """If it prints `yes`, stop. Nothing downstream is worth building on that."""
    loop.main(["--table-only", "--repo", str(repo)])
    judge = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("judge"))
    assert judge.split()[1] == "no"


def test_the_table_prints_before_the_target_repo_is_cloned(tmp_path, capsys):
    """`--table-only` is the first command SPEC.md tells a reader to run.

    Making it need `task setup` first means the first thing a reader sees is a
    traceback, and the scopes it prints do not depend on the clone anyway.
    """
    assert loop.main(["--table-only", "--repo", str(tmp_path / "nope")]) == 0
    out = capsys.readouterr().out
    assert "no target repo" in out
    assert "doer" in out


def test_the_table_shows_the_same_scopes_with_or_without_the_clone(repo, capsys):
    loop.main(["--table-only", "--repo", str(repo)])
    with_repo = capsys.readouterr().out.splitlines()[1:]
    loop.main(["--table-only", "--repo", str(repo / "nope")])
    without = capsys.readouterr().out.splitlines()[2:]
    assert with_repo == without


def test_the_default_run_prints_the_table_and_then_the_configuration(repo, fake_sdk, capsys):
    """Step 5 of SPEC.md. Print the configuration and read it."""
    assert loop.main(["--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "judge" in out
    assert "FakeClaudeAgentOptions" in out, "the built options have to reach stdout"


def test_a_missing_repo_still_stops_anything_past_the_table(tmp_path):
    """The table is the only thing that runs without a target repo."""
    with pytest.raises(ContractError):
        loop.main(["--repo", str(tmp_path / "nope")])


@pytest.mark.skipif(
    __import__("conftest", fromlist=["sdk_installed"]).sdk_installed(),
    reason="SDK is installed; missing-package path is for a clean env",
)
def test_build_needs_the_sdk(contract):
    with pytest.raises(ImportError):
        loop.build(contract)


def test_build_returns_this_runtimes_options_for_the_enhancer_cast(contract, fake_sdk):
    options = loop.build(contract)
    assert set(options.agents) == {"enhancer-doer", "enhancer-judge"}
    assert options.cwd == str(contract.repo)


def test_backend_wraps_the_built_options(contract, fake_sdk):
    made = loop.backend(contract)
    assert isinstance(made, AgentSdkBackend)
    assert made.options.cwd == str(contract.repo)


@pytest.mark.skipif(
    __import__("conftest", fromlist=["sdk_installed"]).sdk_installed(),
    reason="SDK is installed; missing-package path is for a clean env",
)
def test_backend_needs_the_sdk_only_through_build(contract):
    with pytest.raises(ImportError):
        loop.backend(contract)


# -- the separation, checked in a clean interpreter -------------------------


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code], cwd=FOLDER, text=True, capture_output=True, check=False
    )


def test_importing_loop_does_not_pull_in_the_adapter():
    """`backend()` imports `adapter` lazily, which keeps --table-only free of it.

    A fresh interpreter is the only honest place to check this. The rest of this
    suite has already imported `adapter` by the time any test runs.
    """
    done = _run("import sys, loop; assert 'adapter' not in sys.modules; print('ok')")
    assert done.returncode == 0, done.stderr
    assert "ok" in done.stdout


def test_importing_loop_does_not_pull_in_the_sdk():
    done = _run("import sys, loop; assert 'claude_agent_sdk' not in sys.modules; print('ok')")
    assert done.returncode == 0, done.stderr


def test_the_table_prints_from_the_command_line_with_no_sdk_installed(repo):
    """The one command SPEC.md tells a reader to run first."""
    done = subprocess.run(
        [sys.executable, "loop.py", "--table-only", "--repo", str(repo)],
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


def test_once_polls_and_prints_one_line_per_ticket(repo, monkeypatch, capsys):
    """The report is the only user-facing narration the loop produces."""
    monkeypatch.setattr(loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm"})
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    monkeypatch.setattr(
        "enhancer.Enhancer.poll", lambda self, t=None, **kw: [Outcome("T001", "passed", "green")]
    )
    assert loop.main(["--once", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "T001" in out
    assert "passed" in out


def test_a_waiting_ticket_names_the_command_to_poll_again(repo, monkeypatch, capsys):
    monkeypatch.setattr(
        loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm", "poll_interval": "5m"}
    )
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    monkeypatch.setattr(
        "enhancer.Enhancer.poll", lambda self, t=None, **kw: [Outcome("T001", "waiting", "round 1")]
    )
    loop.main(["--once", "--repo", str(repo)])
    assert "poll-forever" in capsys.readouterr().out


def test_no_open_tickets_says_so_rather_than_printing_nothing(repo, monkeypatch, capsys):
    monkeypatch.setattr(loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm"})
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    monkeypatch.setattr("enhancer.Enhancer.poll", lambda self, t=None, **kw: [])
    loop.main(["--once", "--repo", str(repo)])
    assert "no open enhancer tickets" in capsys.readouterr().out


def test_naming_a_ticket_implies_once(repo, monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm"})
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    monkeypatch.setattr(
        "enhancer.Enhancer.poll",
        lambda self, t=None, **kw: (seen.update(ticket=t, kw=kw), [Outcome("T001", "passed")])[1],
    )
    loop.main(["--ticket", "T001", "--simulate-comment", "hi", "--repo", str(repo)])
    assert seen["ticket"] == "T001"
    assert seen["kw"]["simulate_comment"] == "hi"


def test_an_enhancer_error_reports_and_exits_nonzero(repo, monkeypatch, capsys):
    """A loop that dies has to say why, not just exit."""

    def boom(self, t=None, **kw):
        raise EnhancerError("no tickets/ directory")

    monkeypatch.setattr(loop, "config", lambda *a: {"fork_owner": "me", "repo_name": "crm"})
    monkeypatch.setattr(loop, "backend", lambda contract: object())
    monkeypatch.setattr("enhancer.Enhancer.poll", boom)
    assert loop.main(["--once", "--repo", str(repo)]) == 1
    assert "enhancer stopped: no tickets/ directory" in capsys.readouterr().out
