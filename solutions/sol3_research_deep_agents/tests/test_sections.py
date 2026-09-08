"""Section check, context slots, skip, and ledger."""

from __future__ import annotations

import json
from pathlib import Path

import sections


def test_assemble_context_cuts_the_tail_not_the_register():
    slots, cuts = sections.assemble_context(
        outline={"title": "x"},
        ledger=[],
        previous="n" * 9000,
        findings=[{"claim": "c"}],
        retry="",
    )
    assert slots["register"].startswith("Write like a specification")
    assert any("cut previous" in line for line in cuts)
    assert len(slots["previous"]) <= 4000


def test_section_check_fails_a_stub():
    score = sections.section_check("TODO write this later [1]\n")
    assert "stub" in score.signature()


def test_section_check_flags_second_person():
    score = sections.section_check("You should put the bound in the program [1].")
    assert not score.passed
    assert any(c.name == "style" and not c.passed for c in score.checks)


def test_section_check_style_allows_a_question_used_as_a_heading():
    """A heading is a paragraph. The outline hands the writer key questions.

    Removing the heading fails coverage, keeping it failed style. The Agent SDK
    port escalated a live run on the same rule.
    """
    body = "### Why did it fail?\n\nIt failed because of a stated cause [1]."
    score = sections.section_check(body)
    assert not any(c.name == "style" and not c.passed for c in score.checks)


def test_section_check_style_still_flags_a_rhetorical_question_in_prose():
    score = sections.section_check("It failed [1].\n\nBut is that the whole story?")
    assert any(c.name == "style" and not c.passed for c in score.checks)


def _coverage_row(score):
    return next(c for c in score.checks if c.name == "coverage")


def test_a_long_question_needs_a_third_of_its_terms():
    """#510. A judge on PR #508 found the #385 gist question "Which trace
    counts were reported by the MAST taxonomy paper?" scored covered by
    "This paper does not report any of it.", on the single incidental word
    "paper". Scaling the requirement to a third of the question's content
    terms, not a flat floor of two, closes that gap; a nine-term question
    used to need the same two incidental matches a two-term question did.
    """
    mast_question = "Which trace counts were reported by the MAST taxonomy paper?"
    section = {"heading": "One", "key_questions": [mast_question]}

    unrelated = sections.section_check(
        "This paper does not report any of it [1].", section=section
    )
    row = _coverage_row(unrelated)
    assert not row.passed and mast_question in row.detail, row.detail

    covering = sections.section_check(
        "The section names the trace counts and cites the MAST taxonomy directly [1].",
        section=section,
    )
    assert _coverage_row(covering).passed

    long_question = (
        "How does the retry ledger track a stale approval stamp across a "
        "resumed run and an escalation boundary?"
    )
    long_section = {"heading": "One", "key_questions": [long_question]}
    two_terms = sections.section_check(
        "The retry path checks a stamp before it runs again [1].", section=long_section
    )
    row2 = _coverage_row(two_terms)
    assert not row2.passed and long_question in row2.detail, row2.detail

    three_terms = sections.section_check(
        "The retry ledger checks a stamp before an escalation [1].", section=long_section
    )
    assert _coverage_row(three_terms).passed

    # The stop-list growth on its own, isolated from the third-scaling: a
    # question padded with words the old twenty-word list missed (`which`,
    # `were`, `not`, `when`, `was`) has more raw tokens than content terms,
    # and the extra tokens must not count against the body.
    padded_question = "Which claims were not corroborated when the budget was capped?"
    padded_section = {"heading": "One", "key_questions": [padded_question]}
    padded = sections.section_check(
        "The retry budget stayed capped for the whole run [1].", section=padded_section
    )
    assert _coverage_row(padded).passed


def test_a_short_question_still_passes_on_two_terms():
    """#510. The floor of two survives the scaling: a two-term question
    still needs both of its terms, and passes once the body names both.
    """
    section = {"heading": "One", "key_questions": ["What blocks retries?"]}

    one_term = sections.section_check("A stale lock blocks the writer today [1].", section=section)
    assert not _coverage_row(one_term).passed

    both_terms = sections.section_check(
        "A stale lock blocks retries until it clears [1].", section=section
    )
    assert _coverage_row(both_terms).passed


def test_a_question_worded_around_domain_verbs_keeps_its_content_terms():
    """#529 judge finding 4. `paper_check.STE_FUNCTION_WORDS` stops `run`,
    `calls`, `uses`, and `holds` for the noun-stack row; a coverage row
    that inherited the same list scored this question on one leftover
    term, `tool`, easier to satisfy than the old rule's two of seven.
    """
    question = "How many tool calls does a run use before it holds?"
    assert len(sections._terms(question)) >= 4


