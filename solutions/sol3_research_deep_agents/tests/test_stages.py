"""Each gate rejects the input it exists to reject."""

from __future__ import annotations

import evidence
import pytest
import stages
from stages import GateFailed


def plan(**overrides):
    base = {
        "title": "T",
        "questions": [
            {
                "id": f"q{i}",
                "subject": f"s{i}",
                "question": f"why {i}?",
                "check": "a URL",
                "important": i == 1,
            }
            for i in range(1, 4)
        ],
        "sections": ["Abstract", "Introduction", "References"],
        "diagrams": [],
    }
    base.update(overrides)
    return base


def ledger_with(n=1, important=True, truth=evidence.CORROBORATED):
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s1"))
    b = led.add_source(evidence.SourceDocument(title="b", url="https://b.example", subject="s1"))
    claims = []
    for i in range(n):
        claim = led.add_claim(
            evidence.Claim(
                text=f"fact {i}", subject="s1", source_ids=[a.id, b.id], important=important
            )
        )
        claim.truth_state = truth
        claims.append(claim)
    led.add_finding(
        evidence.Finding(question="why 1?", subject="s1", claim_ids=[c.id for c in claims])
    )
    return led, claims


# -- json ------------------------------------------------------------------


def test_json_survives_a_fenced_reply():
    assert stages.parse_json('here you go:\n```json\n{"a": 1}\n```\n') == {"a": 1}
    assert stages.parse_json('prose {"a": 1} more prose') == {"a": 1}


def test_a_reply_with_no_json_fails_the_gate():
    with pytest.raises(GateFailed):
        stages.parse_json("no object here")


# -- 1. plan ---------------------------------------------------------------


def test_plan_gate_accepts_a_good_plan():
    stages.plan_gate(plan())


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"questions": []}, "questions"),
        ({"sections": []}, "sections"),
    ],
)
def test_plan_gate_counts(override, fragment):
    with pytest.raises(GateFailed) as exc:
        stages.plan_gate(plan(**override))
    assert fragment in str(exc.value)


def test_a_question_with_no_check_cannot_be_verified():
    bad = plan()
    bad["questions"][0]["check"] = ""
    with pytest.raises(GateFailed) as exc:
        stages.plan_gate(bad)
    assert "no check" in str(exc.value)


def test_a_plan_with_nothing_important_would_verify_nothing():
    bad = plan()
    for question in bad["questions"]:
        question["important"] = False
    with pytest.raises(GateFailed) as exc:
        stages.plan_gate(bad)
    assert "important" in str(exc.value)


def test_normalize_adds_the_sections_every_paper_has():
    """Otherwise the section gate fails at stage 8, four stages too late."""
    out = stages.normalize_plan({"questions": [], "sections": ["Body"]})
    assert out["sections"] == ["Abstract", "Introduction", "Body", "References"]


def test_a_missing_introduction_lands_after_the_abstract():
    """Inserting it at the front would put the introduction first, which is a
    different paper."""
    out = stages.normalize_plan({"questions": [], "sections": ["Abstract", "Body", "References"]})
    assert out["sections"] == ["Abstract", "Introduction", "Body", "References"]


def test_normalize_leaves_a_complete_plan_alone():
    given = ["Abstract", "Introduction", "Method", "Limitations", "References"]
    assert stages.normalize_plan({"questions": [], "sections": list(given)})["sections"] == given


# -- 2. search -------------------------------------------------------------


def test_record_findings_drops_a_claim_with_no_source():
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q", "important": True},
        {"answer": "a", "sources": [], "claims": [{"text": "unsourced"}]},
    )
    assert led.claims == {}


def test_record_findings_ignores_a_fabricated_url():
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {"answer": "a", "sources": [{"title": "t", "url": "not a url"}], "claims": [{"text": "x"}]},
    )
    assert led.sources == {}
    assert led.claims == {}


def test_search_gate_fails_with_no_claims():
    with pytest.raises(GateFailed):
        stages.search_gate(evidence.Ledger("/nonexistent"), plan())


def test_search_gate_fails_when_an_important_question_found_nothing():
    led, _ = ledger_with()
    wide = plan()
    wide["questions"][1]["important"] = True
    with pytest.raises(GateFailed) as exc:
        stages.search_gate(led, wide)
    assert "q2" in str(exc.value)


# -- 3. verify -------------------------------------------------------------


def test_agreement_adds_a_source_and_corroborates():
    led, claims = ledger_with(truth=evidence.PROPOSED)
    counts = stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claims[0].id,
                    "second_source_url": "https://c.example",
                    "corroborate_status": "agreed",
                    "quote": "q",
                }
            ]
        },
    )
    assert claims[0].truth_state == evidence.CORROBORATED
    assert counts["corroborated"] == 1


def test_agreeing_twice_on_the_same_url_does_not_promote():
    """The model can say `agreed` all day. Python counts distinct sources."""
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s"))
    claim = led.add_claim(evidence.Claim(text="x", subject="s", source_ids=[a.id], important=True))
    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claim.id,
                    "second_source_url": "https://a.example",
                    "corroborate_status": "agreed",
                    "quote": "q",
                }
            ]
        },
    )
    assert claim.truth_state == evidence.SINGLE_SOURCE


def test_disagreement_contradicts():
    led, claims = ledger_with(truth=evidence.PROPOSED)
    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claims[0].id,
                    "corroborate_status": "disagreed",
                    "quote": "the docs say otherwise",
                }
            ]
        },
    )
    assert claims[0].truth_state == evidence.CONTRADICTED
    assert not claims[0].usable


def test_verify_gate_fails_on_an_unchecked_important_claim():
    """Silence is not consent. An important claim nobody looked at blocks."""
    led, _ = ledger_with(truth=evidence.PROPOSED)
    with pytest.raises(GateFailed) as exc:
        stages.verify_gate(led)
    assert "never checked" in str(exc.value)


def test_a_contradicted_claim_is_a_result_not_a_gate_failure():
    led, claims = ledger_with(n=2, truth=evidence.CORROBORATED)
    claims[0].truth_state = evidence.CONTRADICTED
    stages.verify_gate(led)


def test_verify_gate_fails_when_nothing_is_usable():
    led, _ = ledger_with(truth=evidence.CONTRADICTED)
    with pytest.raises(GateFailed) as exc:
        stages.verify_gate(led)
    assert "nothing to write" in str(exc.value)


# -- placeholders ----------------------------------------------------------


def test_placeholders_resolve_to_real_claim_ids():
    led, claims = ledger_with(n=2)
    out = stages.resolve_placeholders({"ids": ["*s1*0", "*s1*1"]}, led)
    assert out["ids"] == [claims[0].id, claims[1].id]


def test_a_live_reply_passes_through_untouched():
    led, claims = ledger_with()
    assert stages.resolve_placeholders({"id": claims[0].id}, led)["id"] == claims[0].id


# -- 4. outline ------------------------------------------------------------


def outline(claim_id, heading="Introduction"):
    return {
        "sections": [
            {"heading": "Abstract", "claim_ids": []},
            {"heading": heading, "claim_ids": [claim_id]},
            {"heading": "References", "claim_ids": []},
        ]
    }


def test_outline_gate_accepts_a_bound_outline():
    led, claims = ledger_with()
    stages.outline_gate(outline(claims[0].id), led, plan())


def test_outline_gate_rejects_an_invented_claim_id():
    led, _ = ledger_with()
    with pytest.raises(GateFailed) as exc:
        stages.outline_gate(outline("claim.does-not-exist"), led, plan())
    assert "does not exist" in str(exc.value)


def test_outline_gate_rejects_a_contradicted_claim():
    led, claims = ledger_with()
    claims[0].truth_state = evidence.CONTRADICTED
    with pytest.raises(GateFailed):
        stages.outline_gate(outline(claims[0].id), led, plan())


def test_a_body_section_must_bind_something():
    led, _ = ledger_with()
    empty = {
        "sections": [
            {"heading": "Abstract", "claim_ids": []},
            {"heading": "Introduction", "claim_ids": []},
            {"heading": "References", "claim_ids": []},
        ]
    }
    with pytest.raises(GateFailed) as exc:
        stages.outline_gate(empty, led, plan())
    assert "no claim ids" in str(exc.value)


