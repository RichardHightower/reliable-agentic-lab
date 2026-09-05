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
