"""The entry point, and the separation that lets it run with no SDK."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import loop
import pytest

FOLDER = Path(__file__).resolve().parents[1]


def test_the_table_prints_as_a_subprocess_with_no_sdk():
    """A fresh interpreter, so an SDK imported by another test cannot help."""
    proc = subprocess.run(
        [sys.executable, "loop.py", "--table-only"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "diagrammer" in proc.stdout
    assert "judge             no" in proc.stdout


def test_importing_loop_pulls_in_neither_the_adapter_nor_the_sdk():
    """The lazy imports are load-bearing, not tidiness."""
    proc = subprocess.run(
        [sys.executable, "-c", "import loop, sys; print(sorted(sys.modules))"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "'adapter'" not in proc.stdout
    assert "'claude_agent_sdk'" not in proc.stdout
    assert "'paper'" not in proc.stdout


def test_the_cast_is_read_from_the_table_not_restated():
    import roleplan  # noqa: PLC0415

    assert loop.cast(None) == roleplan.plan(None, "research")


def test_a_topic_is_required_unless_you_only_want_the_table(capsys):
    assert loop.main(["--table-only"]) == 0
    with pytest.raises(SystemExit):
        loop.main([])


def test_the_fixture_backend_is_chosen_when_nothing_else_is_there(monkeypatch, work):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    chosen = loop.pick_turns("fixture", work, None, None)
    assert type(chosen).__name__ == "OfflineTurns"
    assert chosen.backend.name == "fixture"


def test_a_brief_is_forwarded_only_when_the_run_has_one(work, turns):
    import paper  # noqa: PLC0415

    class Briefed(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.received_brief = brief
            return super().outline(topic, prior_art, budget, note, brief)

    run = paper.Run(
        topic="topic",
        work_dir=work,
        turns=Briefed(),
        state=paper.State.load_or_new(work, "topic"),
        brain=None,
        brief="require a figure",
        log=lambda *_: None,
    )
    paper.prior_art(run)
    paper.plan(run)

    assert run.turns.received_brief == "require a figure"


def test_asking_for_the_agent_with_no_sdk_installed_raises(monkeypatch, work):
    """`auto` degrades. `agent` is a request, and a silent downgrade hides it."""
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    monkeypatch.delitem(sys.modules, "claude_agent_sdk")
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def blocked(name, *args, **kwargs):
        if name == "claude_agent_sdk":
            raise ImportError("no sdk")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(ImportError):
        loop.pick_turns("agent", work, None, None)
    assert type(loop.pick_turns("auto", work, None, None)).__name__ == "OfflineTurns"
