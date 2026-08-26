"""Checks for the research boundary and its budget."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loops.research import (
    Budget,
    BudgetExceeded,
    FixtureBackend,
    Researcher,
    WebSearchBackend,
    choose,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "research.json"


def test_the_fixture_backend_answers_a_recorded_question():
    finding = FixtureBackend(FIXTURE).search("sqlalchemy nullable datetime column mapped optional")
    assert "nullable=True" in finding.answer
    assert finding.citations


def test_an_unrecorded_question_falls_back_to_the_closest_match():
    finding = FixtureBackend(FIXTURE).search("how do I make a datetime column nullable")
    assert finding.answer, "it should return the nearest recorded answer, not nothing"


def test_a_missing_fixture_is_not_available(tmp_path: Path):
    assert FixtureBackend(tmp_path / "nope.json").available() is False


def test_the_money_budget_is_a_hard_cap():
    budget = Budget(max_usd=0.01, max_calls=99)
    budget.charge(0.006)
    with pytest.raises(BudgetExceeded, match="money"):
        budget.charge(0.006)


def test_the_call_budget_is_a_hard_cap():
    budget = Budget(max_usd=99.0, max_calls=2)
    budget.charge(0.0)
    budget.charge(0.0)
    with pytest.raises(BudgetExceeded, match="call budget"):
        budget.charge(0.0)


def test_the_soft_target_warns_without_stopping():
    budget = Budget(max_usd=1.0, soft_usd=0.10)
    budget.charge(0.20)
    assert budget.over_soft_target is True
    budget.charge(0.20)


def test_the_researcher_records_every_finding_and_spend():
    researcher = Researcher(
        backend=FixtureBackend(FIXTURE), budget=Budget(max_usd=1.0, max_calls=5)
    )
    researcher.ask("sqlalchemy nullable datetime column mapped optional")
    researcher.ask("fastapi test rendered template contains value")
    assert len(researcher.findings) == 2
    assert researcher.budget.calls == 2
    assert "backend: fixture" in researcher.report()


def test_the_researcher_stops_at_the_budget():
    researcher = Researcher(backend=FixtureBackend(FIXTURE), budget=Budget(max_calls=1))
    researcher.ask("fastapi test rendered template contains value")
    with pytest.raises(BudgetExceeded):
        researcher.ask("anything else at all")


def test_websearch_returns_an_empty_answer_until_the_agent_fills_the_inbox(tmp_path: Path):
    inbox = tmp_path / "websearch.json"
    backend = WebSearchBackend(inbox)
    assert backend.available() is True
    assert backend.search("what is a due date").answer == ""
    inbox.write_text(json.dumps({"what is a due date": {"answer": "a date", "citations": []}}))
    assert backend.search("what is a due date").answer == "a date"


def test_choose_falls_back_to_the_fixture_when_nothing_else_is_available(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert choose(fixture=FIXTURE).name == "fixture"


def test_choose_refuses_rather_than_silently_returning_nothing(monkeypatch, tmp_path: Path):
    """A research loop with no backend must refuse, not return empty evidence."""
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="no research backend"):
        choose(fixture=tmp_path / "missing.json")
