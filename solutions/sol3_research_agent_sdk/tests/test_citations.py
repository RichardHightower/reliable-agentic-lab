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

import checks
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


def test_a_reference_a_reader_cannot_open_never_takes_a_number(work):
    """Run 21 printed `corpus:knowledge:claim.x` as bibliography entry 1.

    A number here is a promise the paper will print the url beside it. The
    locator either finds the public copy or drops the finding, so anything else
    arriving here is a hole in that pass.
    """
    for bad in ("corpus:knowledge:claim.x", "not-found"):
        with pytest.raises(RuntimeError, match="reader can open"):
            citations.register(work, [bad])
        assert citations.load(work) == {}, "a rejected url still reached the file"

    # An empty slot is a finding with no source, not a bad citation.
    assert citations.register(work, ["", "https://a.invalid"]) == {"https://a.invalid": 1}


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


def test_numbered_carries_the_fetched_metadata_into_the_reference(work):
    """#470: `_numbered` is the seam that will hand `render_reference` its
    fields once `assemble` is switched to call it. This is what E2 tests
    without touching `assemble`."""
    claims = [
        {
            "id": "s1-f1",
            "text": "A fact.",
            "source_url": "https://a.invalid",
            "section": "s1",
            "status": "verified",
            "title": "The Record's Title",
            "authors": ["Jane Doe"],
            "year": "2020",
            "venue": "A Journal",
        },
    ]
    planned = {"sections": [{"id": "s1"}]}
    _, refs = paper._numbered(claims, planned, work)
    assert refs[0]["title"] == "The Record's Title"
    assert refs[0]["authors"] == ["Jane Doe"]
    assert refs[0]["year"] == "2020"
    assert refs[0]["venue"] == "A Journal"
    assert citations.render_reference(refs[0]) == (
        "Jane Doe (2020). The Record's Title. A Journal. https://a.invalid"
    )


def test_numbered_carries_the_tier_into_the_reference(work):
    """#473: the tier `source_policy.tier_for()` gave a source survives into
    the reference `_numbered` builds, the SDK twin of the ledger round trip."""
    claims = [
        {
            "id": "s1-f1",
            "text": "A fact.",
            "source_url": "https://a.invalid",
            "section": "s1",
            "status": "verified",
            "evidence_tier": "position_stand_or_guideline",
        },
    ]
    planned = {"sections": [{"id": "s1"}]}
    _, refs = paper._numbered(claims, planned, work)
    assert refs[0]["evidence_tier"] == "position_stand_or_guideline"


def test_do_sections_carries_metadata_from_findings_into_claims(work, turns, monkeypatch):
    """#470: the title, authors, year, and venue `metadata.fetch_record` found
    on a finding's source survive `do_sections`'s aggregation into
    `claims.json`, which is what `_numbered` then reads."""
    approved = {"title": "T", "sections": [{"id": "s1", "heading": "One"}]}
    monkeypatch.setattr(paper, "approved_outline", lambda run: approved)
    monkeypatch.setattr(sections, "run_section", lambda run, section: {"section": section["id"]})

    knowledge = Path(work) / "knowledge" / "s1"
    knowledge.mkdir(parents=True)
    (knowledge / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "s1-f1",
                        "claim": "A fact.",
                        "quote": "",
                        "answers_question": "q",
                        "source": {
                            "kind": "web",
                            "url_or_path": "https://a.invalid",
                            "title": "The Record's Title",
                            "authors": ["Jane Doe"],
                            "year": "2020",
                            "venue": "A Journal",
                            "note": "",
                        },
                    }
                ],
                "coverage_gaps": [],
            }
        ),
        encoding="utf-8",
    )

    run = paper.Run(
        topic="t",
        work_dir=work,
        turns=turns(root=work),
        state=paper.State.load_or_new(work, "t"),
    )
    paper.do_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text(encoding="utf-8"))["claims"]
    assert claims[0]["title"] == "The Record's Title"
    assert claims[0]["authors"] == ["Jane Doe"]
    assert claims[0]["year"] == "2020"
    assert claims[0]["venue"] == "A Journal"


