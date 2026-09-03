"""Step 3: 2000-word floor, ledger rows, no-new-facts edit."""

from __future__ import annotations

import json
from pathlib import Path

import checks
import paper
import pytest


def test_the_hard_length_floor_is_two_thousand():
    assert checks.MIN_WORDS == 2000
    score = checks.check("The system is fast [1].", ["https://a"], min_words=checks.MIN_WORDS)
    assert "length" in score.signature()


def test_new_claims_names_specifics_the_edit_invented():
    before = "The loop checks done first [1]."
    after = "The loop checks done first. Python 3.13 shipped in 2024 [1]."
    novel = checks.new_claims(before, after)
    assert "3.13" in novel
    assert "2024" in novel
    assert checks.new_claims(before, before) == []


def test_ledger_consistency_fails_on_two_values_for_one_number():
    ledger = {
        "entries": [
            {"section_id": "s1", "numbers": [{"value": "12", "unit": "USD", "measures": "budget"}]},
            {"section_id": "s2", "numbers": [{"value": "40", "unit": "USD", "measures": "budget"}]},
        ]
    }
    issues = checks.ledger_inconsistencies(ledger)
    assert issues
    score = checks.check("A point [1].", ["u"], ledger=ledger)
    assert "ledger_consistency" in score.signature()


def test_ledger_consistency_fails_on_an_unresolved_forward_ref():
    ledger = {
        "entries": [
            {
                "section_id": "s1",
                "terms_defined": [],
                "forward_refs": ["the synthesizer contract"],
            }
        ]
    }
    assert any("forward ref" in item for item in checks.ledger_inconsistencies(ledger))


def test_corpus_marked_fails_when_a_model_brief_is_unlabelled():
    claims = [
        {
            "id": "c1",
            "origin": "corpus",
            "source_kind": "deep_research_brief",
            "source_url": "brain:claim.x",
        }
    ]
    score = checks.check("A point [1].\n\n## References\n\n1. brain:claim.x", ["brain:claim.x"], claims=claims)
    assert "corpus_marked" in score.signature()
    labelled = checks.check(
        "A point [1].\n\n## References\n\n1. brain:claim.x (model-written brief)",
        ["brain:claim.x"],
        claims=claims,
    )
    assert "corpus_marked" not in labelled.signature()


def test_gaps_stated_fails_without_a_limitations_section():
    gaps = [{"question": "how watchdog timers fire"}]
    score = checks.check("## The problem\n\nA point [1].", ["u"], gaps=gaps)
    assert "gaps_stated" in score.signature()
    named = checks.check(
        "## The problem\n\nA point [1].\n\n## Limitations\n\nThis paper did not establish how watchdog timers fire [1].",
        ["u"],
        gaps=gaps,
    )
    assert "gaps_stated" not in named.signature()


def test_edit_paper_reverts_a_specific_the_evidence_does_not_contain(work, turns, no_renderer):
    class Inventor(turns):
        def edit_paper(self, section, body, path=""):
            self.asked.append(("edit_paper", section["id"]))
            invented = body.rstrip() + "\n\nPython 9.9 shipped in 2099 [1].\n"
            if self.root is not None and path:
                target = Path(self.root) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(invented, encoding="utf-8")
            return invented

    sections = Path(work) / "sections"
    sections.mkdir()
    original = "## The problem\n\nThe loop checks done first [1].\n"
    (sections / "s1.md").write_text(original, encoding="utf-8")
    (Path(work) / "outline.approved.json").write_text(
        json.dumps(
            {
                "outline": {
                    "title": "On a topic",
                    "sections": [{"id": "s1", "heading": "The problem", "key_questions": []}],
                }
            }
        ),
        encoding="utf-8",
    )
    (Path(work) / "claims.json").write_text(
        json.dumps({"claims": [{"status": "verified", "source_url": "https://example.invalid/doc", "section": "s1"}]}),
        encoding="utf-8",
    )
    (Path(work) / "sources.json").write_text(
        json.dumps({"findings": [{"answer": "The loop checks done first", "sources": []}]}),
        encoding="utf-8",
    )
    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Inventor(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )
    paper.edit_paper(run)
    after = (sections / "s1.md").read_text(encoding="utf-8")
    assert after == original
    receipt = json.loads((Path(work) / "edit.done.json").read_text())
    assert receipt["reverted"]


def test_demo_profile_targets_two_thousand_words():
    import loop as loop_mod  # noqa: PLC0415

    assert loop_mod.PROFILES["demo"]["word_target_total"] == 2000
    assert loop_mod.PROFILES["paper"]["word_target_total"] == 4000
    assert loop_mod.PROFILES["whitepaper"]["word_target_total"] == 6000


@pytest.fixture
def no_renderer(monkeypatch):
    import diagrams  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "available", lambda: False)
