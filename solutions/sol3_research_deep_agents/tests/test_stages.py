"""Each gate rejects the input it exists to reject."""

from __future__ import annotations

import evidence
import paper
import pytest
import stages
import state
from conftest import build_run
from stages import GateFailed


def plan(**overrides):
    base = {
        "title": "T",
        "questions": [
            {
                "id": f"q{i}",
                "subject": f"s{i}",
                "question": stages.EXIT_DOCTRINE_QUESTION if i == 1 else f"why {i}?",
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


def ledger_with(n=1, important=True, truth=evidence.CORROBORATED, cross_checked=True):
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s1"))
    b = led.add_source(evidence.SourceDocument(title="b", url="https://b.example", subject="s1"))
    claims = []
    for i in range(n):
        claim = led.add_claim(
            evidence.Claim(
                text=f"fact {i}",
                subject="s1",
                source_ids=[a.id, b.id],
                important=important,
                cross_checked=cross_checked,
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


# A shortened stand-in for the recorded #407 truncated outline_editor reply:
# an opening fence and a valid start, then a stop mid-section with no
# balanced close and no closing fence.
TRUNCATED_JSON = (
    '```json\n{\n  "title": "T",\n  "sections": [\n'
    '    {"heading": "A", "figures": [],'
)


def test_parse_json_still_raises_on_a_cut_off_reply():
    """No behavior change here. Only the caller's log line changes (#407)."""
    with pytest.raises(GateFailed):
        stages.parse_json(TRUNCATED_JSON)


def test_reply_was_truncated_flags_an_unbalanced_open_brace():
    assert stages.reply_was_truncated(TRUNCATED_JSON)


def test_reply_was_truncated_leaves_a_non_json_reply_alone():
    assert not stages.reply_was_truncated("sorry, I cannot do that")


def test_reply_was_truncated_leaves_a_complete_reply_alone():
    assert not stages.reply_was_truncated('```json\n{"a": 1}\n```')


def test_reply_was_truncated_ignores_a_brace_inside_a_string_value():
    """A claim's own prose can carry a stray `{`. Only structural braces
    count."""
    complete = '{"title": "T", "abstract": "the loop uses { and } for scope"}'
    assert not stages.reply_was_truncated(complete)


def test_reply_was_truncated_ignores_a_brace_inside_a_complete_fenced_reply():
    complete = '```json\n{"title": "T", "note": "a config like {\\"a\\": 1}"}\n```'
    assert not stages.reply_was_truncated(complete)


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


def test_a_plan_cannot_make_more_than_six_questions_block_the_paper():
    bad = plan()
    bad["questions"].extend(
        {
            "id": f"q{i}",
            "subject": f"s{i}",
            "question": f"why {i}?",
            "check": "an official URL",
            "important": True,
        }
        for i in range(4, 10)
    )
    for question in bad["questions"]:
        question["important"] = True

    with pytest.raises(GateFailed) as exc:
        stages.plan_gate(bad)

    assert "at most 6" in str(exc.value)


def test_a_plan_check_that_names_a_host_is_rejected():
    """The source boundary is Python's allowlist, decided later, never the
    plan. #469"""
    bad = plan()
    bad["questions"][0]["check"] = "a claim cited to arxiv.org"
    with pytest.raises(GateFailed) as exc:
        stages.plan_gate(bad)
    assert "arxiv.org" in str(exc.value)


def test_check_names_host_ignores_an_abbreviation():
    assert stages.check_names_host("a stated mechanism, e.g. a retry budget") == ""
    assert stages.check_names_host("a URL") == ""


def headings(plan):
    return [stages.plan_heading(item) for item in plan["sections"]]


def test_normalize_adds_the_sections_every_paper_has():
    """Otherwise the section gate fails at stage 8, four stages too late."""
    out = stages.normalize_plan({"questions": [], "sections": ["Body"]})
    assert headings(out) == ["Abstract", "Introduction", "Body", "References"]


def test_a_missing_introduction_lands_after_the_abstract():
    """Inserting it at the front would put the introduction first, which is a
    different paper."""
    out = stages.normalize_plan({"questions": [], "sections": ["Abstract", "Body", "References"]})
    assert headings(out) == ["Abstract", "Introduction", "Body", "References"]


def test_normalize_leaves_a_complete_plan_alone():
    given = ["Abstract", "Introduction", "Method", "Limitations", "References"]
    assert headings(stages.normalize_plan({"questions": [], "sections": list(given)})) == given


def test_a_planner_section_object_keeps_its_objective_and_questions():
    """The planner writes these now. Nothing may flatten them back to a heading."""
    written = {
        "heading": "Exit conditions",
        "objective": "Show why a loop with no cost exit runs until the budget is gone.",
        "abstract": "Three exits, in order, and what each one costs to check.",
        "key_questions": ["what are the three exits", "what happens with no cost exit"],
    }
    out = stages.normalize_plan({"questions": [], "sections": [written]})
    kept = [item for item in out["sections"] if item["heading"] == "Exit conditions"][0]
    assert kept == written


def test_the_structural_sections_carry_their_own_objective():
    """Python inserts them, so Python states what they are for."""
    out = stages.normalize_plan({"questions": [], "sections": ["Body"]})
    by_heading = {item["heading"]: item for item in out["sections"]}
    assert by_heading["Abstract"]["objective"] == stages.STRUCTURAL["abstract"]
    assert by_heading["Introduction"]["objective"] == stages.STRUCTURAL["introduction"]
    assert by_heading["References"]["objective"] == stages.STRUCTURAL["references"]


def test_an_old_string_plan_still_parses(): 
    """It parses, and carries no objective. The outline validator names that."""
    out = stages.normalize_plan({"questions": [], "sections": ["Body"]})
    body = [item for item in out["sections"] if item["heading"] == "Body"][0]
    assert body["objective"] == ""


# -- 2. search -------------------------------------------------------------


def test_record_findings_drops_a_claim_with_no_source():
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q", "important": True},
        {"answer": "a", "sources": [], "claims": [{"text": "unsourced"}]},
    )
    assert led.claims == {}


def test_a_retrieval_claim_records_a_gap_not_a_claim():
    """A search miss narrated as a claim is refused; the gap is kept. #469"""
    led = evidence.Ledger("/nonexistent")
    finding = stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [
                {
                    "text": (
                        "No arxiv.org source was found that reports a specific "
                        "quantitative rate."
                    ),
                    "source_urls": ["https://docs.claude.com/x"],
                }
            ],
        },
    )
    assert led.claims == {}
    assert finding.claim_ids == []
    assert finding.gaps and "arxiv.org" in finding.gaps[0]


def test_record_findings_ignores_a_fabricated_url():
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {"answer": "a", "sources": [{"title": "t", "url": "not a url"}], "claims": [{"text": "x"}]},
    )
    assert led.sources == {}
    assert led.claims == {}


# -- 2b. metadata comes from the record, not the model. #470 ---------------


class _FakeBackend:
    name = "perplexity"


def test_record_findings_fetches_metadata_when_a_backend_is_given(monkeypatch):
    def fake_fetch(url, backend, *, model_title=""):
        assert backend is not None
        return {
            "title": "The Record's Actual Title",
            "authors": ["Jane Doe"],
            "year": "2023",
            "venue": "A Journal",
            "note": "",
        }

    monkeypatch.setattr(stages.metadata, "fetch_record", fake_fetch)
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "The Model's Guess", "url": "https://docs.claude.com/x"}],
            "claims": [{"text": "a fact", "source_urls": ["https://docs.claude.com/x"]}],
        },
        backend=_FakeBackend(),
    )
    source = led.source_for_url("https://docs.claude.com/x")
    assert source.title == "The Record's Actual Title"
    assert source.authors == ["Jane Doe"]
    assert source.year == "2023"
    assert source.venue == "A Journal"


