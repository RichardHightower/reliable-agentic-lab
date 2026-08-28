"""The knowledge bundle. What the run checked and threw out is the record."""

from __future__ import annotations

import re

import rkc


def test_the_self_check_runs():
    """It writes a bundle and validates it against the installed plugin."""
    assert rkc.demo() == 0


def test_a_ulid_uses_crockford_base32():
    """No I, L, O, or U, so an id cannot be misread back to a person."""
    for _ in range(20):
        assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", rkc.ulid())


def test_two_ulids_in_the_same_millisecond_differ():
    assert len({rkc.ulid() for _ in range(200)}) == 200


def test_a_long_slug_keeps_a_digest_so_it_stays_unique():
    first = rkc.slug("a" * 100 + "one")
    second = rkc.slug("a" * 100 + "two")
    assert first != second
    assert len(first) <= 64


def test_a_title_with_a_colon_does_not_break_the_front_matter(tmp_path):
    plan = {
        "sections": [{"id": "s1", "heading": "H: with a colon", "goal": "g"}],
        "questions": [{"id": "q1", "text": "why: because", "section": "s1"}],
    }
    claims = [
        {
            "id": "c1",
            "text": "A claim: with a colon.",
            "source_url": "https://e.invalid",
            "quote": "q",
            "section": "s1",
            "status": "verified",
        }
    ]
    root = tmp_path / "knowledge"
    rkc.write_bundle(
        root,
        topic="a: topic",
        area="an area",
        plan=plan,
        findings=[{"answer": "a", "sources": [{"url": "https://e.invalid", "title": "T: t"}]}],
        claims=claims,
    )
    ok, note = rkc.validate(root)
    assert ok, note


def test_a_contradicted_claim_is_recorded_as_rejected(tmp_path):
    """Losing it means the next run pays to rediscover the same wrong answer."""
    plan = {
        "sections": [{"id": "s1", "heading": "H", "goal": "g"}],
        "questions": [{"id": "q1", "text": "q", "section": "s1"}],
    }
    claims = [
        {
            "id": "c1",
            "text": "Wrong.",
            "source_url": "https://e.invalid",
            "quote": "q",
            "section": "s1",
            "status": "contradicted",
        }
    ]
    root = tmp_path / "knowledge"
    rkc.write_bundle(
        root,
        topic="t",
        area="a",
        plan=plan,
        findings=[{"answer": "a", "sources": [{"url": "https://e.invalid", "title": "T"}]}],
        claims=claims,
    )
    written = list((root / "research" / "claims").glob("*.md"))
    assert len(written) == 1
    assert 'status: "rejected"' in written[0].read_text()


def test_a_verdict_becomes_a_confidence(tmp_path):
    assert rkc.STATUS_FOR["verified"][1] > rkc.STATUS_FOR["disputed"][1]
    assert rkc.STATUS_FOR["disputed"][1] > rkc.STATUS_FOR["unverified"][1]
    assert rkc.STATUS_FOR["unverified"][1] > rkc.STATUS_FOR["contradicted"][1]


def test_validation_without_the_plugin_is_not_a_failure(tmp_path, monkeypatch):
    """A run must not die because an optional tool is missing."""
    monkeypatch.setattr(rkc, "VALIDATOR", tmp_path / "nope.py")
    ok, note = rkc.validate(tmp_path)
    assert ok
    assert "not installed" in note