def test_a_fifteen_term_question_needs_a_third_not_two():
    """#529 judge finding 5. The recorded fixtures top out at six content
    terms per question, so the new threshold never actually raises the bar
    there. This question, built for the test, has fifteen: two incidental
    matches is not a third of them, and five is.
    """
    question = (
        "Which trace counts, retry ledger entries, stale approval stamps, "
        "escalation boundaries, and resumed verifier turns does the "
        "harness report?"
    )
    section = {"heading": "One", "key_questions": [question]}

    two_terms = sections.section_check(
        "The dashboard shows a trace and files a report each night [1].", section=section
    )
    assert not _coverage_row(two_terms).passed

    five_terms = sections.section_check(
        "The dashboard shows a trace and files a report each night. "
        "The ledger records stale stamps at each escalation [1].",
        section=section,
    )
    assert _coverage_row(five_terms).passed


def test_a_safety_section_without_a_position_stand_fails():
    """#473: a safety, dosing, or protocol section must cite every
    position-stand or guideline source it was handed. A section with no such
    source among its own findings passes trivially."""
    section = {"heading": "Dosing and safety", "key_questions": ["what dose is safe"]}
    guideline = [{"id": "s1-f1", "number": 1, "evidence_tier": "position_stand_or_guideline"}]

    missing = sections.section_check(
        "A claim about the safe dose that never names the position stand.",
        section=section,
        findings=guideline,
    )
    assert "guideline_cited" in missing.signature()

    cited = sections.section_check(
        "A claim about the safe dose, per the position stand [1].",
        section=section,
        findings=guideline,
    )
    assert "guideline_cited" not in cited.signature()

    no_guideline_source = sections.section_check(
        "A claim about the safe dose with no guideline source in the ledger.",
        section=section,
        findings=[{"id": "s1-f1", "number": 1, "evidence_tier": "primary_trial"}],
    )
    assert "guideline_cited" not in no_guideline_source.signature()

    off_topic = sections.section_check(
        "A claim about something else entirely that never cites [1].",
        section={"heading": "Background", "key_questions": ["what is the mechanism"]},
        findings=guideline,
    )
    assert "guideline_cited" not in off_topic.signature()


def test_guideline_cited_skips_a_non_numeric_number_rather_than_raising():
    """#473 item 7: every current producer supplies an int, but a truthy,
    non-numeric `number` must not crash the row."""
    section = {"heading": "Dosing and safety", "key_questions": ["what dose is safe"]}
    findings = [{"id": "s1-f1", "number": "not-a-number", "evidence_tier": "position_stand_or_guideline"}]
    score = sections.section_check("A claim about the safe dose.", section=section, findings=findings)
    assert "guideline_cited" not in score.signature()


def test_findings_from_claims_carries_the_tier_from_the_ledger():
    """#473: `evidence_tier` on the finding survives from the ledger's
    `SourceDocument`, which is what wires `guideline_cited` to a real run."""
    import evidence
    from types import SimpleNamespace

    ledger = evidence.Ledger("/nonexistent")
    source = ledger.add_source(
        evidence.SourceDocument(
            title="A Position Stand",
            url="https://a.example/stand",
            subject="s",
            tier="position_stand_or_guideline",
        )
    )
    claim = ledger.add_claim(evidence.Claim(text="The safe dose is 5g.", subject="s", source_ids=[source.id]))
    paper = SimpleNamespace(ledger=ledger)
    section = {"heading": "Dosing and safety", "claim_ids": [claim.id]}

    findings = sections.findings_from_claims(paper, section, {source.id: 1})
    assert findings[0]["evidence_tier"] == "position_stand_or_guideline"


# -- #474: the counter-evidence pass -----------------------------------------


def test_a_generalizing_claim_with_no_counter_search_fails():
    """`counterweighed` names the claim when a generalizing finding carries
    no `counter` state at all. A recorded `hit`, `miss`, or `capped` passes."""
    generalizing = {
        "id": "s1-f1",
        "claim": "Protein alone did not prevent lean-mass loss.",
        "generalizing": True,
    }
    missing = sections.section_check(
        "Protein alone did not prevent lean-mass loss [1].",
        section={"heading": "Findings"},
        findings=[generalizing],
    )
    assert "counterweighed" in missing.signature()

    for state in ("hit", "miss", "capped"):
        checked = sections.section_check(
            "Protein alone did not prevent lean-mass loss [1].",
            section={"heading": "Findings"},
            findings=[{**generalizing, "counter": state}],
        )
        assert "counterweighed" not in checked.signature(), state


def test_findings_from_claims_carries_the_counter_fields_from_the_ledger():
    """#474: `generalizing`, `counter`, and `counterargument_to` survive
    from the ledger's `Claim`, which is what wires `counterweighed` to a
    real run."""
    import evidence
    from types import SimpleNamespace

    ledger = evidence.Ledger("/nonexistent")
    source = ledger.add_source(
        evidence.SourceDocument(title="A Review", url="https://a.example/review", subject="s")
    )
    claim = ledger.add_claim(
        evidence.Claim(
            text="Protein alone did not prevent lean-mass loss.",
            subject="s",
            source_ids=[source.id],
        )
    )
    paper = SimpleNamespace(ledger=ledger)
    section = {"heading": "Findings", "claim_ids": [claim.id]}

    findings = sections.findings_from_claims(paper, section, {source.id: 1})
    assert findings[0]["generalizing"] is True
    assert findings[0]["counter"] == ""
    assert findings[0]["counterargument_to"] == ""

    claim.counter = "miss"
    findings = sections.findings_from_claims(paper, section, {source.id: 1})
    assert findings[0]["counter"] == "miss"

    counter = ledger.add_claim(
        evidence.Claim(
            text="Protein with resistance training preserved lean mass.",
            subject="s",
            source_ids=[source.id],
            counterargument_to=claim.id,
        )
    )
    section["claim_ids"] = [counter.id]
    findings = sections.findings_from_claims(paper, section, {source.id: 1})
    assert findings[0]["counterargument_to"] == claim.id


def test_offline_run_writes_section_files_and_ledger(finished_paper: Path):
    assert (finished_paper / "paper_ledger.json").exists()
    entries = json.loads((finished_paper / "paper_ledger.json").read_text())["entries"]
    assert entries
    assert any((finished_paper / "sections").glob("*.md"))
    assert any((finished_paper / "knowledge").glob("*/findings.json"))


def test_close_section_skips_a_finished_section(run_dir, stub_renderer):
    from conftest import build_run  # noqa: PLC0415

    first = build_run(run_dir)
    assert first.run() == 0
    before = json.loads((run_dir / "paper_ledger.json").read_text())["entries"]
    section = {"heading": "Exit conditions", "claim_ids": [], "purpose": "name the exits"}
    spent = sections.close_section(first, section, "already done [1]")
    assert spent == 0.0
    after = json.loads((run_dir / "paper_ledger.json").read_text())["entries"]
    assert after == before


# -- what the judge and the ledger are shown --------------------------------
#
# Both call sites used `body[:6000]`. In a live run the only section over that
# ceiling was the only one the judge rejected, on depth, objective_met, and
# no_filler, which is how a section cut mid-sentence reads. The ledger call was
# worse: not a gate, so evidence past the cut vanished silently (#324).


def test_a_section_under_the_ceiling_is_passed_through_whole():
    body = "One paragraph.\n\nAnd another."
    assert sections.whole(body) == body


def test_a_long_section_is_cut_on_a_paragraph_boundary():
    body = "First para.\n\n" + "Second para. " * 40 + "\n\nThird para."
    shown = sections.whole(body, limit=200)
    text = shown.split("[The section continues")[0].rstrip()
    assert text.endswith("."), "never cut mid-sentence"
    assert "Second para." not in text or text.startswith("First para.")


def test_a_cut_section_says_how_much_was_withheld():
    body = "First para.\n\n" + "x" * 5000
    shown = sections.whole(body, limit=100)
    assert "withheld for length" in shown
    assert "It is not truncated in the paper" in shown
    assert "Do not fail depth, objective_met, or no_filler" in shown


def test_the_ceiling_is_read_at_call_time(monkeypatch):
    """A default argument binds once. A test lowering it would prove nothing."""
    body = "a" * 500
    monkeypatch.setattr(sections, "BODY_PROMPT_CHARS", 100)
    assert "withheld for length" in sections.whole(body)


def test_the_real_ceiling_clears_a_normal_section():
    """A 7,602 character section failed a live run. It must pass untouched."""
    assert sections.BODY_PROMPT_CHARS > 7602
    assert sections.whole("x" * 7602) == "x" * 7602


def test_the_judge_and_the_ledger_both_receive_the_whole_section(run_dir, stub_renderer):
    """Proof the stage calls `whole`. Testing `whole` alone proved nothing.

    Reverting either call site to `body[:6000]` left the helper tests green.
    A helper test does not catch a stage that stopped calling the helper.
    """
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0

    seen: list[tuple[str, str]] = []
    original = run._ask

    def record(role, prompt):
        seen.append((role, prompt))
        return original(role, prompt)

    run._ask = record
    tail = "The last paragraph carries the load-bearing number, 42 percent. [1]"
    body = "Opening paragraph. [1]\n\n" + ("Filler sentence about loops. " * 400) + "\n\n" + tail
    assert len(body) > 6000, "the body must exceed the old ceiling"

    section = {"heading": "Bounding the loop", "claim_ids": [], "purpose": "bound it"}
    sections.close_section(run, section, body, force=True)

    for role in ("section_judge", "ledger"):
        prompt = next(p for name, p in seen if name == role)
        assert tail in prompt, f"{role} lost the end of the section"