def test_record_findings_with_no_backend_keeps_the_model_title():
    """The default. Every existing test above calls `record_findings` this
    way, and none of them may start making a network call."""
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "The Model's Guess", "url": "https://docs.claude.com/x"}],
            "claims": [{"text": "a fact", "source_urls": ["https://docs.claude.com/x"]}],
        },
    )
    assert led.source_for_url("https://docs.claude.com/x").title == "The Model's Guess"


def test_record_findings_fetches_a_url_only_once_per_run(monkeypatch):
    calls = []

    def fake_fetch(url, backend, *, model_title=""):
        calls.append(url)
        return {"title": "Fetched", "authors": [], "year": "", "venue": "", "note": ""}

    monkeypatch.setattr(stages.metadata, "fetch_record", fake_fetch)
    led = evidence.Ledger("/nonexistent")
    for _ in range(2):
        stages.record_findings(
            led,
            {"subject": "s1", "question": "q"},
            {
                "answer": "a",
                "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
                "claims": [{"text": "a fact", "source_urls": ["https://docs.claude.com/x"]}],
            },
            backend=_FakeBackend(),
        )
    assert calls == ["https://docs.claude.com/x"], calls


# -- 2c. attribution: the verifier checks the cited source says the claim. -
# #471


def _fetch_with_text(text):
    def fake_fetch(url, backend, *, model_title=""):
        return {"title": model_title, "authors": [], "year": "", "venue": "", "note": "", "text": text}

    return fake_fetch


def test_a_quote_absent_from_the_source_loses_the_binding(monkeypatch):
    """`attributed()` drops the binding, and the drop is logged as a gap."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        _fetch_with_text("This page discusses guanidinoacetic acid, not creatine monohydrate."),
    )
    led = evidence.Ledger("/nonexistent")
    finding = stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [
                {
                    "text": 'The trial reports "a 42 percent reduction in creatine monohydrate '
                    'clearance", which no source here backs.',
                    "source_urls": ["https://docs.claude.com/x"],
                }
            ],
        },
        backend=_FakeBackend(),
    )
    assert led.claims == {}
    assert any("dropped" in gap for gap in finding.gaps), finding.gaps


def test_two_urls_in_one_reply_stay_single_source(monkeypatch):
    """Corroboration counts attributed bindings, not URLs in one reply.

    Neither source here was fetched (no backend), so both bindings are kept
    unattributed. Two raw source ids from one reply must not read as two
    independent looks.
    """
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [
                {"title": "a", "url": "https://docs.claude.com/a"},
                {"title": "b", "url": "https://docs.claude.com/b"},
            ],
            "claims": [{"text": "a fact", "source_urls": []}],
        },
    )
    claim = next(iter(led.claims.values()))
    assert len(claim.source_ids) == 2
    assert claim.truth_state == evidence.SINGLE_SOURCE
    assert claim.attributed_source_ids == []


def test_a_numeric_unimportant_claim_still_reaches_attribution(monkeypatch):
    """The `important` flag never gates attribution; only `verify_batch`'s
    model turn is capped by it. An unimportant numeric claim whose cited
    source lacks that number still loses its binding.
    """
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        _fetch_with_text("The cohort included far fewer participants than reported elsewhere."),
    )
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q", "important": False},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [
                {
                    "text": "The cohort included 214 participants.",
                    "source_urls": ["https://docs.claude.com/x"],
                }
            ],
        },
        backend=_FakeBackend(),
    )
    assert led.claims == {}, "the miss was checked despite important=False"


def test_a_claim_with_no_attributed_binding_is_dropped_and_logged(monkeypatch):
    """A claim whose only source fails `attributed()` never reaches the
    ledger, and the finding's gaps say why."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        _fetch_with_text("Nothing on this page mentions that number."),
    )
    led = evidence.Ledger("/nonexistent")
    finding = stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [
                {"text": "The response rate was 87 percent.", "source_urls": ["https://docs.claude.com/x"]}
            ],
        },
        backend=_FakeBackend(),
    )
    assert led.claims == {}
    assert any("87 percent" in gap or "dropped" in gap for gap in finding.gaps), finding.gaps


def test_an_unfetched_source_keeps_the_binding_and_notes_it_unattributed():
    """No backend, no fetch, no text: nothing to contradict, so the binding
    survives and the claim says attribution was never checked."""
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [{"text": "A claim with a number, 42.", "source_urls": ["https://docs.claude.com/x"]}],
        },
    )
    claim = next(iter(led.claims.values()))
    assert claim.source_ids, "the binding survived"
    assert claim.note == "unattributed: attribution not checked"


def test_the_sources_own_quote_attributes_the_claim(monkeypatch):
    """#471, finding 3: the needle is the researcher's own quote for this
    specific binding (that source's `quote` field in the reply, carried onto
    `SourceDocument.body`), not a `"..."` substring embedded in the claim's
    own text, which a DA claim rarely carries."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        _fetch_with_text("This position stand reviews creatine monohydrate and lean body mass."),
    )
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [
                {
                    "title": "t",
                    "url": "https://docs.claude.com/x",
                    "quote": "creatine monohydrate and lean body mass",
                }
            ],
            "claims": [
                {"text": "Creatine monohydrate preserves lean body mass.", "source_urls": ["https://docs.claude.com/x"]}
            ],
        },
        backend=_FakeBackend(),
    )
    claim = next(iter(led.claims.values()))
    assert claim.source_ids, "the binding was dropped despite the source's own quote matching"
    assert claim.attributed_source_ids == claim.source_ids


class _MetaFixtureBackend:
    name = "fixture"


def test_a_pubmed_source_with_an_abstract_attributes_a_number(monkeypatch):
    """#471, finding 2: the recorded PubMed fixture carries an efetch-shaped
    abstract, not the rare esummary field. No monkeypatch of `fetch_record`
    itself: the real fixture reader runs."""
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"}],
            "claims": [
                {
                    "text": "The trial enrolled 42 adults.",
                    "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/12345678/"],
                }
            ],
        },
        seed=("pubmed.ncbi.nlm.nih.gov",),
        backend=_MetaFixtureBackend(),
    )
    claim = next(iter(led.claims.values()))
    assert claim.source_ids, "the binding was dropped despite the abstract carrying the number"
    assert claim.attributed_source_ids == claim.source_ids


def test_a_pubmed_source_with_no_abstract_keeps_the_binding_unattributed(tmp_path, monkeypatch):
    """esummary alone, with efetch giving nothing (a fixture recorded before
    #471, or a live efetch failure): the binding survives and says so."""
    no_abstract = tmp_path / "no_abstract.json"
    no_abstract.write_text('{"title": "A Paper", "authors": [], "year": "2020", "venue": "J Test"}')
    monkeypatch.setattr(stages.metadata, "_fixture_path", lambda url: no_abstract)
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://pubmed.ncbi.nlm.nih.gov/11111111/"}],
            "claims": [
                {
                    "text": "The trial enrolled 42 adults.",
                    "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/11111111/"],
                }
            ],
        },
        seed=("pubmed.ncbi.nlm.nih.gov",),
        backend=_MetaFixtureBackend(),
    )
    claim = next(iter(led.claims.values()))
    assert claim.source_ids, "the binding was dropped with nothing to check it against"
    assert claim.note == "unattributed: attribution not checked"


def test_record_findings_carries_the_study_object_onto_the_claim():
    """Unused until #478's study table; `record_findings` only has to keep
    what the researcher reported."""
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "t", "url": "https://docs.claude.com/x"}],
            "claims": [
                {
                    "text": "The trial enrolled 120 adults.",
                    "source_urls": ["https://docs.claude.com/x"],
                    "study": {"design": "RCT", "n": 120},
                }
            ],
        },
    )
    claim = next(iter(led.claims.values()))
    assert claim.study == {"design": "RCT", "n": 120}


def test_not_found_writes_the_queries_into_the_note():
    """Silence is not a result. #471"""
    led = evidence.Ledger("/nonexistent")
    claim = led.add_claim(evidence.Claim(text="x", subject="s", source_ids=["a"], important=True))
    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claim.id,
                    "corroborate_status": "not_found",
                    "queries_used": ["x alternate wording", "x site:example.org"],
                }
            ]
        },
    )
    assert "x alternate wording" in claim.note
    assert "x site:example.org" in claim.note


def test_not_found_with_no_reported_queries_still_names_the_claim():
    """A verifier that reports no queries at all still leaves a real note,
    not a blank one."""
    led = evidence.Ledger("/nonexistent")
    claim = led.add_claim(evidence.Claim(text="creatine preserves lean mass", subject="s"))
    stages.apply_verification(
        led, {"checked": [{"claim_id": claim.id, "corroborate_status": "not_found"}]}
    )
    assert "creatine preserves lean mass" in claim.note


def test_agreed_second_source_fetches_its_metadata(monkeypatch):
    """Folded finding: the verifier's second source used to be titled from
    sixty characters of its own quote, with no metadata fetch, and that
    fragment could reach `references_block`. It now goes through the same
    record as any other source. #471
    """
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "The Real Title of the Second Source",
            "authors": ["A. Author"],
            "year": "2020",
            "venue": "A Journal",
            "note": "",
            "text": "",
            "pubtype": ["Randomized Controlled Trial"],
        },
    )
    led = evidence.Ledger("/nonexistent")
    claim = led.add_claim(evidence.Claim(text="x", subject="s", source_ids=["a"], important=True))
    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claim.id,
                    "second_source_url": "https://c.example",
                    "corroborate_status": "agreed",
                    "quote": "a fragment nobody should render as a title",
                }
            ]
        },
        backend=_FakeBackend(),
    )
    source = led.source_for_url("https://c.example")
    assert source.title == "The Real Title of the Second Source"
    assert source.authors == ["A. Author"]
    assert source.year == "2020"
    assert stages.render_reference(source).startswith("A. Author (2020)")
    # #473: the second source gets a tier the same way any other does.
    assert source.tier == "primary_trial"


# -- 2b. follow the summary to its primary. #473 -----------------------------


def test_a_numeric_preprint_claim_gets_one_follow_turn(monkeypatch):
    """A numeric claim bound only to a preprint is a follow candidate, and a
    hit rebinds it to the primary study."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "A Preprint",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "",
            "category": "cs.AI",
        },
    )
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "A Preprint", "url": "https://docs.claude.com/preprint"}],
            "claims": [
                {
                    "text": "The dose increased 42 percent.",
                    "source_urls": ["https://docs.claude.com/preprint"],
                }
            ],
        },
        backend=_FakeBackend(),
    )
    candidates = stages.claims_needing_a_primary(led)
    assert len(candidates) == 1
    claim = candidates[0]

    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "The Primary Trial",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "the dose increased 42 percent",
            "pubtype": ["Randomized Controlled Trial"],
        },
    )
    hit = stages.apply_follow_result(
        led,
        claim,
        {"found": True, "url": "https://docs.claude.com/primary", "title": "The Primary Trial", "quote": ""},
        backend=_FakeBackend(),
    )
    assert hit
    # Appended, not substituted (item 5): the original preprint stays bound.
    assert len(claim.source_ids) == 2
    rebound = led.source_for_url("https://docs.claude.com/primary")
    assert rebound.id in claim.source_ids
    assert rebound.tier == "primary_trial"
    assert not claim.secondary
    # A rebound claim no longer needs a second follow turn.
    assert stages.claims_needing_a_primary(led) == []


def test_a_rebind_keeps_a_corroborating_secondary_corroborated(monkeypatch):
    """#473 item 5: a claim two secondary sources already corroborated stays
    corroborated after a follow hit, since the primary is appended rather
    than replacing the binding."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "A Preprint",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "the dose increased 42 percent",
            "category": "cs.AI",
        },
    )
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [
                {"title": "Preprint A", "url": "https://docs.claude.com/preprint-a"},
                {"title": "Preprint B", "url": "https://docs.claude.com/preprint-b"},
            ],
            "claims": [
                {
                    "text": "The dose increased 42 percent.",
                    "source_urls": ["https://docs.claude.com/preprint-a", "https://docs.claude.com/preprint-b"],
                }
            ],
        },
        backend=_FakeBackend(),
    )
    claim = next(iter(led.claims.values()))
    assert claim.truth_state == evidence.CORROBORATED, claim.truth_state

    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "The Primary Trial",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "the dose increased 42 percent",
            "pubtype": ["Randomized Controlled Trial"],
        },
    )
    hit = stages.apply_follow_result(
        led,
        claim,
        {"found": True, "url": "https://docs.claude.com/primary", "title": "The Primary Trial", "quote": ""},
        backend=_FakeBackend(),
    )
    assert hit
    assert len(claim.source_ids) == 3
    assert claim.truth_state == evidence.CORROBORATED, claim.truth_state


def test_a_follow_hit_that_is_itself_secondary_does_not_clear_the_caveat(monkeypatch):
    """#473 item 2: a follow turn that answers with another review must not
    clear the caveat. The tier of the source `ledger.source_for_url`
    already holds is consulted the same way a freshly fetched one is."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "A Review",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "",
            "category": "cs.AI",
        },
    )
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "A Review", "url": "https://docs.claude.com/review"}],
            "claims": [
                {"text": "The effect was 20 percent.", "source_urls": ["https://docs.claude.com/review"]}
            ],
        },
        backend=_FakeBackend(),
    )
    claim = stages.claims_needing_a_primary(led)[0]

    # The follow turn names a *different* review, still secondary-tier.
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "Another Review",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "",
            "pubtype": ["Review"],
        },
    )
    hit = stages.apply_follow_result(
        led,
        claim,
        {"found": True, "url": "https://docs.claude.com/another-review", "title": "Another Review", "quote": ""},
        backend=_FakeBackend(),
    )
    assert not hit
    assert claim.secondary
    assert claim.source_ids == [led.source_for_url("https://docs.claude.com/review").id]

    index, _ = stages.numbering(led)
    brief = stages.claim_brief(led, claim.id, index)
    assert "as summarized by" in brief


class _SearchThenVerifyRunner(paper.Runner):
    """Answers the researcher for search and follow, then the verifier.

    Distinguishes the two "researcher" prompts by content, the same way the
    live agent graph is distinguished only by what it was asked, not by a
    separate role name: `_follow_primaries` and `stage_search`'s per-question
    loop both call `_ask("researcher", ...)`.
    """

    name = "scripted"

    def __init__(self):
        self.verify_claim_id: str | None = None

    def ask(self, role, prompt):
        if role == "researcher" and "primary study" in prompt:
            return paper.Reply(data={"found": False, "url": "", "title": "", "quote": ""})
        if role == "researcher":
            return paper.Reply(
                data={
                    "answer": "a",
                    "sources": [{"title": "A Review", "url": "https://docs.claude.com/review"}],
                    "claims": [
                        {
                            "text": "The effect was 20 percent.",
                            "source_urls": ["https://docs.claude.com/review"],
                        }
                    ],
                }
            )
        if role == "verifier":
            return paper.Reply(
                data={
                    "checked": [
                        {
                            "claim_id": self.verify_claim_id,
                            "second_source_url": "",
                            "corroborate_status": "not_found",
                            "quote": "",
                            "queries_used": ["q"],
                        }
                    ]
                }
            )
        return paper.Reply(data={})


def test_a_follow_miss_marks_the_claim_secondary(run_dir, monkeypatch):
    """A miss keeps the finding bound to the review it started with, and the
    brief the writer reads still says "as summarized by [n]" after the
    verify stage runs, the live `STAGE_ORDER` path between the follow and
    the brief. #473 item 1: `apply_verification`'s `not_found` branch
    overwrites `claim.note`, which is why the marker lives in a dedicated
    `claim.secondary` field `apply_verification` never touches."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "A Review",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "",
            "category": "cs.AI",
        },
    )
    runner = _SearchThenVerifyRunner()
    run = build_run(run_dir, runner=runner, loop_doctrine=False)
    run.plan = {
        "title": "T",
        "questions": [{"id": "q1", "subject": "s1", "question": "why?", "check": "a URL", "important": True}],
        "sections": ["Abstract", "Introduction", "References"],
        "diagrams": [],
    }

    run.stage_search()
    claim = next(iter(run.ledger.claims.values()))
    assert claim.secondary

    runner.verify_claim_id = claim.id
    run.stage_verify()

    assert claim.secondary, "apply_verification must never touch this field"
    index, _ = stages.numbering(run.ledger)
    brief = stages.claim_brief(run.ledger, claim.id, index)
    assert "as summarized by" in brief


class _CountingRunner(paper.Runner):
    name = "counting"

    def __init__(self):
        self.prompts: list[str] = []

    def ask(self, role: str, prompt: str) -> paper.Reply:
        self.prompts.append(prompt)
        return paper.Reply(data={"found": False, "url": "", "title": "", "quote": ""})


def _claim_with_tier(ledger: evidence.Ledger, tier: str, text: str) -> evidence.Claim:
    source = ledger.add_source(
        evidence.SourceDocument(
            title="Src", url=f"https://docs.claude.com/{tier}-{len(ledger.sources)}", subject="s", tier=tier
        )
    )
    return ledger.add_claim(evidence.Claim(text=text, subject="s", source_ids=[source.id]))


def test_the_follow_pass_stops_at_the_run_cap(run_dir):
    """Seven candidates, six turns: the run-wide cap, shakiest tier first."""
    run = build_run(run_dir, runner=_CountingRunner())
    logs: list[str] = []
    run.say = logs.append
    for i in range(3):
        _claim_with_tier(run.ledger, "preprint_or_compilation", f"The result changed {10 + i} percent.")
    for i in range(3):
        _claim_with_tier(run.ledger, "narrative_review", f"The rate moved {20 + i} percent.")
    _claim_with_tier(run.ledger, "meta_analysis_or_systematic_review", "The effect was 99 percent.")

    run._follow_primaries()

    assert run.runner.prompts and len(run.runner.prompts) == run.max_follow == 6
    followed = "\n".join(run.runner.prompts)
    assert followed.count("changed 1") == 3
    assert followed.count("moved 2") == 3
    assert "effect was 99" not in followed, "the systematic review is the least shaky, and the one left out"

    assert any("follow" in line and "6/6 used this run" in line for line in logs), logs


def test_a_stage_retry_does_not_exceed_max_follow_in_total(run_dir):
    """#473 item 3: `stage_search` retries a `search_gate` failure by
    re-entering `_follow_primaries` from the top. `self.follow_used`,
    persisted in `state.follow_used`, must keep a second call from getting
    a fresh slice of `max_follow`."""
    run = build_run(run_dir, runner=_CountingRunner())
    for i in range(4):
        _claim_with_tier(run.ledger, "preprint_or_compilation", f"The result changed {10 + i} percent.")

    run._follow_primaries()
    assert len(run.runner.prompts) == 4
    assert run.follow_used == 4
    assert run.state.follow_used == 4

    # A fresh batch of candidates surfaces on the retry, as a re-searched
    # question's new claims would.
    for i in range(4):
        _claim_with_tier(run.ledger, "narrative_review", f"The rate moved {20 + i} percent.")
    run._follow_primaries()

    assert len(run.runner.prompts) == run.max_follow == 6, run.runner.prompts
    assert run.follow_used == 6
    assert run.state.follow_used == 6

    # A resumed run in a new process reads the same total back.
    reloaded = state.PaperState.load_or_create(run.work_dir)
    assert reloaded.follow_used == 6


# -- 2c. the counter-evidence pass. #474 -------------------------------------


def test_a_generalizing_claim_gets_one_counter_turn(run_dir):
    """"protein alone did not prevent lean-mass loss" gets exactly one
    counter turn, and the contrary claim binds with `counterargument_to`."""
    run = build_run(run_dir, runner=_CountingRunner())
    original = evidence.Claim(
        text="Protein alone did not prevent lean-mass loss.", subject="creatine"
    )
    run.ledger.add_claim(original)

    run._counter_evidence()

    assert len(run.runner.prompts) == 1, "exactly one counter turn for the one candidate"
    assert "Protein alone did not prevent lean-mass loss." in run.runner.prompts[0]


def test_a_counter_miss_passes_and_the_brief_says_so(monkeypatch):
    """A miss is appended to the claim's own note, and the writer's brief
    carries "no contrary evidence found in this search"."""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {},
    )
    led = evidence.Ledger("/nonexistent")
    claim = led.add_claim(
        evidence.Claim(text="Protein alone did not prevent lean-mass loss.", subject="creatine")
    )
    hit = stages.apply_counter_result(led, claim, {"found": False}, backend=_FakeBackend())
    assert not hit
    assert stages.counter_checked(led, claim)

    index, _ = stages.numbering(led)
    brief = stages.claim_brief(led, claim.id, index)
    assert "no contrary evidence found in this search" in brief


def test_a_counter_hit_binds_the_contrary_claim_and_the_brief_carries_both(monkeypatch):
    """A hit creates a new claim, `counterargument_to` pointing at the
    original, and the writer's brief for the original names it. #474"""
    monkeypatch.setattr(
        stages.metadata,
        "fetch_record",
        lambda url, backend, *, model_title="": {
            "title": "Longland 2016",
            "authors": [],
            "year": "",
            "venue": "",
            "note": "",
            "text": "protein with resistance training preserved lean mass",
            "pubtype": ["Randomized Controlled Trial"],
        },
    )
    led = evidence.Ledger("/nonexistent")
    claim = led.add_claim(
        evidence.Claim(text="Protein alone did not prevent lean-mass loss.", subject="creatine")
    )
    hit = stages.apply_counter_result(
        led,
        claim,
        {
            "found": True,
            "counter_claim": "Protein with resistance training preserved lean mass (Longland 2016).",
            "url": "https://docs.claude.com/longland",
            "title": "Longland 2016",
            "quote": "protein with resistance training preserved lean mass",
        },
        backend=_FakeBackend(),
    )
    assert hit
    countered = stages.counter_evidence_for(led, claim.id)
    assert countered is not None
    assert countered.counterargument_to == claim.id
    assert not str(claim.note or "").startswith("secondary:")
    assert claim.source_ids == [], "the original claim is not rebound, only evidenced against"

    index, _ = stages.numbering(led)
    brief = stages.claim_brief(led, claim.id, index)
    assert "Contrary evidence" in brief
    assert "Longland 2016" in brief


def test_the_counter_pass_stops_at_the_run_cap(run_dir):
    """Seven generalizing claims, `--max-counter 6`, six turns."""
    run = build_run(run_dir, runner=_CountingRunner())
    logs: list[str] = []
    run.say = logs.append
    for i in range(7):
        run.ledger.add_claim(
            evidence.Claim(text=f"The result never changed by more than {i} percent.", subject="s")
        )

    run._counter_evidence()

    assert run.runner.prompts and len(run.runner.prompts) == run.max_counter == 6
    assert any("counter" in line and "cap 6" in line for line in logs), logs


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
    """#471: corroboration now needs two *attributed* bindings. `ledger_with`
    gives the claim two raw source ids from one reply, which is single-source
    on its own; seed one of them as already attributed (the researcher's
    citation, checked against its fetched text) and the verifier's own
    independently found second source is the one that promotes the claim.
    """
    led, claims = ledger_with(truth=evidence.PROPOSED)
    claims[0].attributed_source_ids = [claims[0].source_ids[0]]
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


