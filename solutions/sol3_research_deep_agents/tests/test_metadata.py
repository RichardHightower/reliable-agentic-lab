"""Reference metadata comes from the record, not the model. #470

Every test here is offline. The fixture backend path is asserted never to
call the network transport at all; the "live" path is exercised only against
a monkeypatched `metadata._get`, never a real socket.
"""

from __future__ import annotations

import pytest

import metadata

PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/12345678/"
ARXIV_URL = "https://arxiv.org/abs/2401.01234"
DOI_URL = "https://doi.org/10.1000/xyz123"


class FixtureBackend:
    name = "fixture"


class LiveBackend:
    name = "perplexity"


def test_a_pubmed_url_renders_the_recorded_title():
    record = metadata.fetch_record(PUBMED_URL, FixtureBackend(), model_title="Wrong Model Title")
    assert record["title"] == (
        "The Interplay Between Physical Activity, Protein Consumption, and Sleep "
        "Quality in Muscle Protein Synthesis"
    )
    assert record["authors"] == ["Nakamura K", "Ortiz L"]
    assert record["year"] == "2022"
    assert record["venue"] == "Journal of Applied Physiology"


def test_a_title_that_differs_by_a_third_writes_the_note():
    record = metadata.fetch_record(
        PUBMED_URL,
        FixtureBackend(),
        model_title="The Interplay Between Physical Activity, Protein Consumption, and Energy Balance",
    )
    assert "title_mismatch" in record["note"], record

    # A title that is nearly the same word for word gets no note.
    close = metadata.fetch_record(
        PUBMED_URL,
        FixtureBackend(),
        model_title=(
            "The Interplay Between Physical Activity, Protein Consumption, and Sleep "
            "Quality in Muscle Protein Synthesis"
        ),
    )
    assert close["note"] == ""


def test_a_fetch_timeout_keeps_the_model_title(monkeypatch):
    def _boom(_url):
        raise TimeoutError("timed out")

    monkeypatch.setattr(metadata, "_get", _boom)
    record = metadata.fetch_record(
        "https://docs.example.com/some-page", LiveBackend(), model_title="Original Model Title"
    )
    assert record["title"] == "Original Model Title"
    assert record["note"], "a failed fetch still explains itself"


def test_the_fixture_backend_makes_no_network_call(monkeypatch):
    def _boom(_url):
        raise AssertionError("the fixture backend must never reach the network")

    monkeypatch.setattr(metadata, "_get", _boom)

    # A url with a recorded reply.
    record = metadata.fetch_record(PUBMED_URL, FixtureBackend(), model_title="Kept")
    assert record["title"] != "Kept"

    # A url with no recorded reply still never calls the network.
    miss = metadata.fetch_record("https://example.invalid/nothing-here", FixtureBackend(), model_title="Kept")
    assert miss["title"] == "Kept"
    assert "no recorded reply" in miss["note"]


def test_an_arxiv_id_and_a_doi_resolve_through_their_apis():
    arxiv = metadata.fetch_record(ARXIV_URL, FixtureBackend())
    assert arxiv["title"] == "Exit Conditions for Long-Running Agent Loops"
    assert arxiv["authors"] == ["A. Researcher", "B. Coauthor"]
    assert arxiv["year"] == "2024"
    assert arxiv["venue"] == "arXiv"

    doi = metadata.fetch_record(DOI_URL, FixtureBackend())
    assert doi["title"] == "Position Stand on Creatine Supplementation and Lean Mass"
    assert doi["authors"] == ["Jane Smith", "Miguel Alvarez"]
    assert doi["year"] == "2021"
    assert doi["venue"] == "International Journal of Sports Nutrition"


def test_a_url_with_no_backend_information_keeps_the_model_title():
    record = metadata.fetch_record("", FixtureBackend(), model_title="Untouched")
    assert record["title"] == "Untouched"
