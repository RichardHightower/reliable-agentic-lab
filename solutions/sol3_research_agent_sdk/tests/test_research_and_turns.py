"""The search boundary and the six turns."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import research
import source_policy
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
    assert "done, then cost, then max turns" in finding.answer
    assert finding.citations


def test_a_missing_fixture_is_unavailable_not_a_crash(tmp_path):
    assert not research.FixtureBackend(tmp_path / "nope.json").available()


# -- perplexity -------------------------------------------------------------


def test_legacy_sonar_payloads_still_pass_the_source_wall():
    payload = {
        "choices": [{"message": {"content": " an answer "}}],
        "search_results": [{"url": "https://docs.langchain.com/a", "title": "A"}],
        "citations": ["https://docs.langchain.com/a", "https://deepwiki.com/b"],
    }
    finding = research._finding_from_sonar("q", payload, "perplexity", 0.006)
    assert finding.answer == "an answer"
    assert finding.citations == ["https://docs.langchain.com/a"]
    assert finding.sources[0] == {"url": "https://docs.langchain.com/a", "title": "A"}


def test_a_response_missing_search_results_keeps_an_allowed_citation():
    payload = {
        "choices": [{"message": {"content": "x"}}],
        "citations": ["https://docs.langchain.com/a"],
    }
    assert research._finding_from_sonar("q", payload, "p", 0.0).citations == [
        "https://docs.langchain.com/a"
    ]


def test_an_empty_response_produces_no_citations():
    """No answer and no source. The grounding check fails it, which is right."""
    finding = research._finding_from_sonar("q", {}, "p", 0.0)
    assert finding.answer == "" and finding.citations == []


def test_choose_uses_perplexity_then_anthropic_then_the_fixture(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert research.FALLBACK_CHAIN == ("perplexity", "anthropic", "fixture")
    assert research.choose(fixture=FIXTURE, ask=lambda q: None).name == "anthropic"
    assert research.choose(fixture=FIXTURE).name == "fixture"
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    assert research.choose(fixture=FIXTURE).name == "perplexity"


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _perplexity_responses(monkeypatch, payloads):
    calls = []

    def open_(request, timeout):
        calls.append((request.full_url, json.loads(request.data.decode("utf-8"))))
        return _Response(payloads.pop(0))

    monkeypatch.setattr(research.urllib.request, "urlopen", open_)
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    return calls


def test_perplexity_search_sends_the_allowlist_and_drops_deepwiki(monkeypatch):
    calls = _perplexity_responses(
        monkeypatch,
        [
            {"results": [{"url": "https://medium.com/post", "title": "Blog", "snippet": "no"}]},
            {
                "results": [
                    {
                        "url": "https://docs.langchain.com/oss/python/langchain/overview",
                        "title": "LangChain docs",
                        "snippet": "Official excerpt.",
                    },
                    {
                        "url": "https://deepwiki.com/langchain-ai/langchain",
                        "title": "DeepWiki",
                        "snippet": "A blog-like copy.",
                    },
                ]
            },
        ],
    )

    finding = research.PerplexityBackend().search("how does the loop stop")

    assert finding.citations == ["https://docs.langchain.com/oss/python/langchain/overview"]
    assert len(calls) == 2
    assert all(url == research.PERPLEXITY_SEARCH_URL for url, _ in calls)
    assert calls[0][1]["search_domain_filter"] == list(source_policy.SEED_ALLOWLIST)
    assert calls[1][1]["search_domain_filter"] == list(source_policy.SEED_ALLOWLIST)


def test_scout_rejects_medium_but_can_add_an_official_docs_host():
    merged = source_policy.merge_scout_domains(
        ["https://medium.com/guess", "https://docs.example.vendor/guide"]
    )
    assert "medium.com" not in merged
    assert "docs.example.vendor" in merged


def test_perplexity_does_not_ask_when_search_includes_quotes(monkeypatch):
    calls = _perplexity_responses(
        monkeypatch,
        [
            {"results": [{"url": "https://docs.langchain.com/a", "title": "A", "snippet": "Scout"}]},
            {"results": [{"url": "https://docs.langchain.com/a", "title": "A", "snippet": "Quote"}]},
        ],
    )

    research.PerplexityBackend().search("q")

    assert len(calls) == 2
    assert all(urlsplit(url).path == "/search" for url, _ in calls)


def test_perplexity_asks_once_when_search_has_hits_but_no_quote(monkeypatch):
    calls = _perplexity_responses(
        monkeypatch,
        [
            {"results": [{"url": "https://docs.langchain.com/a", "title": "A", "snippet": "Scout"}]},
            {"results": [{"url": "https://docs.langchain.com/a", "title": "A", "snippet": ""}]},
            {
                "output_text": "Quoted answer.",
                "citations": ["https://docs.langchain.com/a"],
            },
        ],
    )

    finding = research.PerplexityBackend().search("q")

    assert finding.answer == "Quoted answer."
    assert len(calls) == 3
    assert calls[-1][0] == research.PERPLEXITY_ASK_URL
    assert calls[-1][1]["tools"][0]["filters"]["search_domain_filter"] == calls[1][1][
        "search_domain_filter"
    ]


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


def test_every_body_bearing_turn_receives_the_whole_section(work):
    """Proof the turns call `whole`. Testing `whole` alone proved nothing.

    Reverting all four call sites to `body[:8000]` left the helper tests green.
    A helper test does not catch a turn that stopped calling the helper. The
    Deep Agents port already paid for this lesson in #324.
    """
    tail = "The last paragraph carries the load-bearing number, 42 percent. [1]"
    body = (
        "Opening paragraph. [1]\n\n"
        + "\n\n".join("Filler sentence about loops. " * 20 for _ in range(20))
        + "\n\n"
        + tail
    )
    assert len(body) > 8000, "the body must exceed the old ceiling"
    assert len(body) < t.BODY_PROMPT_CHARS, "and stay under the new one"

    section = {"id": "s1", "heading": "Bounding the loop"}
    verdict = {"failed_rows": ["depth"], "notes": ["no mechanism"]}
    cases = (
        ("judge_section", lambda turn: turn.judge_section(section, body, [])),
        ("ledger_turn", lambda turn: turn.ledger_turn(section, body)),
        ("edit_section", lambda turn: turn.edit_section(section, body, verdict)),
        ("edit_paper", lambda turn: turn.edit_paper(section, body)),
    )
    for name, call in cases:
        backend = Backend([result(output="{}", structured={})])
        call(t.SdkTurns(backend=backend, work_dir=work))
        prompt = backend.prompts[0][0]
        assert tail in prompt, f"{name} lost the end of the section"


def test_a_body_past_the_ceiling_is_cut_on_a_paragraph_and_declared(work):
    backend = Backend([result(output="{}", structured={})])
    body = "\n\n".join(f"Paragraph {n}. " + "word " * 60 for n in range(400))
    assert len(body) > t.BODY_PROMPT_CHARS
    t.SdkTurns(backend=backend, work_dir=work).judge_section({"id": "s1"}, body, [])
    prompt = backend.prompts[0][0]
    assert "withheld for length" in prompt
    assert "Do not fail objective_met" in prompt


def test_the_writer_is_shown_the_string_the_coverage_row_matches(work):
    """The writer was told to reproduce the researcher's note verbatim, so it did.

    It pasted 460 characters of note, corpus ULIDs included, into an HTML
    comment to satisfy `coverage`. The `cited` row then failed on the comment.
    """
    question = "What stops the loop? (Answered by the pack: knowledge:claim.loop.01M0.)"
    section = {
        "id": "s1",
        "heading": "Stopping",
        "key_questions": [question],
        "figures": [],
        "word_target": 200,
    }
    backend = Backend([result(output="a section")])
    turn = t.SdkTurns(backend=backend, work_dir=work)
    turn.write(section, [{"number": 1, "text": "A thing."}], [], "", path="sections/s1.md")
    prompt = backend.prompts[0][0]
    assert "What stops the loop?" in prompt
    assert "knowledge:claim.loop.01M0" not in prompt, prompt


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


def test_sdk_research_cannot_return_a_deepwiki_claim(work):
    backend = Backend(
        [
            result(
                structured={
                    "answer": "two sources",
                    "sources": [
                        {"url": "https://deepwiki.com/x", "title": "copy"},
                        {"url": "https://docs.langchain.com/x", "title": "docs"},
                    ],
                    "claims": [
                        {"text": "bad", "source_url": "https://deepwiki.com/x", "quote": "bad"},
                        {"text": "good", "source_url": "https://docs.langchain.com/x", "quote": "good"},
                    ],
                }
            )
        ]
    )

    finding = t.SdkTurns(backend=backend, work_dir=work).research("q")

    assert finding["sources"] == [{"url": "https://docs.langchain.com/x", "title": "docs"}]
    assert finding["claims"] == [
        {"text": "good", "source_url": "https://docs.langchain.com/x", "quote": "good"}
    ]


def test_the_exit_doctrine_finding_accepts_only_this_repository(work):
    repository = "https://github.com/RichardHightower/reliable-agentic-lab/tree/main/solutions/sol3_research_agent_sdk"
    backend = Backend(
        [
            result(
                structured={
                    "answer": "two sources",
                    "sources": [
                        {"url": "https://docs.langchain.com/x", "title": "framework"},
                        {"url": repository, "title": "this repository"},
                    ],
                    "claims": [
                        {"text": "framework", "source_url": "https://docs.langchain.com/x", "quote": "x"},
                        {"text": "repo", "source_url": repository, "quote": "y"},
                    ],
                }
            )
        ]
    )

    finding = t.SdkTurns(backend=backend, work_dir=work).research(t.EXIT_DOCTRINE_QUESTION)

    assert [source["url"] for source in finding["sources"]] == [repository]
    assert [claim["text"] for claim in finding["claims"]] == ["repo"]


def test_the_offline_outline_includes_the_exit_doctrine_question(work):
    offline = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    drafted = offline.plan("topic", "")
    questions = [q for s in drafted["sections"] for q in s["key_questions"]]
    assert t.EXIT_DOCTRINE_QUESTION in questions

    backend = Backend(
        [result(structured={"title": "t", "audience": "a", "thesis": "x", "word_target_total": 400, "sections": []})]
    )
    t.SdkTurns(backend=backend, work_dir=work).outline("topic", "")
    assert "research-outliner" in backend.prompts[0][0]
    assert t.EXIT_DOCTRINE_QUESTION not in backend.prompts[0][0]


def test_the_offline_outline_reads_as_prose():
    """The topic is the title, not a template hole.

    Interpolating 'how MCP servers authenticate' into 'Describe how {topic}
    works' produced 'how how MCP servers authenticate works'. Section
    objectives and questions have to be English on their own.
    """
    import outline as outlines  # noqa: PLC0415

    offline = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    topic = "how MCP servers authenticate"
    drafted = offline.outline(topic, "")
    rendered = outlines.to_markdown(drafted).lower()
    assert "how how" not in rendered
    assert drafted["title"].lower().startswith("how mcp")
    assert topic in drafted["thesis"]
    for section in drafted["sections"]:
        objective = section["objective"]
        assert objective[0].isupper(), objective
        assert topic not in objective, objective
        assert not objective.lower().startswith("describe how how")
        assert not objective.lower().startswith("state what how")
        for question in section["key_questions"]:
            assert "how how" not in question.lower(), question
            assert not question.lower().startswith(topic), question
            assert question[0].isupper() or question[0].isdigit(), question


def test_bind_exit_doctrine_still_exists_for_the_commissioning_brief():
    """Removed from the normal outline path. Reachable for E2E via the brief."""
    plan = {
        "sections": [{"id": "problem"}],
        "questions": [{"id": "q1", "text": "other", "section": "problem"}],
    }
    bound = t.bind_exit_doctrine(plan)
    assert bound["questions"][0]["text"] == t.EXIT_DOCTRINE_QUESTION


def test_each_turn_declares_the_scope_it_may_write(work):
    backend = Backend([result(structured={"language": "mermaid", "source": "", "caption": ""})])
    t.SdkTurns(backend=backend, work_dir=work).diagram("pipeline", "c")
    assert backend.prompts[0][1] == ["diagrams/pipeline.mmd", "diagrams/pipeline.puml"]


def test_cost_is_reported_to_the_driver(work):
    spent = []
    backend = Backend([result(usd=0.42, cost_reported=True, structured={"verdict": "supports"})])
    t.SdkTurns(
        backend=backend,
        work_dir=work,
        on_cost=lambda usd, **detail: spent.append((usd, detail)),
    ).verify("c")
    assert spent[0][0] == 0.42
    assert spent[0][1]["role"] == "research-verifier"


def test_a_turn_with_no_cost_field_reports_none_not_zero(work):
    """A bare 0.0 reads as a free turn and hides a broken cost path (#303)."""
    spent = []
    backend = Backend([result(structured={"verdict": "supports"})])
    t.SdkTurns(
        backend=backend,
        work_dir=work,
        on_cost=lambda usd, **detail: spent.append(usd),
    ).verify("c")
    assert spent == [None]


def test_the_turn_detail_names_the_role_and_the_elapsed_time(work):
    seen = {}
    backend = Backend([result(elapsed_s=12.5, prompt_chars=400, events=7, structured={"verdict": "supports"})])
    t.SdkTurns(
        backend=backend,
        work_dir=work,
        on_cost=lambda usd, **detail: seen.update(detail),
    ).verify("c")
    assert seen["elapsed_s"] == 12.5
    assert seen["prompt_chars"] == 400
    assert seen["events"] == 7


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


def test_the_offline_writer_unpacks_a_claim_into_a_section():
    """A one-sentence echo of the claim is a brief, not a paper."""
    import checks  # noqa: PLC0415

    turn = t.OfflineTurns(backend=research.FixtureBackend(FIXTURE))
    claim = {
        "text": "The paper loop checks three exits: done, then cost, then max turns.",
        "number": 1,
        "status": "verified",
    }
    body = turn.write({"id": "s", "heading": "The approach", "goal": "g"}, [claim], [], "")
    assert checks.word_count(body) >= 400
    assert "—" not in body
    assert "[1]" in body


def test_developed_claims_clear_the_paper_floor():
    import checks  # noqa: PLC0415

    claim = "The paper loop checks three exits in this order: done, then cost, then max turns."
    parts = []
    for index in range(1, 5):
        parts += t.develop_claim(claim, f"[{index}]")
    assert checks.word_count("\n".join(parts)) >= checks.MIN_WORDS


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


def test_the_writer_prompt_names_key_questions_and_the_claim_number(work):
    """Coverage is a substring match. A writer that never sees the question
    paraphrases it and fails. Cite-by-number is the card; the id is not.
    """
    backend = Backend([result(output="## The problem\n")])
    section = {
        "id": "s1",
        "heading": "The problem",
        "objective": "State it.",
        "abstract": "An abstract.",
        "key_questions": ["what three exits does the loop check", "why does order matter"],
        "claims_to_support": ["The exits are arithmetic."],
        "word_target": 400,
    }
    claims = [
        {"id": "s1-f1", "text": "Done then cost then turns.", "number": 3, "status": "verified"}
    ]
    t.SdkTurns(backend=backend, work_dir=work).write(section, claims, [], "", "sections/s1.md")
    prompt = backend.prompts[0][0]
    assert "what three exits does the loop check" in prompt
    assert "why does order matter" in prompt
    assert "Cite each claim by its `number` field" in prompt
    assert '"number": 3' in prompt