def test_do_sections_carries_the_tier_from_findings_into_claims(work, monkeypatch):
    """#473: the SDK record twin of `test_tier_survives_a_ledger_round_trip`.
    A finding's `evidence_tier` survives `do_sections`'s aggregation into
    `claims.json` the same way title, authors, year, and venue already do."""
    approved = {"title": "T", "sections": [{"id": "s1", "heading": "One"}]}
    monkeypatch.setattr(paper, "approved_outline", lambda run: approved)
    monkeypatch.setattr(sections, "run_section", lambda run, section: {"section": section["id"]})

    knowledge = Path(work) / "knowledge" / "s1"
    knowledge.mkdir(parents=True)
    (knowledge / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "s1-f1",
                        "claim": "A fact.",
                        "quote": "",
                        "answers_question": "q",
                        "source": {
                            "kind": "web",
                            "url_or_path": "https://a.invalid",
                            "title": "A Guideline",
                            "note": "",
                            "evidence_tier": "position_stand_or_guideline",
                        },
                    }
                ],
                "coverage_gaps": [],
            }
        ),
        encoding="utf-8",
    )

    run = paper.Run(
        topic="t",
        work_dir=work,
        turns=object(),
        state=paper.State.load_or_new(work, "t"),
    )
    paper.do_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text(encoding="utf-8"))["claims"]
    assert claims[0]["evidence_tier"] == "position_stand_or_guideline"


def test_do_sections_carries_the_via_title_from_a_rebound_finding(work, monkeypatch):
    """#474 item 10: `_apply_follow_result` keeps the review a rebound claim
    came from under `finding["via"]`. `do_sections` is the field's only
    production reader; before this it was written and never read."""
    approved = {"title": "T", "sections": [{"id": "s1", "heading": "One"}]}
    monkeypatch.setattr(paper, "approved_outline", lambda run: approved)
    monkeypatch.setattr(sections, "run_section", lambda run, section: {"section": section["id"]})

    knowledge = Path(work) / "knowledge" / "s1"
    knowledge.mkdir(parents=True)
    (knowledge / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "s1-f1",
                        "claim": "A fact.",
                        "quote": "",
                        "answers_question": "q",
                        "source": {
                            "kind": "web",
                            "url_or_path": "https://a.invalid/primary",
                            "title": "The Primary Trial",
                            "note": "",
                        },
                        "via": {"title": "A Review", "url_or_path": "https://a.invalid/review"},
                    }
                ],
                "coverage_gaps": [],
            }
        ),
        encoding="utf-8",
    )

    run = paper.Run(
        topic="t",
        work_dir=work,
        turns=object(),
        state=paper.State.load_or_new(work, "t"),
    )
    paper.do_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text(encoding="utf-8"))["claims"]
    assert claims[0]["via_title"] == "A Review"


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


# -- the production wiring, not the helpers (#355 review finding 6) -----------