def test_a_url_missing_its_scheme_separator_adds_no_source():
    """`httpsdocs.example.com` starts with `http` but is not a url a reader can
    open. The old `url.startswith("http")` let it through, and `Ledger.load`'s
    belt (#384) would then refuse the run's own resume."""
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s"))
    claim = led.add_claim(evidence.Claim(text="x", subject="s", source_ids=[a.id], important=True))
    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claim.id,
                    "second_source_url": "httpsdocs.example.com",
                    "corroborate_status": "agreed",
                    "quote": "q",
                }
            ]
        },
    )
    assert claim.source_ids == [a.id], "a malformed url was added as a source"
    assert "httpsdocs.example.com" not in {src.url for src in led.sources.values()}

    stages.apply_verification(
        led,
        {
            "checked": [
                {
                    "claim_id": claim.id,
                    "second_source_url": "https://c.example",
                    "corroborate_status": "agreed",
                    "quote": "q",
                }
            ]
        },
    )
    assert "https://c.example" in {src.url for src in led.sources.values()}


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


def test_diagram_gate_requires_every_planned_figure():
    figure = type("F", (), {"name": "first", "alt": "first"})()
    with pytest.raises(stages.GateFailed) as raised:
        stages.diagram_gate([figure], ["second.mmd: renderer failed"], [{"name": "first"}, {"name": "second"}])
    assert raised.value.signature == ("missing_figures",)


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


def test_write_gate_rejects_an_uncited_paragraph_in_an_otherwise_cited_section():
    with pytest.raises(GateFailed) as exc:
        stages.write_gate("Introduction", "One fact. [1]\n\nAnother fact.", [1])
    assert exc.value.signature == ("uncited_paragraph",)


def test_uncited_writer_padding_is_dropped_without_inventing_a_citation():
    raw = (
        "Unsupported generic framing with no source.\n\n"
        "AgentExecutor defaults to fifteen iterations. [2][4]\n\n"
        "![A bounded loop](figures/loop_imagen.png)"
    )

    cleaned = stages.drop_uncited_prose(raw)

    assert "Unsupported generic framing" not in cleaned
    assert "AgentExecutor defaults" in cleaned
    assert "[2][4]" in cleaned
    assert "![A bounded loop]" in cleaned
    assert set(stages.CITATION.findall(cleaned)) == {"2", "4"}


def test_an_acronym_is_defined_once_at_its_first_use():
    sections = {
        "Abstract": "Tool calls made through MCP can time out. [1]",
        "Resilience": "Model Context Protocol (MCP) cancellation is explicit. [2]",
        "Checklist": "Define Model Context Protocol (MCP) timeouts. [2]",
    }

    normalized = stages.define_acronym_once(sections, "Model Context Protocol", "MCP")
    body = "\n".join(normalized.values())

    assert normalized["Abstract"].startswith("Tool calls made through Model Context Protocol (MCP)")
    assert body.count("Model Context Protocol (MCP)") == 1


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


def test_review_gate_reads_the_paired_reply_shape():
    """#411: a row and its note travel in one object, so pairing never drifts."""
    with pytest.raises(GateFailed) as exc:
        stages.review_gate(
            {
                "failed_rows": [
                    {"row": "no_filler", "note": "Paragraph two restates the abstract."},
                    {"row": "depth", "note": "No mechanism, only the claim."},
                ],
                "score": 0.4,
            }
        )
    assert "no_filler: Paragraph two restates the abstract." in str(exc.value)
    assert "depth: No mechanism, only the claim." in str(exc.value)
    assert exc.value.signature == ("depth", "no_filler")
    assert exc.value.score == 0.4


def test_review_gate_leaves_the_score_unset_on_the_legacy_shape():
    with pytest.raises(GateFailed) as exc:
        stages.review_gate({"failed_rows": ["voice"], "notes": ["a hook"]})
    assert exc.value.score is None


def test_split_verdict_parses_a_mixed_list_of_rows():
    """A reviewer that names one row in the paired shape and one in the
    legacy shape in the same reply must not crash (#411 follow-up)."""
    rows, notes, score = stages._split_verdict(
        {
            "failed_rows": [{"row": "no_filler", "note": "restates the abstract"}, "voice"],
            "score": 0.5,
        }
    )
    assert rows == ["no_filler", "voice"]
    assert notes == ["restates the abstract", ""]
    assert score == 0.5


def test_split_verdict_treats_a_non_list_failed_rows_as_empty():
    """A schema violation from a live model, not a crash (#411 follow-up)."""
    rows, notes, score = stages._split_verdict({"failed_rows": {"row": "voice"}, "score": 0.4})
    assert rows == []
    assert notes == []
    assert score == 0.4


# -- 8. assemble -----------------------------------------------------------


class Figure:
    def __init__(self, name):
        self.name = name
        self.alt = f"A diagram of {name}"
        self.polished = True
        self.png = type("P", (), {"name": f"{name}_imagen.png"})()

    @property
    def best(self):
        return self.png


def test_figure_block_rejects_any_non_plugin_asset():
    figure = Figure("loop")
    figure.png = type("P", (), {"name": "loop.svg"})()
    with pytest.raises(GateFailed) as exc:
        stages.figure_block(figure)
    assert exc.value.signature == ("figure_asset",)


def test_assemble_generates_the_references_from_the_ledger():
    """A generated bibliography cannot cite a source that was never retrieved."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(title="T"), outline(claims[0].id), {"Introduction": "A fact. [1][2]"}, [], led
    )
    assert "## References" in body
    assert "https://a.example" in body
    assert body.count("https://") == 2


def test_the_reference_block_carries_authors_and_years():
    """#470: "Authors (year). Title. Venue. URL.", falling back field by field."""
    full = evidence.SourceDocument(
        title="A Study",
        url="https://a.example",
        subject="s",
        authors=["Jane Doe", "John Smith"],
        year="2020",
        venue="Journal of Things",
    )
    bare = evidence.SourceDocument(title="", url="https://b.example", subject="s")
    block = stages.references_block(["https://a.example", "https://b.example"], [full, bare])
    assert "1. Jane Doe, John Smith (2020). A Study. Journal of Things. https://a.example" in block
    assert "2. https://b.example" in block


def test_render_reference_falls_back_field_by_field():
    title_only = evidence.SourceDocument(title="Just a Title", url="https://a.example", subject="s")
    assert stages.render_reference(title_only) == "Just a Title. https://a.example"

    nothing = evidence.SourceDocument(title="", url="https://a.example", subject="s")
    assert stages.render_reference(nothing) == "https://a.example"


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


def test_a_term_marker_is_harvested_and_stripped():
    """The writer's `TERM` marker never reaches the reader, and its term
    reaches the glossary assembly writes."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(title="T"),
        outline(claims[0].id),
        {"Introduction": "A fact. [1][2] <!-- TERM: orchestrator: the process that sequences roles -->"},
        [],
        led,
    )
    assert "TERM" not in body
    assert "**orchestrator.** the process that sequences roles" in body


def test_assemble_writes_a_glossary_before_references():
    """Heading order: the last prose section, then Glossary, then References.
    The writer is denied both trailing headings."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(title="T"),
        outline(claims[0].id),
        {"Introduction": "A fact. [1][2] <!-- TERM: orchestrator: the process that sequences roles -->"},
        [],
        led,
    )
    assert body.index("## Introduction") < body.index("## Glossary") < body.index("## References")


def test_no_glossary_heading_when_no_term_was_captured():
    """No marker, no section. A Glossary with zero entries is not written."""
    led, claims = ledger_with()
    body = stages.assemble(
        plan(title="T"), outline(claims[0].id), {"Introduction": "A fact. [1][2]"}, [], led
    )
    assert "## Glossary" not in body


def test_assemble_gate_raises_on_a_failing_paper():
    led, _ = ledger_with()
    with pytest.raises(GateFailed) as exc:
        stages.assemble_gate("# T\n\nno sections, no citations\n", led)
    assert "hard gates" in str(exc.value)


def test_assemble_gate_passes_the_doctrine_flag_through_to_paper_check(monkeypatch):
    """#406: `assemble_gate` decides nothing about the doctrine itself. It is
    only the wire between the run and `paper_check.check`."""
    import paper_check

    led, _ = ledger_with()
    seen = {}

    def fake_check(body, sources, **kwargs):
        seen.update(kwargs)
        return paper_check.PaperScore(checks=[paper_check.Check("stub", True)])

    monkeypatch.setattr(stages.paper_check, "check", fake_check)

    stages.assemble_gate("# T\n\nbody\n", led, loop_doctrine=False)
    assert seen["loop_doctrine"] is False

    stages.assemble_gate("# T\n\nbody\n", led, loop_doctrine=True)
    assert seen["loop_doctrine"] is True


def test_assemble_gate_fails_a_heading_that_pastes_a_key_question(monkeypatch):
    """#463: `assemble_gate` hands its `outline` argument through to
    `paper_check.check`, so `question_heading` can also grade a heading
    against the plan's `key_questions`, not only against a heading ending
    in `?`. The H3 below drops the question mark, so it passes with no
    outline; handed the outline, its text still equals a key question and
    it fails."""
    import paper_check  # noqa: PLC0415

    monkeypatch.setattr(paper_check, "MIN_WORDS", 0)
    monkeypatch.setattr(paper_check, "MIN_SECTION_WORDS", 5)
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(
        evidence.SourceDocument(title="a", url="https://docs.langchain.com/one", subject="exits")
    )
    b = led.add_source(
        evidence.SourceDocument(title="b", url="https://docs.claude.com/two", subject="exits")
    )
    led.add_claim(
        evidence.Claim(
            text="Three exits cover the observed cases.", subject="exits", source_ids=[a.id, b.id]
        )
    )
    body = (
        "# Exit conditions\n\n"
        "## Abstract\n\nA loop without an exit spends until someone notices. [1]\n\n"
        "## Introduction\n\n"
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
        "### What stops the loop from running forever\n\n"
        "A rubric computed in code decides when the loop stops. [1]\n\n"
        "## Limitations\n\nThis paper measures two runtimes only. [2]\n\n"
        "## Next step\n\n"
        "- Evaluate the three exits on a live ticket before adopting them.\n"
        "- Run the fixture with --backend fixture, then again with a live backend.\n"
        "- Compare this port against the sibling runtime on the same topic.\n\n"
        "## References\n\n1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
    )
    outline = {
        "sections": [
            {
                "heading": "Introduction",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }

    assert "question_heading" not in stages.assemble_gate(body, led, loop_doctrine=False).signature()

    with pytest.raises(GateFailed) as exc:
        stages.assemble_gate(body, led, loop_doctrine=False, outline=outline)
    assert "question_heading" in exc.value.signature


# -- the verification cap --------------------------------------------------


def wide_ledger(n):
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s1"))
    for i in range(n):
        led.add_claim(
            evidence.Claim(
                text=f"fact {i}",
                subject="s1",
                source_ids=[a.id],
                important=True,
                confidence=i / n,
            )
        )
    return led


def test_the_verify_list_is_bounded():
    """The verifier searches once per claim, so this list is the size of the
    work. Unbounded, four research questions became 111 verification turns."""
    check, skip = stages.verify_batch(wide_ledger(40))
    assert len(check) == stages.MAX_VERIFY_CLAIMS
    assert len(skip) == 40 - stages.MAX_VERIFY_CLAIMS


def test_the_shakiest_claims_are_checked_first():
    """A cap that took claims in dictionary order would spend the budget
    confirming the facts nobody doubted."""
    check, _ = stages.verify_batch(wide_ledger(40), limit=3)
    assert [claim.text for claim in check] == ["fact 0", "fact 1", "fact 2"]


def test_a_small_ledger_is_not_capped():
    check, skip = stages.verify_batch(wide_ledger(4))
    assert len(check) == 4
    assert skip == []


def test_a_claim_past_the_cap_says_so():
    """Silence would read as a pass."""
    _, skip = stages.verify_batch(wide_ledger(20), limit=2)
    stages.note_uncrosschecked(skip)
    assert all("Not cross-checked" in claim.note for claim in skip)
    assert all(claim.cross_checked is False for claim in skip)


def test_the_gate_refuses_a_silent_skip():
    led = wide_ledger(20)
    check, skip = stages.verify_batch(led, limit=2)
    for claim in check:
        claim.cross_checked = True
        evidence.corroborate(claim)
    for claim in skip:
        evidence.corroborate(claim)  # decided, but nobody said it was skipped
    with pytest.raises(GateFailed) as exc:
        stages.verify_gate(led)
    assert exc.value.signature == ("silent_skip",)

    stages.note_uncrosschecked(skip)
    stages.verify_gate(led)


def test_verification_marks_the_claims_it_reported_on():
    led, claims = ledger_with(truth=evidence.PROPOSED, cross_checked=False)
    stages.apply_verification(
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
    assert claims[0].cross_checked is True


def test_a_source_count_is_not_a_second_look():
    """Two URLs inside one search answer are two sources and one look.

    #471: `corroborate()` used to count raw source ids, so this claim came
    back corroborated despite nobody having checked either binding. It now
    stays single-source until each source is actually attributed.
    """
    led = evidence.Ledger("/nonexistent")
    a = led.add_source(evidence.SourceDocument(title="a", url="https://a.example", subject="s"))
    b = led.add_source(evidence.SourceDocument(title="b", url="https://b.example", subject="s"))
    claim = led.add_claim(
        evidence.Claim(text="x", subject="s", source_ids=[a.id, b.id], important=True)
    )
    evidence.corroborate(claim)
    assert claim.truth_state == evidence.SINGLE_SOURCE
    assert claim.cross_checked is False
    assert led.unchecked() == [claim]
def test_plan_requires_the_repo_exit_order_question_first():
    plan = {
        "questions": [
            {"id": "q1", "question": stages.EXIT_DOCTRINE_QUESTION, "check": "the repo source", "important": True},
            {"id": "q2", "question": "A second question", "check": "a source"},
            {"id": "q3", "question": "A third question", "check": "a source"},
        ],
        "sections": ["Abstract"],
        "diagrams": [],
    }
    stages.plan_gate(plan)
    plan["questions"][0]["question"] = "Which exit happens first?"
    with pytest.raises(stages.GateFailed, match="first question"):
        stages.plan_gate(plan)


def test_a_plan_for_any_other_topic_does_not_need_the_doctrine_question():
    """#406: the doctrine was the seminar's own topic, bound as a Python
    constant. Off, a plan for a topic that has nothing to do with this repo
    carries no forced first question and no section about it."""
    creatine_plan = {
        "title": "Creatine supplementation for preventing muscle loss during a calorie deficit",
        "questions": [
            {
                "id": "q1",
                "question": "What dosing protocol saturates intramuscular phosphocreatine?",
                "check": "a loading and maintenance dose with a citation",
                "important": True,
            },
            {"id": "q2", "question": "What percentage of lean mass is typically lost in a deficit?", "check": "a study"},
            {"id": "q3", "question": "What RCTs measured lean mass retention with creatine?", "check": "a named RCT"},
        ],
        "sections": [
            {
                "heading": "Mechanism",
                "objective": "Explain phosphocreatine buffering.",
                "abstract": "Creatine raises intramuscular phosphocreatine.",
                "key_questions": ["what dosing protocol saturates intramuscular phosphocreatine"],
            },
        ],
        "diagrams": [],
    }
    stages.plan_gate(creatine_plan, loop_doctrine=False)  # must not raise

    normalized = stages.normalize_plan(dict(creatine_plan))
    doctrine_words = ("exit", "cost", "max turns")
    for section in normalized["sections"]:
        heading = section.get("heading", "").lower()
        questions = " ".join(section.get("key_questions") or []).lower()
        assert not any(word in heading for word in doctrine_words), section
        assert not any(word in questions for word in doctrine_words), section

    # On, the same plan is still held to the doctrine, unchanged from before
    # the flag existed.
    with pytest.raises(stages.GateFailed, match="first question"):
        stages.plan_gate(creatine_plan, loop_doctrine=True)


def test_review_gate_never_attaches_a_note_to_the_wrong_row():
    """This string becomes the writer's revision instruction.

    A live run stalled with `scope_honest` labelled "evidence_matches is now
    fixed": one extra note shifted every pairing after it, the real defect was
    described to nobody, and the row failed again (#326).
    """
    with pytest.raises(stages.GateFailed) as exc:
        stages.review_gate(
            {
                "failed_rows": ["scope_honest"],
                "notes": [
                    "evidence_matches is now fixed",
                    "the scope claim outruns its evidence",
                ],
            }
        )
    message = str(exc.value)
    assert "scope_honest: evidence_matches is now fixed" not in message
    assert "not matched up" in message
    assert "the scope claim outruns its evidence" in message, "no note may be dropped"
    assert exc.value.signature == ("scope_honest",)


def test_review_gate_pairs_when_the_counts_agree():
    with pytest.raises(stages.GateFailed) as exc:
        stages.review_gate(
            {"failed_rows": ["voice", "depth"], "notes": ["a hook", "no mechanism"]}
        )
    assert "voice: a hook" in str(exc.value)
    assert "depth: no mechanism" in str(exc.value)


def test_review_gate_still_reports_rows_with_no_notes():
    with pytest.raises(stages.GateFailed) as exc:
        stages.review_gate({"failed_rows": ["depth"], "notes": []})
    assert "depth" in str(exc.value)
    assert exc.value.signature == ("depth",)


# -- a located cabinet source is admitted, an untagged one is not -----------

LOCATED_URL = "https://arxiv.org/abs/2503.13657"


def _record_one(url, **extra):
    led = evidence.Ledger("/nonexistent")
    stages.record_findings(
        led,
        {"subject": "s1", "question": "q"},
        {
            "answer": "a",
            "sources": [{"title": "MAST", "url": url, **extra}],
            "claims": [{"text": "a fact", "source_urls": [url]}],
        },
    )
    return led


def test_record_findings_admits_a_located_source_off_the_allowlist():
    led = _record_one(LOCATED_URL, located_from="knowledge:claim.x")
    urls = [source.url for source in led.sources.values()]
    assert urls == [LOCATED_URL]
    assert next(iter(led.sources.values())).located_from == "knowledge:claim.x"


def test_record_findings_refuses_the_same_url_without_the_tag():
    """arxiv.org is not on the allowlist. Only the cross-reference exempts it."""
    assert _record_one(LOCATED_URL).sources == {}


def test_a_located_tag_still_needs_an_openable_url():
    assert _record_one("corpus:knowledge:claim.x", located_from="knowledge:claim.x").sources == {}
