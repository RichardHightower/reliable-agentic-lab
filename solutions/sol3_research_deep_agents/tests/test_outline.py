"""Outline validator, plan lift, approval stamp, --approve exit."""

from __future__ import annotations

import json
from pathlib import Path

import outline as outlines
import paper
import pytest


def sample_section(sid="s1", heading="The problem", **over):
    section = {
        "id": sid,
        "heading": heading,
        "objective": "State it.",
        "abstract": "Two sentences about the problem. A third names the stake.",
        "key_questions": ["what is the problem", "why existing approaches fail"],
        "claims_to_support": ["The problem is structural."],
        "required_evidence": ["a primary specification"],
        "word_target": 400,
        "figures": [],
        "depends_on": [],
        "corpus_refs": [],
    }
    section.update(over)
    return section


def sample_outline(**over):
    drafted = {
        "title": "On a topic",
        "audience": "engineers",
        "thesis": "A thesis.",
        "word_target_total": 400,
        "sections": [sample_section()],
    }
    drafted.update(over)
    return drafted


def test_a_valid_outline_has_no_errors():
    assert outlines.validate(sample_outline()) == []


def test_duplicate_ids_fail():
    drafted = sample_outline(
        word_target_total=800,
        sections=[
            sample_section("s1", word_target=400),
            sample_section("s1", heading="Other", word_target=400),
        ],
    )
    errors = outlines.validate(drafted)
    assert any("duplicated" in item for item in errors)


def test_unknown_corpus_refs_fail():
    drafted = sample_outline(
        sections=[sample_section(corpus_refs=["brain:missing"])],
    )
    errors = outlines.validate(drafted, corpus_keys=["brain:known"])
    assert any("unknown key" in item for item in errors)


def test_plan_lifts_into_the_outline_schema():
    plan = {
        "title": "Exits",
        "audience": "engineers",
        "questions": [
            {"id": "q1", "question": "what three exits", "check": "done then cost"},
            {"id": "q2", "question": "what happens with no exit", "check": "a runtime limit"},
        ],
        "sections": ["Abstract", "Exit conditions", "Limitations", "References"],
        "diagrams": [{"name": "three-exits", "kind": "mermaid", "shows": "the order"}],
        "notes": ["the doctrine is local"],
    }
    drafted = outlines.outline_from_plan(plan, word_target_total=2000)
    assert drafted["title"] == "Exits"
    assert {section["heading"] for section in drafted["sections"]} == {
        "Exit conditions",
        "Limitations",
    }
    assert outlines.validate(drafted, word_target_total=2000) == []
    assert outlines.diagrams(drafted)


def test_approve_stops_before_research(run_dir, stub_renderer):
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir, require_approval=True)
    assert run.run() == 3
    assert (run_dir / "outline.md").exists()
    assert (run_dir / "outline.json").exists()
    assert not (run_dir / "outline.approved.json").exists()
    assert not (run_dir / "whitepaper.md").exists()


def test_resume_stamps_the_approved_outline(run_dir, stub_renderer):
    from conftest import build_run  # noqa: PLC0415

    first = build_run(run_dir, require_approval=True)
    assert first.run() == 3
    second = build_run(run_dir, require_approval=True, resume=True)
    assert second.run() == 0
    stamped = json.loads((run_dir / "outline.approved.json").read_text())
    assert stamped["approved_by"] == "operator"
    assert "sha256" in stamped


def test_offline_run_stamps_the_outline(finished_paper):
    stamped = json.loads((finished_paper / "outline.approved.json").read_text())
    drafted = outlines.load_approved(stamped)
    assert drafted["sections"]
    assert stamped["approved_by"] == "judge"
