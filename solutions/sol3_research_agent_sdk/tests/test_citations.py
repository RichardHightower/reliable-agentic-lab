"""One source-number registry for a run, proved end to end (#354).

The defect these cover was silent. Every deterministic row passed: `cited` saw
a marker, `grounded` saw a number matching a local `number` field, and nothing
compared the number in the prose to the number in the bibliography. Asserting
that a citation exists would leave it undetected. These assert that a citation
resolves to the URL it was meant to name.
"""

from __future__ import annotations

import json
from pathlib import Path

import citations
import paper
import pytest
import sections


def test_a_source_keeps_the_number_it_was_first_given(work):
    first = citations.register(work, ["https://a.invalid", "https://b.invalid"])
    assert first == {"https://a.invalid": 1, "https://b.invalid": 2}
    # Section two meets them in the opposite order and finds one more.
    second = citations.register(
        work, ["https://b.invalid", "https://c.invalid", "https://a.invalid"]
    )
    assert second["https://a.invalid"] == 1
    assert second["https://b.invalid"] == 2
    assert second["https://c.invalid"] == 3


def test_a_resume_reads_the_same_numbers_off_disk(work):
    citations.register(work, ["https://a.invalid", "https://b.invalid"])
    # A fresh process, holding nothing in memory.
    assert citations.load(work) == {"https://a.invalid": 1, "https://b.invalid": 2}
    after = citations.register(work, ["https://c.invalid"])
    assert after["https://a.invalid"] == 1, "a resume renumbered a cited source"
    assert after["https://c.invalid"] == 3


def test_an_unreadable_registry_stops_the_run(work):
    citations.register(work, ["https://a.invalid"])
    (Path(work) / ".harness" / citations.FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unreadable"):
        citations.load(work)


def _finding(fid: str, url: str) -> dict:
    return {"id": fid, "claim": f"A claim from {url}.", "source": {"url_or_path": url}}


def test_two_sections_meeting_sources_in_opposite_orders_cite_the_same_numbers(work):
    """The exact shape that produced a wrong bibliography.

    Section one meets A then B. Section two meets B, then a new source C, then
    A again. Without one registry, section two's writer was told to cite B as
    `[1]`, and the paper's `[1]` was A.
    """
    one = [_finding("s1-f1", "https://a.invalid"), _finding("s1-f2", "https://b.invalid")]
    two = [
        _finding("s2-f1", "https://b.invalid"),
        _finding("s2-f2", "https://c.invalid"),
        _finding("s2-f3", "https://a.invalid"),
    ]

    numbers = citations.register(work, [(f["source"]["url_or_path"]) for f in one])
    bound_one = sections._claims_for_writer(one, {}, "s1", numbers)
    numbers = citations.register(work, [(f["source"]["url_or_path"]) for f in two])
    bound_two = sections._claims_for_writer(two, {}, "s2", numbers)

    told = {c["id"]: (c["number"], c["source_url"]) for c in bound_one + bound_two}
    # One number per url, whatever order a section met it in.
    assert told["s1-f1"][0] == told["s2-f3"][0], told
    assert told["s1-f2"][0] == told["s2-f1"][0], told
    assert told["s2-f2"][0] not in (told["s1-f1"][0], told["s1-f2"][0]), told

    # And the bibliography agrees with what each writer was told.
    biblio = {row["number"]: row["url"] for row in citations.bibliography(work)}
    for fid, (number, url) in told.items():
        assert biblio[number] == url, f"{fid} cites [{number}], which the paper gives to {biblio[number]}"


def test_many_claims_from_one_source_share_its_number(work):
    findings = [
        _finding("s1-f1", "https://a.invalid"),
        _finding("s1-f2", "https://a.invalid"),
        _finding("s1-f3", "https://b.invalid"),
    ]
    numbers = citations.register(work, [f["source"]["url_or_path"] for f in findings])
    bound = sections._claims_for_writer(findings, {}, "s1", numbers)
    by_id = {c["id"]: c["number"] for c in bound}
    assert by_id["s1-f1"] == by_id["s1-f2"], by_id
    assert by_id["s1-f3"] != by_id["s1-f1"], by_id


def test_assembly_numbers_the_bibliography_from_the_registry(work):
    """The number in the prose and the number in the reference list, one pass.

    The registry hands out B as 1 and A as 2, because a section cited B first.
    Assembly reads claims in section order, so rebuilding the numbers there
    would give A as 1. The registry has to win, or the paper renumbers a source
    a written section already cited.
    """
    citations.register(work, ["https://b.invalid", "https://a.invalid"])
    claims = [
        {"id": "s1-f1", "text": "From A.", "source_url": "https://a.invalid",
         "section": "s1", "status": "verified"},
        {"id": "s2-f1", "text": "From B.", "source_url": "https://b.invalid",
         "section": "s2", "status": "verified"},
    ]
    planned = {"sections": [{"id": "s1"}, {"id": "s2"}]}
    usable, refs = paper._numbered(claims, planned, work)
    by_url = {r["url"]: r["number"] for r in refs}
    assert by_url["https://b.invalid"] == 1, "assembly renumbered from section order"
    assert by_url["https://a.invalid"] == 2, by_url
    for claim in usable:
        assert claim["number"] == by_url[claim["source_url"]], claim
    # The list a reader sees runs 1, 2, not section order.
    assert [r["number"] for r in refs] == [1, 2]


def test_a_bare_number_never_binds_to_a_finding_id_that_ends_in_it(work):
    """`[1]` is a reference number. It is not a suffix of `s1-1`.

    #342 let an abbreviated id resolve by suffix. A bare number falling through
    that rule would bind a citation to whichever finding happened to end in
    that digit, silently and with `grounded` green.
    """
    import checks  # noqa: PLC0415

    score = checks.section_check(
        "A claim [1]. " + ("word " * 80),
        section={"id": "s1", "heading": "h", "key_questions": [], "word_target": 80,
                 "figures": []},
        findings=[{"id": "s1-1", "number": 7}],
    )
    assert "grounded" in score.signature(), "a bare number matched an id suffix"
