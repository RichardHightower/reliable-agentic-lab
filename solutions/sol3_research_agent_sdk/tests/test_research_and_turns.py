"""The search boundary and the six turns."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import research
import turns as t

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "research.json"


# -- the budget -------------------------------------------------------------


def test_the_hard_cap_raises_it_does_not_warn():
    budget = research.Budget(max_usd=0.01, max_calls=9)
    with pytest.raises(research.BudgetExceeded, match="money budget"):
        budget.charge(0.02)


def test_the_call_ceiling_is_separate_from_the_money_one():
    budget = research.Budget(max_usd=100.0, max_calls=1)
    budget.charge(0.0)
    with pytest.raises(research.BudgetExceeded, match="call budget"):
        budget.charge(0.0)


def test_a_free_backend_still_burns_a_call():
    """A zero-cost search is not a free search. It is a turn and a page fetch."""
    scholar = research.Researcher(
        backend=research.FixtureBackend(FIXTURE), budget=research.Budget(max_calls=1)
    )
    scholar.ask("loop engineering exit criteria")
    with pytest.raises(research.BudgetExceeded):
        scholar.ask("again")


# -- the fixture ------------------------------------------------------------


def test_a_note_in_the_fixture_is_not_an_answer():
    """An underscore key is a comment. It must not become the nearest match."""
    finding = research.FixtureBackend(FIXTURE).search("something never recorded")
    assert finding.answer
    assert "Recorded answers" not in finding.answer


def test_the_fixture_falls_back_to_the_nearest_question():
    finding = research.FixtureBackend(FIXTURE).search("loop engineering exit criteria")
    assert "max_turns" in finding.answer
    assert finding.citations


def test_a_missing_fixture_is_unavailable_not_a_crash(tmp_path):
    assert not research.FixtureBackend(tmp_path / "nope.json").available()


# -- perplexity -------------------------------------------------------------


def test_sonar_citations_and_search_results_are_merged():
    payload = {
        "choices": [{"message": {"content": " an answer "}}],
        "search_results": [{"url": "https://a", "title": "A"}],
        "citations": ["https://a", "https://b"],
    }
    finding = research._finding_from_sonar("q", payload, "perplexity", 0.006)
    assert finding.answer == "an answer"
    assert finding.citations == ["https://a", "https://b"]
    assert finding.sources[0] == {"url": "https://a", "title": "A"}


def test_a_response_missing_search_results_keeps_its_citations():
    payload = {"choices": [{"message": {"content": "x"}}], "citations": ["https://a"]}
    assert research._finding_from_sonar("q", payload, "p", 0.0).citations == ["https://a"]


def test_an_empty_response_produces_no_citations():
    """No answer and no source. The grounding check fails it, which is right."""
    finding = research._finding_from_sonar("q", {}, "p", 0.0)
    assert finding.answer == "" and finding.citations == []


def test_choose_prefers_the_agent_then_perplexity_then_the_fixture(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert research.choose(fixture=FIXTURE, ask=lambda q: None).name == "agent"
    assert research.choose(fixture=FIXTURE).name == "fixture"
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    assert research.choose(fixture=FIXTURE).name == "perplexity"


def test_no_backend_at_all_refuses(monkeypatch, tmp_path):
    """Silently returning no evidence is worse than refusing."""
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="no research backend"):
        research.choose(fixture=tmp_path / "nope.json")


# -- json extraction --------------------------------------------------------


def test_it_walks_braces_rather_than_using_the_last_one():
    """A trailing list swallows everything between find and rfind."""
    assert t.extract_json('{"a": 1}\n\n- see [1] and {2}') == {"a": 1}


def test_a_brace_inside_a_string_does_not_close_the_object():
    assert t.extract_json('{"a": "}"}') == {"a": "}"}
    assert t.extract_json('{"a": "\\\\"}') == {"a": "\\"}


def test_no_json_returns_none():
    assert t.extract_json("just prose") is None
    assert t.extract_json("{not json}") is None


# -- the sdk turns ----------------------------------------------------------


class Backend:
    def __init__(self, results):
        self.results = list(results)
        self.prompts = []

    def run(self, *, root, prompt, allow, **extra):
        self.prompts.append((prompt, allow, extra.get("output_format")))
        return self.results.pop(0)


def result(**kwargs):
    from adapter import TurnResult  # noqa: PLC0415

    return TurnResult(**kwargs)


def test_structured_output_is_the_happy_path(work):
    backend = Backend([result(output="", structured={"verdict": "supports"})])
    turn = t.SdkTurns(backend=backend, work_dir=work)
    assert turn.verify("a claim")["verdict"] == "supports"


def test_text_json_is_the_fallback(work):
    backend = Backend([result(output='noise {"verdict": "unclear"} tail')])
    turn = t.SdkTurns(backend=backend, work_dir=work)
    assert turn.verify("a claim")["verdict"] == "unclear"


def test_a_turn_with_no_json_fails_loudly(work):
    backend = Backend([result(output="I could not decide.")])
    with pytest.raises(t.TurnFailed, match="no JSON object"):
        t.SdkTurns(backend=backend, work_dir=work).verify("a claim")


def test_a_runtime_ceiling_escalates_rather_than_retrying(work):
    """Retrying spends the rest of the budget rediscovering the same ceiling."""
    backend = Backend([result(output="", stop_reason="max turns")])
    with pytest.raises(t.Escalate, match="max turns"):
        t.SdkTurns(backend=backend, work_dir=work).research("q")


def test_every_turn_names_its_agent(work):
    backend = Backend([result(structured={"verdict": "supports"})])
    t.SdkTurns(backend=backend, work_dir=work).verify("a claim")
    assert backend.prompts[0][0].startswith("Use the research-verifier agent.")


def test_the_verify_prompt_carries_the_claim_and_nothing_else(work):
    backend = Backend([result(structured={"verdict": "supports"})])
    t.SdkTurns(backend=backend, work_dir=work).verify("the claim text")
    prompt = backend.prompts[0][0]
    assert "the claim text" in prompt
    assert "Search for it yourself" in prompt


def test_a_generating_turn_carries_the_grounding_contract(work):
    backend = Backend([result(structured={"answer": "", "sources": [], "claims": []})])
    t.SdkTurns(backend=backend, work_dir=work).research("q")
    assert "grounding_contract" in backend.prompts[0][0]


def test_each_turn_declares_the_scope_it_may_write(work):
    backend = Backend([result(structured={"language": "mermaid", "source": "", "caption": ""})])
    t.SdkTurns(backend=backend, work_dir=work).diagram("pipeline", "c")
    assert backend.prompts[0][1] == ["diagrams/pipeline.mmd", "diagrams/pipeline.puml"]


def test_cost_is_reported_to_the_driver(work):
    spent = []
    backend = Backend([result(usd=0.42, structured={"verdict": "supports"})])
    t.SdkTurns(backend=backend, work_dir=work, on_cost=spent.append).verify("c")
    assert spent == [0.42]


# -- the offline twin -------------------------------------------------------


def test_the_offline_verifier_says_unclear_when_it_cannot_match():
    """A crude test that is honest about being crude."""
    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    assert turn.verify("something entirely unrelated to any recording")["verdict"] == "unclear"


def test_the_offline_verifier_agrees_when_the_words_line_up():
    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    recorded = json.loads(FIXTURE.read_text())["loop engineering exit criteria"]["answer"]
    assert turn.verify(recorded)["verdict"] == "supports"


def test_the_offline_writer_never_invents_a_citation_marker():
    """Satisfying the check with a fake marker is the dishonesty it exists for."""
    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    body = turn.write({"id": "s", "heading": "H", "goal": "State it."}, [], [], "")
    assert "[0]" not in body
    import checks  # noqa: PLC0415

    assert checks.uncited_claims(body) == []


def test_the_offline_writer_marks_a_weaker_claim_as_weaker():
    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    section = {"id": "s", "heading": "H", "goal": "g"}
    disputed = turn.write(section, [{"text": "X.", "number": 1, "status": "disputed"}], [], "")
    unverified = turn.write(section, [{"text": "X.", "number": 1, "status": "unverified"}], [], "")
    assert "Sources disagree" in disputed
    assert "unconfirmed" in unverified


def test_the_offline_judge_adds_no_opinion_of_its_own():
    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    assert turn.review("body", "PASS  cited      ok")["done"]
    assert not turn.review("body", "FAIL  cited      no")["done"]
