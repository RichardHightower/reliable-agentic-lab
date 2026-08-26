"""Checks for the research assistant and its deterministic brief checks."""

from __future__ import annotations

from pathlib import Path

from loops import brief, gates, research
from loops.researcher import FIXTURE, run, write_brief


def test_em_dashes_are_replaced_not_argued_about():
    out = brief.strip_em_dashes("The loop stops — always — when the budget is spent.")
    assert "—" not in out


def test_a_comma_heavy_line_takes_a_colon():
    out = brief.strip_em_dashes("First, second, and third — that is the rule.")
    assert ": " in out
    assert "—" not in out


def test_a_light_line_takes_a_semicolon():
    out = brief.strip_em_dashes("It stops — always.")
    assert "; " in out


def test_a_code_span_keeps_its_dash():
    out = brief.strip_em_dashes("Run `a — b` and then stop — now.")
    assert "`a — b`" in out
    assert out.count("—") == 1


def test_a_citation_pointing_at_nothing_is_caught():
    assert brief.ungrounded_citations("A claim [3].", ["one", "two"]) == ["[3]"]


def test_a_paragraph_with_no_citation_is_caught():
    loose = brief.uncited_claims("# Title\n\nThis is a confident claim nobody can trace.\n")
    assert loose


def test_a_numbered_source_list_is_not_a_claim():
    assert brief.uncited_claims("## Sources\n\n1. https://example.test\n") == []


def test_the_brief_check_fails_when_nothing_was_retrieved():
    score = brief.check("# Title\n\nA claim [1].\n", [])
    assert score.passed is False
    assert "has_sources" in score.signature()


def test_write_brief_numbers_sources_and_cites_them():
    findings = [
        research.Finding("q1", "answer one", ["https://a.test"]),
        research.Finding("q2", "answer two", ["https://b.test"]),
    ]
    body, sources = write_brief("the question", findings)
    assert sources == ["https://a.test", "https://b.test"]
    assert "[1]" in body
    assert "[2]" in body
    assert brief.check(body, sources).passed


def test_the_loop_produces_a_passing_brief_from_the_fixture(tmp_path: Path):
    trace = run(
        question="sqlalchemy nullable datetime column mapped optional",
        backend=research.FixtureBackend(FIXTURE),
        out_dir=tmp_path,
        write_trace=False,
    )
    assert trace["gate"] == gates.PASS, trace["report"]
    assert Path(trace["brief"]).exists()
    assert trace["sources"]


def test_the_loop_stops_when_no_source_can_be_found(tmp_path: Path):
    """No evidence is not a pass. The brief must not go out uncited."""
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    trace = run(
        question="anything",
        backend=research.FixtureBackend(empty),
        out_dir=tmp_path,
        write_trace=False,
    )
    assert trace["gate"] == gates.ESCALATE
    assert "has_sources" in trace["report"]


def test_the_research_budget_is_reported(tmp_path: Path):
    trace = run(
        question="fastapi test rendered template contains value",
        backend=research.FixtureBackend(FIXTURE),
        out_dir=tmp_path,
        write_trace=False,
    )
    assert "calls" in trace["budget"]
