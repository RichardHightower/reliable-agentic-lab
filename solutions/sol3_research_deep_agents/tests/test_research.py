from __future__ import annotations

import os
from pathlib import Path

import loop
import mcp_tools
import evidence
import research
import researcher
import pytest
import roles
import stages

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


def test_budget_limits_one_research_request_and_persists_its_charge():
    charges = []
    budget = research.Budget(max_calls=3, max_usd=1, on_charge=charges.append)
    budget.begin_request(max_calls=1)
    budget.charge(0.01)
    with pytest.raises(research.BudgetExceeded, match="request search budget"):
        budget.charge(0.01)
    budget.end_request()

    assert charges == [0.01]
    assert budget.calls == 1
    assert budget.spent_usd == 0.01


def test_one_tool_request_can_reserve_scout_retrieve_and_no_quote_ask():
    budget = research.Budget(max_calls=4, max_usd=1)
    budget.begin_request(max_calls=1, max_provider_calls=3)
    budget.reserve_tool()
    budget.charge(0.01)
    budget.charge(0.01)
    budget.charge(0.01)
    with pytest.raises(research.BudgetExceeded, match="tool call"):
        budget.reserve_tool()
    with pytest.raises(research.BudgetExceeded, match="request search budget"):
        budget.charge(0.01)
    budget.end_request()


def test_perplexity_drops_deepwiki_and_does_not_ask_when_search_has_quotes(monkeypatch):
    calls = []

    def search(question, domains, config=None):
        calls.append(("search", domains))
        return mcp_tools.Answer(
            text="A quoted official source https://docs.langchain.com/deep-agents",
            citations=["https://deepwiki.com/langchain", "https://docs.langchain.com/deep-agents"],
            hits=2,
            usable_quotes=True,
        )

    monkeypatch.setattr(mcp_tools, "search_perplexity", search)
    monkeypatch.setattr(
        mcp_tools,
        "ask_perplexity",
        lambda *_: pytest.fail("Ask may only run for hits without usable quotes"),
    )

    finding = research.PerplexityBackend().search("q")

    assert len(calls) == 2, "Scout and Retrieve are inside one researcher tool call"
    assert finding.citations == ["https://docs.langchain.com/deep-agents"]
    assert "deepwiki" not in finding.answer.lower() or "deepwiki" not in finding.citations


def test_perplexity_asks_once_when_search_hits_lack_usable_quotes(monkeypatch):
    calls = {"search": 0, "ask": 0}

    def search(question, domains, config=None):
        calls["search"] += 1
        return mcp_tools.Answer(
            text="Result https://docs.langchain.com/deep-agents",
            citations=["https://docs.langchain.com/deep-agents"],
            hits=1,
            usable_quotes=False,
        )

    def ask(question, domains, config=None):
        calls["ask"] += 1
        return mcp_tools.Answer(
            text="The official source says the graph has a recursion limit.",
            citations=["https://docs.langchain.com/deep-agents"],
        )

    monkeypatch.setattr(mcp_tools, "search_perplexity", search)
    monkeypatch.setattr(mcp_tools, "ask_perplexity", ask)

    finding = research.PerplexityBackend().search("q")

    assert calls == {"search": 2, "ask": 1}
    assert finding.citations == ["https://docs.langchain.com/deep-agents"]


def test_fallback_receipt_names_the_provider_and_transport_that_answered():
    class LiveProvider(research.Backend):
        name = "perplexity"
        transport = "perplexity-search-rest"

        def search(self, question, reserve=None):
            return research.Finding(
                question,
                "grounded answer",
                citations=["https://docs.langchain.com/deep-agents"],
                backend=self.name,
            )

    backend = research.FallbackBackend([LiveProvider()])
    backend.search("q")

    assert backend.active_name == "perplexity"
    assert backend.active_transport == "perplexity-search-rest"


def test_repository_exit_doctrine_uses_the_checked_in_first_party_source():
    finding = research.FallbackBackend([]).search(research.EXIT_DOCTRINE_QUESTION)

    assert finding.backend == "repository"
    assert finding.citations == [research.REPOSITORY_PAPER_URL]
    assert finding.answer.index("if done:") < finding.answer.index("if spent_usd")
    assert finding.answer.index("if spent_usd") < finding.answer.index("if exhausted:")


def test_repository_exit_doctrine_tolerates_the_researchers_narrowing_context():
    finding = research.FallbackBackend([]).search(
        research.EXIT_DOCTRINE_QUESTION
        + " Cite the repo paper loop implementation and preserve the order."
    )

    assert finding.backend == "repository"
    assert finding.citations == [research.REPOSITORY_PAPER_URL]


