"""Which findings came from the cabinet, and which URL may stand for one."""

from __future__ import annotations

import locate
import pytest


# -- admission --------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://arxiv.org/abs/2503.13657",
        "https://www.cnn.com/2025/01/01/story",
    ],
)
def test_admit_keeps_a_read_page_on_any_host(url):
    """Neither host is on `source_policy.SEED_ALLOWLIST`, and that is the point.

    The locator is a cross-reference, not research. The page that carries a
    cabinet source is wherever its publisher put it, and the researcher's
    allowlist was chosen to answer a different question.
    """
    assert locate.admit({"url": url, "supports": True, "excerpt": "x"}) == url


def test_a_reported_miss_is_never_promoted_to_a_citation():
    reply = {"url": "https://arxiv.org/abs/2503.13657", "supports": False, "excerpt": ""}
    assert locate.admit(reply) == ""


@pytest.mark.parametrize(
    "url",
    [
        "ftp://x/y",
        "corpus:knowledge:claim.x",
        "not-found",
        "01M0Y8EYEG6KGA2FDTZEJFKVNS",
        "https://",
        "https://a.invalid/a b",
        'https://a.invalid/a"b',
        "https://a.invalid/a\\b",
    ],
)
def test_admit_refuses_anything_a_reader_cannot_open(url):
    """Run 21 published every one of these shapes as a reference."""
    assert locate.admit({"url": url, "supports": True, "excerpt": "x"}) == ""


# -- is_cabinet -------------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "corpus:knowledge:claim.x",
        "corpus://knowledge:claim.x",
        "knowledge:claim.x",
        "brain:claim.x",
        "corpus:claude.md (research/source-assets/abc/original.md:68-69)",
        "not-found",
        "",
    ],
)
def test_every_run_21_reference_shape_is_a_cabinet_finding(ref):
    assert locate.is_cabinet({"source": {"url_or_path": ref}})


def test_a_live_web_finding_is_not_a_cabinet_finding():
    finding = {"source": {"kind": "web", "url_or_path": "https://docs.langchain.com/x"}}
    assert not locate.is_cabinet(finding)


def test_the_kind_wins_over_a_url_that_looks_public():
    """A corpus hit can carry a URL. It is still a cabinet finding."""
    finding = {"source": {"kind": "corpus", "url_or_path": "https://arxiv.org/x"}}
    assert locate.is_cabinet(finding)


def test_the_origin_field_alone_is_enough():
    finding = {"origin": "corpus", "source": {"url_or_path": "https://arxiv.org/x"}}
    assert locate.is_cabinet(finding)


# -- the query --------------------------------------------------------------


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("corpus://knowledge:claim.x", "knowledge:claim.x"),
        ("corpus:knowledge:claim.x", "knowledge:claim.x"),
        ("knowledge:claim.x", "knowledge:claim.x"),
        ("brain:claim.x", "brain:claim.x"),
    ],
)
def test_normalize_key_strips_only_the_transport_prefix(ref, expected):
    assert locate.normalize_key(ref) == expected


def test_query_for_cuts_the_claim_at_twenty_words():
    """The locator recognizes a document. It does not research the claim."""
    claim = " ".join(f"w{n}" for n in range(50))
    query = locate.query_for(
        {"claim": claim, "source": {"title": "A Paper", "vendor": "Anthropic"}}
    )
    assert query["title"] == "A Paper"
    assert query["vendor"] == "Anthropic"
    assert query["claim_head"].split() == [f"w{n}" for n in range(locate.CLAIM_HEAD_WORDS)]


def test_the_self_check_runs():
    locate.demo()
