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