def test_the_whole_pipeline_binds_every_citation_to_its_own_source(work, turns, monkeypatch):
    """`do_sections` to reload to `assemble` to `check`, reading `paper.md`.

    Every helper test in this file calls `_claims_for_writer` or `_numbered`
    directly, so both of these mutations left all 489 tests green:

        bound = _claims_for_writer(findings, verdicts, sid)   # drop `numbers`
        _numbered(claims, planned)                            # drop `run.work_dir`

    The helpers were tested. The wiring was not. This test fails under either.
    """
    import diagrams  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "available", lambda: False)
    seen: list[dict] = []

    a, b, c = "https://a.invalid", "https://b.invalid", "https://c.invalid"
    # Section one meets A then B. Section two meets B, then a new source C,
    # then A. Local numbering would tell section two to cite B as [1], and the
    # paper's [1] is A.
    # `d` is contradicted, so it reserves number 1 and never reaches the paper.
    # The reference list then legitimately starts at 2, and rebuilding the
    # numbers from assembly order would hand A the number the registry gave D.
    d = "https://d.invalid"
    per_section = {
        "s1": [(d, "s1-f0"), (a, "s1-f1"), (b, "s1-f2")],
        "s2": [(b, "s2-f1"), (c, "s2-f2"), (a, "s2-f3")],
    }
    contradicted = {"s1-f0"}

    class Numbered(turns):
        """A writer that cites exactly the numbers it was handed."""

        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            base = super().outline(topic, prior_art, budget, note, brief)
            first = base["sections"][0]
            half = int(first.get("word_target") or 400) // 2
            base["sections"] = [
                {**first, "id": "s1", "heading": "One", "word_target": half},
                {**first, "id": "s2", "heading": "Two", "word_target": half,
                 "depends_on": ["s1"]},
            ]
            return base

        def research_section(self, section, questions, note=""):
            rows = per_section[section["id"]]
            return {
                "findings": [
                    {
                        "id": fid,
                        "claim": f"A claim from {url}.",
                        "quote": "",
                        "answers_question": checks.question_text(questions[0]) if questions else "",
                        "source": {"kind": "web", "url_or_path": url, "tier": 1},
                    }
                    for url, fid in rows
                ],
                "queries": [],
            }

        def write(self, section, claims, figures, notes, path=""):
            seen.append({c["id"]: (c["number"], c["source_url"]) for c in claims})
            named = ". ".join(section.get("key_questions") or ["what failed"])
            cites = " ".join(f"Claim {c['id']} [{c['number']}]." for c in claims)
            body = f"{named} {cites} " + ("word " * max(int(section.get("word_target") or 0), 60))
            target = Path(self.root) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            return body

        def judge_section(self, section, body, findings, note=""):
            return {"passed": True, "failed_rows": []}

        def verify(self, claim):
            if "d.invalid" in claim:
                return {"verdict": "contradicts", "source_url": "", "excerpt": "no"}
            return {"verdict": "supports", "source_url": "", "excerpt": "yes"}

    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Numbered(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=False,
    )
    paper.prior_art(run)
    paper.plan(run)
    paper.do_sections(run)

    # A resume: a second process, holding nothing from the first.
    reloaded = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Numbered(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=False,
    )
    paper.diagram(reloaded)
    paper.assemble(reloaded)

    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    biblio = {}
    for line in body.splitlines():
        parts = line.split(". ", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            biblio[int(parts[0])] = parts[1].strip()
    assert biblio, body

    registry = citations.load(work)
    assert registry, "the run wrote no registry"

    # Every marker in the paper resolves to the source its claim came from.
    import re  # noqa: PLC0415

    assert registry[d] < registry[a], "the contradicted source did not take a number first"
    assert d not in biblio.values(), "a contradicted source reached the reference list"

    checked = 0
    for section_map in seen:
        for cid, (number, url) in section_map.items():
            match = re.search(rf"Claim {re.escape(cid)} \[(\d+)\]", body)
            if not match:
                continue
            printed = int(match.group(1))
            assert printed in biblio, f"{cid} cites [{printed}], absent from the reference list"
            assert biblio[printed] == url, (
                f"{cid} cites [{printed}], which the paper gives to {biblio[printed]}, not {url}"
            )
            assert registry[url] == printed, f"{cid} cites [{printed}], registry says {registry[url]}"
            checked += 1
    assert checked >= 2, f"only {checked} citations reached the paper"

    # Through the final gate, not up to it. The pipeline test stopped at
    # `assemble`, so removing `reference_numbers` from `paper.check` left every
    # citation and section test green.
    reloaded.enforce_research_policy = False
    score = paper.check(reloaded)
    assert "grounded" not in score.get("failing", []), score
    detail = {row["name"]: row for row in score.get("checks", [])}
    assert detail["grounded"]["passed"], detail["grounded"]


def test_a_sparse_reference_list_is_not_read_as_a_fabrication():
    """A contradicted source or a resume leaves a legitimate gap.

    Positional numbering assumed `1..len(sources)`, so with reference 2 alone
    on the page it rejected `[2]` and accepted `[1]`. Wrong twice.
    """
    assert checks.ungrounded_citations("A [2].", ["https://b.invalid"], [2]) == []
    assert checks.ungrounded_citations("A [1].", ["https://b.invalid"], [2]) == ["[1]"]
    # With no map, the old positional rule stands for a caller that has none.
    assert checks.ungrounded_citations("A [1].", ["https://b.invalid"]) == []


def test_the_paper_gate_accepts_a_sparse_reference_list():
    """The `grounded` row inside `check`, not the helper it calls.

    Testing `ungrounded_citations` alone left the `check` call site free to
    keep passing positional numbers.
    """
    body = (
        "# T\n\n## Abstract\n\nAn abstract.\n\n## One\n\n"
        "A grounded claim [2].\n\n## References\n\n2. https://b.invalid\n"
    )
    with_map = checks.check(body, ["https://b.invalid"], reference_numbers=[2])
    assert "grounded" not in with_map.signature(), with_map.to_dict()["checks"]
    ungrounded = checks.check(body.replace("[2]", "[1]"), ["https://b.invalid"],
                              reference_numbers=[2])
    assert "grounded" in ungrounded.signature()


def test_the_pdf_parser_keeps_the_reference_numbers():
    """The parser discarded the label. This half needs no PDF toolchain."""
    import pdf_report  # noqa: PLC0415

    story = pdf_report.markdown_blocks(
        "1. step one\n2. step two\n\n## References\n\n1. https://a.invalid\n"
        "3. https://c.invalid\n"
    )
    assert [b.level for b in story if b.kind == "numbered"] == [1, 2, 1, 3]


def test_the_rendered_pdf_keeps_the_reference_numbers(tmp_path):
    """The renderer, not the parser. A parser-only assertion stayed green.

    Skipped where the PDF toolchain is absent, matching `test_pdf_report.py`.
    The renderer revert is caught wherever the export lane can actually run.
    """
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    import pdf_report  # noqa: PLC0415

    source = tmp_path / "paper.md"
    source.write_text(
        "# T\n\n## Abstract\n\nAn abstract.\n\n## References\n\n"
        "1. https://a.invalid\n3. https://c.invalid\n",
        encoding="utf-8",
    )
    out = tmp_path / "paper.pdf"
    pdf_report.build_pdf(source, out)

    # The delivered PDF, not the parser. Reverting the renderer left a
    # parser-only assertion green.
    from pypdf import PdfReader  # noqa: PLC0415

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(out)).pages)
    assert "3." in text, text
    assert "2. https://c.invalid" not in text, "the renderer renumbered the reference list"