def test_repository_exit_doctrine_report_is_ready_for_the_evidence_ledger():
    report = research.repository_doctrine_report(research.EXIT_DOCTRINE_QUESTION)

    assert report["sources"][0]["url"] == research.REPOSITORY_PAPER_URL
    assert report["sources"][0]["quote"].index("if done:") < report["sources"][0][
        "quote"
    ].index("if spent_usd")
    assert report["claims"][0]["source_urls"] == [research.REPOSITORY_PAPER_URL]


def test_repository_source_adapter_does_not_answer_any_other_question():
    finding = research.FallbackBackend([]).search("What are loop engineering best practices?")

    assert finding.empty
    assert finding.provider_unavailable


def test_python_post_filter_keeps_docs_and_drops_deepwiki_from_model_json(tmp_path):
    ledger = evidence.Ledger(tmp_path / "evidence")
    finding = stages.record_findings(
        ledger,
        {"subject": "sources", "question": "q", "important": True},
        {
            "answer": "mixed sources",
            "sources": [
                {"title": "DeepWiki", "url": "https://deepwiki.com/langchain", "quote": "no"},
                {"title": "LangChain docs", "url": "https://docs.langchain.com/deep-agents", "quote": "yes"},
            ],
            "claims": [
                {
                    "text": "An allowed fact",
                    "confidence": 0.8,
                    "source_urls": [
                        "https://deepwiki.com/langchain",
                        "https://docs.langchain.com/deep-agents",
                    ],
                }
            ],
        },
    )

    assert finding.claim_ids
    assert [source.url for source in ledger.sources.values()] == ["https://docs.langchain.com/deep-agents"]


@pytest.mark.parametrize("location", range(4))
def test_load_dotenv_finds_a_key_in_each_supported_parent(tmp_path, monkeypatch, location):
    anchor = tmp_path / "one" / "two" / "three" / "solution"
    paths = research.dotenv_paths(anchor)
    paths[location].parent.mkdir(parents=True, exist_ok=True)
    paths[location].write_text("PERPLEXITY_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    research.load_dotenv(paths)

    assert os.environ["PERPLEXITY_API_KEY"] == "from-dotenv"


def test_load_dotenv_keeps_an_exported_key_and_prefers_nearest_file(tmp_path, monkeypatch):
    anchor = tmp_path / "one" / "two" / "three" / "solution"
    local, _, root, _ = research.dotenv_paths(anchor)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("PERPLEXITY_API_KEY=local\n", encoding="utf-8")
    root.parent.mkdir(parents=True, exist_ok=True)
    root.write_text("PERPLEXITY_API_KEY=root\n", encoding="utf-8")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    research.load_dotenv(research.dotenv_paths(anchor))
    assert os.environ["PERPLEXITY_API_KEY"] == "local"

    monkeypatch.setenv("PERPLEXITY_API_KEY", "exported")
    research.load_dotenv(research.dotenv_paths(anchor))
    assert os.environ["PERPLEXITY_API_KEY"] == "exported"


def test_websearch_reads_a_recorded_answer_before_using_the_network(tmp_path):
    question = "How does a production agent loop stop?"
    inbox = tmp_path / "answers.json"
    inbox.write_text(
        '{"How does a production agent loop stop?": {"answer": "With explicit exits.", '
        '"citations": ["https://example.com/exits"]}}',
        encoding="utf-8",
    )

    finding = research.WebSearchBackend(inbox).search(question)

    assert finding.answer == "With explicit exits."
    assert finding.citations == ["https://example.com/exits"]
    assert finding.note == "recorded web-search answer"


def test_websearch_returns_result_urls_without_a_key(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return (
                b'<li class="b_algo"><h2><a href="https://example.com/one">'
                b"Primary source</a></h2>"
                b"<p>An evidence-bearing result.</p></li>"
            )

    monkeypatch.setattr(research, "urlopen", lambda *_args, **_kwargs: Response())

    finding = research.WebSearchBackend().search("production agent loop exits")

    assert finding.backend == "websearch"
    assert finding.citations == ["https://example.com/one"]
    assert "Primary source" in finding.answer


def test_websearch_unwraps_bing_result_redirects():
    target = research._result_url(
        "https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9vbmU"
    )

    assert target == "https://example.com/one"


def test_researcher_has_search_not_write(fake_langchain, tmp_path):
    backend = research.FixtureBackend(FIXTURE)
    agents = _by_name(roles.subagents_for(None, backend=backend))
    researcher_agent = agents["researcher"]
    names = [t.__name__ for t in researcher_agent["tools"]]
    assert "search" in names
    assert "write" not in names
    judge = agents["judge"]
    assert judge["tools"] == []


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
    import subprocess  # noqa: PLC0415  (sys.path is set by conftest first)

    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []
