"""The tool boundary. MCP, then the vendor's own interface, then nothing."""

from __future__ import annotations

import json

import mcp_tools
import pytest
import research


def test_demo_assertions_hold():
    mcp_tools.demo()


def test_an_unset_variable_resolves_to_empty(monkeypatch):
    """Leaving the literal ${VAR} in place makes the server start and then 401,
    which reads like a network problem and is not."""
    monkeypatch.delenv("SOL3_TEST_KEY", raising=False)
    assert mcp_tools.expand("${SOL3_TEST_KEY}") == ""
    monkeypatch.setenv("SOL3_TEST_KEY", "value")
    assert mcp_tools.expand("k=${SOL3_TEST_KEY}") == "k=value"


def test_mcp_config_resolves_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SOL3_TEST_KEY", "secret")
    path = tmp_path / ".mcp.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
                    "perplexity-ask": {
                        "command": "npx",
                        "args": ["-y", "server-perplexity-ask"],
                        "env": {"PERPLEXITY_API_KEY": "${SOL3_TEST_KEY}"},
                    },
                }
            }
        )
    )
    servers = mcp_tools.load_mcp_config(path)
    assert servers["perplexity-ask"]["env"]["PERPLEXITY_API_KEY"] == "secret"
    assert servers["context7"]["url"].endswith("/mcp")


def test_a_missing_config_is_empty_not_an_error(tmp_path):
    assert mcp_tools.load_mcp_config(tmp_path / "nope.json") == {}


def test_http_and_stdio_translate_to_adapter_transports():
    """Claude Code writes `type: http`. The adapter calls it `streamable_http`."""
    assert mcp_tools._adapter_spec({"type": "http", "url": "https://x"})["transport"] == (
        "streamable_http"
    )
    assert mcp_tools._adapter_spec({"command": "npx", "args": []})["transport"] == "stdio"


def test_an_unknown_server_is_unavailable_not_a_crash():
    with pytest.raises(mcp_tools.TransportUnavailable):
        mcp_tools.mcp_tools("no-such-server", {})


def test_citations_are_deduplicated_in_order():
    text = "see https://b.example/2 then https://a.example/1 and https://b.example/2."
    assert mcp_tools.citations_from(text) == ["https://b.example/2", "https://a.example/1"]


def test_a_missing_key_makes_perplexity_unavailable(monkeypatch):
    """Unavailable, not raising. The caller falls through to the fixture."""
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert research.PerplexityBackend().available() is False
    finding = research.PerplexityBackend().search("anything")
    assert finding.empty
    assert "PERPLEXITY_API_KEY" in finding.note


def test_perplexity_falls_back_from_mcp_to_rest(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "k")
    monkeypatch.setattr(
        mcp_tools,
        "ask_perplexity_mcp",
        lambda q, c=None: (_ for _ in ()).throw(mcp_tools.TransportUnavailable("no npx")),
    )
    monkeypatch.setattr(
        mcp_tools,
        "ask_perplexity_rest",
        lambda q: mcp_tools.Answer(text="from rest", transport="perplexity-rest", usd=0.006),
    )
    finding = research.PerplexityBackend().search("q")
    assert finding.answer == "from rest"
    assert finding.usd == 0.006


def test_context7_needs_a_library(monkeypatch):
    """A question with no library is not something this backend can answer, and
    it says so rather than guessing one."""
    finding = research.Context7Backend().search("just a question")
    assert finding.empty
    assert "library" in finding.note


def test_context7_splits_library_from_question(monkeypatch):
    seen = {}

    def fake(library, question, config=None):
        seen["library"], seen["question"] = library, question
        return mcp_tools.Answer(text="docs say yes", transport="context7-cli")

    monkeypatch.setattr(mcp_tools, "ask_context7", fake)
    finding = research.Context7Backend().search("deepagents :: does it take permissions")
    assert seen == {"library": "deepagents", "question": "does it take permissions"}
    assert finding.answer == "docs say yes"


def test_choose_prefers_a_real_search_over_a_recording(monkeypatch, tmp_path):
    fixture = tmp_path / "research.json"
    fixture.write_text("{}")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "k")
    assert research.choose(fixture=fixture).name == "perplexity"
    monkeypatch.delenv("PERPLEXITY_API_KEY")
    assert research.choose(fixture=fixture).name == "fixture"


def test_nothing_is_never_a_backend(tmp_path):
    """A research loop that silently returns no evidence is worse than one that
    refuses."""
    with pytest.raises(RuntimeError):
        research.choose()