def test_assembly_refuses_a_source_the_registry_never_numbered(work):
    """Falling back for one url gave two sources the same number, silently."""
    citations.register(work, ["https://a.invalid"])
    registry = citations.load(work)
    (Path(work) / ".harness" / citations.FILE).write_text(
        json.dumps({"sources": {"https://a.invalid": 2}}), encoding="utf-8"
    )
    claims = [
        {"id": "s1-f1", "text": "A", "source_url": "https://a.invalid",
         "section": "s1", "status": "verified"},
        {"id": "s1-f2", "text": "B", "source_url": "https://b.invalid",
         "section": "s1", "status": "verified"},
    ]
    with pytest.raises(paper.RunFailed, match="never registered"):
        paper._numbered(claims, {"sections": [{"id": "s1"}]}, work)


def test_a_registry_number_must_be_a_positive_integer(work):
    path = Path(work) / ".harness"
    path.mkdir(parents=True, exist_ok=True)
    for bad in ({"https://a.invalid": True}, {"https://a.invalid": 1.5},
                {"https://a.invalid": 0}, {"https://a.invalid": -1}):
        (path / citations.FILE).write_text(json.dumps({"sources": bad}), encoding="utf-8")
        with pytest.raises(RuntimeError, match="positive integer"):
            citations.load(work)


def test_a_registry_key_must_be_a_url_a_reader_can_open(work):
    """The one path #387 left: a hand-edited file, not the locator or `register`."""
    path = Path(work) / ".harness"
    path.mkdir(parents=True, exist_ok=True)
    (path / citations.FILE).write_text(
        json.dumps({"sources": {"corpus:knowledge:claim.x": 3, "https://a.invalid": 4}}),
        encoding="utf-8",
    )
    import re  # noqa: PLC0415

    with pytest.raises(RuntimeError, match=re.escape("corpus:knowledge:claim.x")):
        citations.load(work)

    # A registry of only http(s) keys still loads.
    (path / citations.FILE).write_text(
        json.dumps({"sources": {"https://a.invalid": 1, "https://b.invalid": 2}}),
        encoding="utf-8",
    )
    assert citations.load(work) == {"https://a.invalid": 1, "https://b.invalid": 2}


