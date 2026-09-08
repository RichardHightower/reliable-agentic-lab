"""Research state. The arithmetic no model gets a vote on."""

from __future__ import annotations

import re

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
    # #471: two raw source ids are not two attributed bindings.
    assert evidence.corroborate(claim).truth_state == evidence.SINGLE_SOURCE
    claim.attributed_source_ids = ["a", "b"]
    assert evidence.corroborate(claim).truth_state == evidence.CORROBORATED


def test_attributed_requires_the_quote_or_the_numbers_to_appear():
    """#471: the two signals `attributed()` checks, and the default when a
    claim carries neither. `quote` is the researcher's own excerpt for this
    binding (`SourceDocument.body`), not a substring of `claim.text`."""
    quoted = evidence.Claim(text="The page states that creatine improves lean mass.", subject="s")
    assert evidence.attributed(
        quoted, "A review notes creatine improves lean mass in trained adults.", quote="creatine improves lean mass"
    )
    assert not evidence.attributed(
        quoted, "This page never mentions lean mass at all.", quote="creatine improves lean mass"
    )

    numeric = evidence.Claim(text="The study enrolled 42 participants.", subject="s")
    assert evidence.attributed(numeric, "Of the 42 participants who enrolled, most finished.")
    assert not evidence.attributed(numeric, "The study enrolled a different number of people.")

    # Every one of the claim's numbers must appear, not just one. #471
    dosage = evidence.Claim(text="Creatine adds 1.2 kg of lean mass over 12 weeks.", subject="s")
    assert not evidence.attributed(dosage, "This was a 12 week study of resistance-trained adults.")
    assert evidence.attributed(dosage, "Over 12 weeks, creatine added 1.2 kg of lean mass on average.")

    plain = evidence.Claim(text="Creatine is widely studied.", subject="s")
    assert evidence.attributed(plain, "This text is about something unrelated."), (
        "nothing to check is not a failure"
    )


def test_a_study_object_survives_a_ledger_round_trip(tmp_path):
    """Unused until #478's study table; the field only has to persist. #471"""
    source = evidence.SourceDocument(title="A Study", url="https://study.example/x", subject="s")
    claim = evidence.Claim(
        text="The trial enrolled 120 adults over eight weeks.",
        subject="s",
        source_ids=[source.id],
        attributed_source_ids=[source.id],
        study={"design": "RCT", "n": 120, "weeks": 8},
    )
    led = evidence.Ledger(tmp_path / "evidence")
    led.add_source(source)
    led.add_claim(claim)
    led.write()

    reloaded = evidence.Ledger(tmp_path / "evidence").load().claim(claim.id)
    assert reloaded.study == claim.study
    assert reloaded.attributed_source_ids == [source.id]


def test_a_claim_with_no_study_writes_none(tmp_path):
    """The common case: `study` is unused, and no key clutters the record."""
    claim = evidence.Claim(text="x", subject="s")
    fields, _ = evidence.parse_front_matter(claim.to_markdown())
    assert "study" not in fields


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
        attributed_source_ids=["source.a", "source.b"],
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


def test_located_from_survives_write_and_load(tmp_path):
    """`record_findings` reads the tag to admit a host no allowlist named."""
    led = evidence.Ledger(tmp_path / "evidence")
    source = led.add_source(
        evidence.SourceDocument(
            title="MAST",
            url="https://arxiv.org/abs/2503.13657",
            subject="exits",
            located_from="knowledge:claim.mast",
        )
    )
    plain = led.add_source(
        evidence.SourceDocument(title="Docs", url="https://docs.claude.com/x", subject="exits")
    )
    assert "located_from" not in plain.to_markdown()
    led.write()

    reloaded = evidence.Ledger(tmp_path / "evidence").load()

    assert reloaded.sources[source.id].located_from == "knowledge:claim.mast"
    assert reloaded.sources[plain.id].located_from == ""


def test_a_hand_edited_non_http_source_url_stops_a_resume(tmp_path):
    """#384: `record_findings` and `apply_verification` guard live ingest, so
    the one path left for a `corpus:`/`knowledge:` key to reach the ledger is a
    hand-edited evidence file. A resume must refuse it, not print it."""
    root = tmp_path / "evidence"
    root.mkdir()
    bad = evidence.SourceDocument(title="Bad", url="corpus:knowledge:claim.x", subject="exits")
    (root / f"{bad.id}.md").write_text(bad.to_markdown(), encoding="utf-8")

    with pytest.raises(RuntimeError, match=re.escape("corpus:knowledge:claim.x")):
        evidence.Ledger(root).load()

    # An https url in the same shape of file still loads.
    good_root = tmp_path / "evidence-good"
    good_root.mkdir()
    good = evidence.SourceDocument(title="Good", url="https://a.example", subject="exits")
    (good_root / f"{good.id}.md").write_text(good.to_markdown(), encoding="utf-8")
    loaded = evidence.Ledger(good_root).load()
    assert loaded.sources[good.id].url == "https://a.example"


def test_metadata_round_trips_through_the_ledger(tmp_path):
    """#470: authors, year, venue, and a title_mismatch note all survive a
    `to_markdown` write and a `load` back, the same way `located_from` does."""
    fetched = evidence.SourceDocument(
        title="The Interplay Between Physical Activity, Protein Consumption, "
        "and Sleep Quality in Muscle Protein Synthesis",
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        subject="creatine",
        authors=["Nakamura K", "Ortiz L"],
        year="2022",
        venue="Journal of Applied Physiology",
        note="title_mismatch: model said 'X'; the record says 'Y'",
    )
    led = evidence.Ledger(tmp_path / "evidence")
    led.add_source(fetched)
    led.write()

    reloaded = evidence.Ledger(tmp_path / "evidence").load().source_for_url(fetched.url)
    assert reloaded.title == fetched.title
    assert reloaded.authors == fetched.authors
    assert str(reloaded.year) == fetched.year
    assert reloaded.venue == fetched.venue
    assert reloaded.note == fetched.note


def test_tier_survives_a_ledger_round_trip(tmp_path):
    """#473: `source_policy.tier_for()`'s answer survives a `to_markdown`
    write and a `load` back, the same way the other metadata fields do."""
    tiered = evidence.SourceDocument(
        title="Position Stand on Creatine Supplementation",
        url="https://a.example/position-stand",
        subject="creatine",
        tier="position_stand_or_guideline",
    )
    led = evidence.Ledger(tmp_path / "evidence")
    led.add_source(tiered)
    led.write()

    reloaded = evidence.Ledger(tmp_path / "evidence").load().source_for_url(tiered.url)
    assert reloaded.tier == "position_stand_or_guideline"
