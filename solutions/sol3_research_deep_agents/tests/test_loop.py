"""The entry point. `--table-only` must work with nothing installed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import loop
import pytest
import roleplan

ROOT = Path(__file__).resolve().parents[1]


def test_table_only_prints_the_research_cast(capsys):
    assert loop.main(["--table-only"]) == 0
    out = capsys.readouterr().out
    assert "orchestrator      no" in out
    assert "judge             no" in out


def test_table_only_prints_the_paper_cast(capsys):
    assert loop.main(["--table-only", "--paper"]) == 0
    out = capsys.readouterr().out
    assert "reviewer          no" in out
    assert "diagrammer        yes" in out


def test_table_only_imports_no_runtime():
    """The load-bearing convention in this folder. A reader must be able to see
    what a role may write before installing an SDK."""
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r});"
        "import loop; loop.main(['--table-only', '--paper']);"
        "assert 'deepagents' not in sys.modules;"
        "assert 'langchain' not in sys.modules;"
        "assert 'paper' not in sys.modules;"
        "assert 'roles' not in sys.modules;"
        "print('clean')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "clean" in out.stdout


def test_the_lab_answer_still_runs(capsys):
    """Growing this folder must not move Saturday's artifact."""
    assert (
        loop.main(["--question", "sqlalchemy nullable datetime column", "--backend", "fixture"])
        == 0
    )


def test_check_brief_is_still_arithmetic():
    score = loop.check_brief(
        "A fact. [1]\n\n## Sources\n\n1. https://a.example\n", ["https://a.example"]
    )
    assert score.passed
    assert not loop.check_brief("A claim [9]\n", ["https://a.example"]).passed


def test_plan_questions_still_widens_the_question():
    questions = loop.plan_questions("sqlalchemy nullable datetime column")
    assert questions[0] == "sqlalchemy nullable datetime column"
    assert len(questions) > 1


def test_paper_needs_a_topic():
    with pytest.raises(SystemExit):
        loop.main(["--paper"])


def test_paper_debug_flag_reaches_the_paper_builder(monkeypatch):
    seen = {}

    class Run:
        def run(self):
            return 0

    monkeypatch.setattr(loop, "second_brain", lambda: None)
    monkeypatch.setattr("paper.build", lambda topic, **kwargs: (seen.update(topic=topic, **kwargs), Run())[1])

    assert loop.main(["--paper", "--topic", "loop engineering", "--debug"]) == 0
    assert seen["topic"] == "loop engineering"
    assert seen["debug"] is True


def test_the_second_brain_is_never_required(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN", "/definitely/not/here")
    assert loop.second_brain() is None


def test_the_second_brain_is_used_when_it_is_there(monkeypatch, tmp_path):
    monkeypatch.setenv("SECOND_BRAIN", str(tmp_path))
    assert loop.second_brain() == tmp_path


def test_the_entry_point_names_its_own_loop():
    """This copy's `DEFAULT_LOOP` already matches the loop it runs. Four other
    ports inherited `'implementer'` from the shared `roleplan.py` the repo
    deleted. The Deep Agents enhancer and fixer now agree with their own loop.
    Two Agent SDK copies still carry the old value.

    This test pins the explicit name here, so the two never drift apart.
    """
    assert loop.LOOP == "research"
    assert set(loop.cast(None)) == set(roleplan.LOOPS["research"])