def test_assembly_refuses_a_hand_edited_non_http_key(work):
    """The belt named in #384: `assemble` must not print a `corpus:` key.

    #387 closed the locator and `register` paths. The one path left is a
    registry hand-edited after the fact, which `_numbered` reads straight off
    disk via `citations.load`. The run must stop before `paper.md` exists.
    """
    path = Path(work) / ".harness"
    path.mkdir(parents=True, exist_ok=True)
    (path / citations.FILE).write_text(
        json.dumps({"sources": {"corpus:knowledge:claim.x": 3, "https://a.invalid": 4}}),
        encoding="utf-8",
    )
    claims = [
        {"id": "s1-f1", "text": "A", "source_url": "https://a.invalid",
         "section": "s1", "status": "verified"},
    ]
    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=None,
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=False,
    )
    run.write_json("claims.json", {"claims": claims})
    outline = {"title": "T", "sections": [{"id": "s1", "heading": "One"}]}
    run.write_json("outline.approved.json", outline)

    import re  # noqa: PLC0415

    with pytest.raises(RuntimeError, match=re.escape("corpus:knowledge:claim.x")):
        paper.assemble(run)

    assert not run.file("paper.md").exists(), "the run wrote paper.md past a bad registry key"


def test_two_sources_may_not_share_a_number(work):
    path = Path(work) / ".harness"
    path.mkdir(parents=True, exist_ok=True)
    (path / citations.FILE).write_text(
        json.dumps({"sources": {"https://a.invalid": 1, "https://b.invalid": 1}}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="one number to two sources"):
        citations.load(work)


def test_the_pdf_keeps_the_number_the_reference_list_carries():
    """The parser discarded the label and the renderer invented a counter.

    References numbered 1 and 3 became 1 and 2, so every `[3]` in the prose
    pointed at the wrong entry. A numbered list earlier in the paper moved the
    counter too.
    """
    import pdf_report  # noqa: PLC0415

    blocks = pdf_report.markdown_blocks(
        "1. step one\n2. step two\n\n## References\n\n1. https://a.invalid\n"
        "3. https://c.invalid\n"
    )
    labels = [(b.level, b.text) for b in blocks if b.kind == "numbered"]
    assert labels == [
        (1, "step one"),
        (2, "step two"),
        (1, "https://a.invalid"),
        (3, "https://c.invalid"),
    ], labels


# -- render_reference: authors, year, venue, from the record, not the model.
# P3 has not landed `## Glossary` or the `assemble` seam yet, so E2 creates
# `render_reference` fully implemented and exercises it directly. #470


def test_the_reference_block_carries_authors_and_years():
    ref = {
        "url": "https://a.invalid",
        "title": "A Study of Creatine and Muscle Loss",
        "authors": ["Jane Doe", "John Smith"],
        "year": "2020",
        "venue": "Journal of Things",
    }
    assert citations.render_reference(ref) == (
        "Jane Doe, John Smith (2020). A Study of Creatine and Muscle Loss. "
        "Journal of Things. https://a.invalid"
    )


def test_render_reference_falls_back_field_by_field():
    assert citations.render_reference({"url": "https://a.invalid"}) == "https://a.invalid"
    assert citations.render_reference(
        {"url": "https://a.invalid", "title": "A Study"}
    ) == "A Study. https://a.invalid"
    assert citations.render_reference(
        {"url": "https://a.invalid", "title": "A Study", "year": "2020"}
    ) == "(2020). A Study. https://a.invalid"
    # A year with no authors still renders, alone in its own parens.
    assert citations.render_reference(
        {"url": "https://a.invalid", "year": "2020"}
    ) == "(2020). https://a.invalid"