def test_abstract_and_references_need_no_binding():
    assert stages.UNBOUND_SECTIONS == ("abstract", "references")


# -- 5. diagram ------------------------------------------------------------


def test_diagram_gate_passes_the_complexity_complaint_back():
    complaint = "x.mmd: This diagram has 20 nodes. A figure carries at most 12. Combine."
    with pytest.raises(GateFailed) as exc:
        stages.diagram_gate([], [complaint], [{"name": "x"}])
    assert "Combine" in str(exc.value)
    assert exc.value.signature == ("too_complex",)


def test_diagram_gate_is_quiet_when_nothing_was_planned():
    stages.diagram_gate([], [], [])


def test_a_figure_with_no_alt_text_blocks():
    figure = type("F", (), {"name": "x", "alt": ""})()
    with pytest.raises(GateFailed) as exc:
        stages.diagram_gate([figure], [], [{"name": "x"}])
    assert "no alt text" in str(exc.value)


# -- 6. write --------------------------------------------------------------


def test_numbering_is_stable_and_starts_at_one():
    led, _ = ledger_with()
    index, urls = stages.numbering(led)
    assert urls == ["https://a.example", "https://b.example"]
    assert sorted(index.values()) == [1, 2]


def test_a_single_source_claim_tells_the_writer_to_say_so():
    led, claims = ledger_with()
    claims[0].truth_state = evidence.SINGLE_SOURCE
    index, _ = stages.numbering(led)
    assert "SINGLE SOURCE" in stages.claim_brief(led, claims[0].id, index)


def test_write_gate_rejects_a_citation_the_claims_do_not_support():
    with pytest.raises(GateFailed) as exc:
        stages.write_gate("Introduction", "A fact. [9]", [1, 2])
    assert "[1, 2]" in str(exc.value)


def test_write_gate_rejects_a_section_that_cites_nothing():
    with pytest.raises(GateFailed):
        stages.write_gate("Introduction", "A confident sentence with no source.", [1])


def test_write_gate_rejects_an_empty_section():
    with pytest.raises(GateFailed):
        stages.write_gate("Introduction", "   ", [1])


# -- 7. review -------------------------------------------------------------


def test_review_gate_passes_an_empty_failure_list():
    stages.review_gate({"failed_rows": [], "notes": []})


def test_review_gate_reports_the_rows_and_the_notes():
    with pytest.raises(GateFailed) as exc:
        stages.review_gate({"failed_rows": ["voice"], "notes": ["marketing verb in section 2"]})
    assert "marketing verb" in str(exc.value)
    assert exc.value.signature == ("voice",)


# -- 8. assemble -----------------------------------------------------------


class Figure:
    def __init__(self, name):
        self.name = name
        self.alt = f"A diagram of {name}"
        self.polished = False
        self.svg = type("P", (), {"name": f"{name}.svg"})()

    @property
    def best(self):
        return self.svg


def test_assemble_generates_the_references_from_the_ledger():
    """A generated bibliography cannot cite a source that was never retrieved."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(title="T"), outline(claims[0].id), {"Introduction": "A fact. [1][2]"}, [], led
    )
    assert "## References" in body
    assert "https://a.example" in body
    assert body.count("https://") == 2


def test_assemble_places_a_figure_under_its_section():
    led, claims = ledger_with()
    out = outline(claims[0].id)
    out["sections"][1]["figures"] = ["loop"]
    body = stages.assemble(plan(), out, {"Introduction": "A fact. [1]"}, [Figure("loop")], led)
    assert body.index("A diagram of loop") > body.index("## Introduction")
    assert body.index("A diagram of loop") < body.index("## References")


def test_a_rendered_figure_the_outline_forgot_is_still_placed():
    """It cost a render. Dropping it silently hides that the outline drifted."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(), outline(claims[0].id), {"Introduction": "A fact. [1]"}, [Figure("orphan")], led
    )
    assert "## Figures" in body
    assert "A diagram of orphan" in body


def test_assemble_gate_raises_on_a_failing_paper():
    led, _ = ledger_with()
    with pytest.raises(GateFailed) as exc:
        stages.assemble_gate("# T\n\nno sections, no citations\n", led)
    assert "hard gates" in str(exc.value)
