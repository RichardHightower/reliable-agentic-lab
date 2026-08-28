"""Research state. The arithmetic no model gets a vote on."""

from __future__ import annotations

import evidence
import pytest


def source(url, subject="s"):
    return evidence.SourceDocument(title=url, url=url, subject=subject)


def test_demo_assertions_hold():
    evidence.demo()


def test_one_url_is_one_source():
    """Without this, the same page retrieved twice looks like two independent
    sources, and every claim reports as corroborated."""
    ledger = evidence.Ledger("/nonexistent")
    first = ledger.add_source(source("https://a.example"))
    second = ledger.add_source(source("https://a.example"))
    assert first is second
    assert len(ledger.sources) == 1


def test_corroboration_needs_two_distinct_sources():
    claim = evidence.Claim(text="x", subject="s", source_ids=["a", "a"])
    assert evidence.corroborate(claim).truth_state == evidence.SINGLE_SOURCE
    claim.source_ids = ["a", "b"]
    assert evidence.corroborate(claim).truth_state == evidence.CORROBORATED


def test_an_uncited_claim_is_never_usable():
    claim = evidence.Claim(text="x", subject="s")
    evidence.corroborate(claim)
    assert claim.truth_state == evidence.PROPOSED
    assert not claim.usable


def test_a_contradicted_claim_is_never_usable():
    claim = evidence.Claim(text="x", subject="s", source_ids=["a", "b"])
    evidence.corroborate(claim, contradicted=True)
    assert not claim.usable


def test_bibliography_keeps_retrieval_order(tmp_path):
    """Reference numbers come from this order. Sorting by generated id would
    renumber the paper on every rebuild."""
    ledger = evidence.Ledger(tmp_path)
    urls = ["https://c.example", "https://a.example", "https://b.example"]
    ids = [ledger.add_source(source(url)).id for url in urls]
    ledger.add_claim(evidence.Claim(text="x", subject="s", source_ids=ids))
    assert [src.url for src in ledger.bibliography()] == urls


def test_bibliography_order_survives_a_reload(tmp_path):
    ledger = evidence.Ledger(tmp_path / "evidence")
    urls = ["https://c.example", "https://a.example", "https://b.example"]
    ids = [ledger.add_source(source(url)).id for url in urls]
    ledger.add_claim(evidence.Claim(text="x", subject="s", source_ids=ids))
    ledger.write()

    again = evidence.Ledger(tmp_path / "evidence").load()
    assert [src.url for src in again.bibliography()] == urls


def test_an_uncited_source_stays_out_of_the_bibliography():
    ledger = evidence.Ledger("/nonexistent")
    used = ledger.add_source(source("https://used.example"))
    ledger.add_source(source("https://unused.example"))
    ledger.add_claim(evidence.Claim(text="x", subject="s", source_ids=[used.id]))
    assert [src.url for src in ledger.bibliography()] == ["https://used.example"]


def test_front_matter_round_trips(tmp_path):
    claim = evidence.Claim(
        text="A nullable column stores NULL.",
        subject="dt",
        source_ids=["source.a", "source.b"],
        important=True,
        confidence=0.75,
    )
    evidence.corroborate(claim)
    fields, body = evidence.parse_front_matter(claim.to_markdown())
    assert fields["type"] == "Claim"
    assert fields["truth_state"] == evidence.CORROBORATED
    assert fields["important"] is True
    assert fields["confidence"] == 0.75
    assert [link["target"] for link in fields["links"]] == ["source.a", "source.b"]
    assert body.strip() == claim.text


def test_the_record_shape_matches_the_second_brain():
    """These field names are what `research-ingest` reads. Renaming one turns a
    run into something the brain cannot take."""
    fields, _ = evidence.parse_front_matter(
        evidence.Finding(question="q", subject="s", claim_ids=["claim.a"]).to_markdown()
    )
    assert fields["type"] == "Finding"
    assert fields["links"] == [{"rel": "asserts", "target": "claim.a"}]

    fields, _ = evidence.parse_front_matter(source("https://a.example").to_markdown())
    assert fields["type"] == "SourceDocument"
    assert fields["source_hash"].startswith("sha256:")


def test_ledger_round_trips_through_disk(tmp_path):
    ledger = evidence.Ledger(tmp_path / "evidence")
    src = ledger.add_source(source("https://a.example"))
    claim = ledger.add_claim(
        evidence.Claim(text="a fact", subject="s", source_ids=[src.id], important=True)
    )
    evidence.corroborate(claim)
    ledger.add_finding(evidence.Finding(question="q", subject="s", claim_ids=[claim.id]))
    ledger.write()

    again = evidence.Ledger(tmp_path / "evidence").load()
    assert len(again.sources) == 1
    assert len(again.claims) == 1
    assert again.claim(claim.id).truth_state == evidence.SINGLE_SOURCE
    assert again.claim(claim.id).important is True
    assert again.urls_for(claim.id) == ["https://a.example"]


@pytest.mark.parametrize(
    "text,expected",
    [("SQLAlchemy: nullable DateTime!", "sqlalchemy-nullable-datetime"), ("", "untitled")],
)
def test_slug_is_deterministic(text, expected):
    assert evidence.slug(text) == expected


def test_ids_do_not_collide():
    assert len({evidence.new_id() for _ in range(500)}) == 500
