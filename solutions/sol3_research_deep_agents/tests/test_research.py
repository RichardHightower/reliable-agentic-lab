from __future__ import annotations

from pathlib import Path

import brief
import loop
import research
import researcher
import roles

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "research.json"


def _by_name(subagents):
    return {a["name"]: a for a in subagents}


def test_plan_questions_are_checkable():
    qs = loop.plan_questions("sqlalchemy nullable datetime column")
    assert qs[0] == "sqlalchemy nullable datetime column"
    assert any("verify" in q for q in qs)


def test_fixture_backend_cites():
    backend = research.FixtureBackend(FIXTURE)
    finding = backend.search("sqlalchemy nullable datetime column")
    assert finding.citations
    assert "nullable" in finding.answer.lower() or "DateTime" in finding.answer


def test_check_brief_is_arithmetic():
    body = "# Q\n\nUse DateTime nullable. [1]\n\n## Sources\n\n1. https://example.com\n"
    score = loop.check_brief(body, ["https://example.com"])
    assert score.passed


def test_ungrounded_citation_fails():
    score = loop.check_brief("Claim [9]\n", ["https://example.com"])
    assert not score.passed


def test_budget_hard_cap():
    b = research.Budget(max_calls=1, max_usd=1)
    b.charge(0)
    try:
        b.charge(0)
    except research.BudgetExceeded:
        return
    raise AssertionError("expected BudgetExceeded")


def test_researcher_has_search_not_write(fake_langchain, tmp_path):
    backend = research.FixtureBackend(FIXTURE)
    agents = _by_name(roles.subagents_for(None, backend=backend))
    researcher_agent = agents["researcher"]
    names = [t.__name__ for t in researcher_agent["tools"]]
    assert "search" in names
    assert "write" not in names
    judge = agents["judge"]
    assert [t.__name__ for t in judge["tools"]] == ["read_file"]


def test_run_fixture_writes_brief(tmp_path):
    trace = researcher.run(
        question="sqlalchemy nullable datetime column",
        backend=research.FixtureBackend(FIXTURE),
        out_dir=tmp_path,
        budget=1,
    )
    assert (tmp_path / "brief.md").exists()
    assert trace["gate"] in {"pass", "retry", "escalate"}
    assert "sources" in trace


def test_no_loops_import():
    import subprocess

    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []
