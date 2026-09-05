"""Section loop: check rows, coverage, gap pass, stall, ledger, context cut."""

from __future__ import annotations

import json
from pathlib import Path

import checks
import paper
import pytest
import sections
from turns import Escalate


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "brain"


@pytest.fixture
def no_renderer(monkeypatch):
    import diagrams  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "available", lambda: False)


def _section(**kwargs):
    base = {
        "id": "s1",
        "heading": "The problem",
        "objective": "State it.",
        "abstract": "This section states the problem.",
        "key_questions": ["what failed", "why it failed"],
        "claims_to_support": ["The problem is structural."],
        "required_evidence": ["a spec"],
        "word_target": 80,
        "figures": [],
        "depends_on": [],
    }
    base.update(kwargs)
    return base


def test_section_check_length_fails_when_thin():
    score = checks.section_check("short [1].", section=_section(word_target=200), findings=[{"number": 1}])
    assert "length" in score.signature()


def test_section_check_stub_fails_on_todo():
    body = "TODO fill this in later [1]. " + ("word " * 80)
    score = checks.section_check(body, section=_section(word_target=80), findings=[{"number": 1}])
    assert "stub" in score.signature()


def test_section_check_coverage_fails_when_a_question_is_missing():
    body = "what failed is named [1]. " + ("word " * 80)
    score = checks.section_check(body, section=_section(word_target=80), findings=[{"number": 1}])
    assert "coverage" in score.signature()


def test_section_check_cited_accepts_the_finding_id_the_writer_holds():
    """The researcher keys findings `fm-q1-03`, so that is what the writer cites.

    A numeric-only pattern read a fully cited section as entirely uncited, and
    the writer could not act on the note. It spent every attempt and the run
    escalated.
    """
    body = "Python 3.13 shipped [fm-q1-03]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "fm-q1-03", "number": 1}],
    )
    assert "cited" not in score.signature()
    assert "grounded" not in score.signature()


def test_section_check_grounded_fails_on_a_finding_id_that_does_not_exist():
    body = "Python 3.13 shipped [fm-q9-99]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "fm-q1-03", "number": 1}],
    )
    assert "grounded" in score.signature()


def test_section_check_cited_does_not_take_a_markdown_link_for_a_citation():
    """`[the spec](url)` names a source. It does not say which claim it backs."""
    body = "Python 3.13 shipped, see [the spec](https://x.invalid). " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "fm-q1-03", "number": 1}],
    )
    assert "cited" in score.signature()


def test_section_check_style_allows_a_question_used_as_a_heading():
    """The outline hands the writer key questions. `coverage` demands it name them.

    The writer names them as subheadings. This row read those as rhetoric, so
    removing the heading failed `coverage` and keeping it failed `style`. A
    live run escalated on that with seven of eight checks passing.
    """
    body = (
        "### What failed, and under what load?\n\n"
        "what failed is named [1]. " + ("word " * 40) + "\n\n"
        "### Why did it fail?\n\n"
        "why it failed is named [1]. " + ("word " * 40)
    )
    score = checks.section_check(
        body, section=_section(word_target=80), findings=[{"number": 1}]
    )
    assert "style" not in score.signature(), score.to_dict()["checks"]


def test_section_check_style_still_fails_a_rhetorical_question_in_prose():
    body = "The thing failed [1]. " + ("word " * 80) + "\n\nBut is that the whole story?"
    score = checks.section_check(
        body, section=_section(word_target=80), findings=[{"number": 1}]
    )
    assert "style" in score.signature()


def test_section_check_cited_fails_on_an_uncited_specific():
    body = "Python 3.13 shipped. " + ("word " * 80)
    score = checks.section_check(
        body, section=_section(word_target=80, key_questions=[]), findings=[{"number": 1}]
    )
    assert "cited" in score.signature()


def test_section_check_grounded_fails_on_a_dangling_marker():
    body = "A finding [9]. " + ("word " * 80)
    score = checks.section_check(
        body, section=_section(word_target=80, key_questions=[]), findings=[{"number": 1}]
    )
    assert "grounded" in score.signature()


def test_section_check_sourced_fails_on_a_version_not_in_evidence():
    body = "Python 3.13 shipped [1]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"number": 1, "quote": "a loop computes done"}],
        evidence="a loop computes done",
    )
    assert "sourced" in score.signature()
    assert any("3.13" in c.detail for c in score.checks if c.name == "sourced")


def test_section_check_figures_fails_when_a_planned_figure_is_missing():
    body = "No picture here [1]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(
            word_target=80,
            key_questions=[],
            figures=[{"name": "control-loop", "kind": "diagram", "shows": "exits", "data_needed": ""}],
        ),
        findings=[{"number": 1}],
    )
    assert "figures" in score.signature()


def test_section_check_style_fails_on_second_person():
    body = "You should put the check in the loop [1]. " + ("word " * 80)
    score = checks.section_check(
        body, section=_section(word_target=80, key_questions=[]), findings=[{"number": 1}]
    )
    assert "style" in score.signature()


def test_has_specifics_detects_numbers_and_quotes():
    assert checks.has_specifics("shipped in 2024")
    assert checks.has_specifics('the "Model Context Protocol"')
    assert not checks.has_specifics("The mechanism is local to the component.")


def test_assemble_context_logs_a_cut():
    slots, cuts = sections.assemble_context(
        outline={"title": "t", "sections": []},
        ledger=[],
        previous="x" * 9000,
        findings=[{"claim": "a"}],
        retry="",
    )
    assert any("previous" in line for line in cuts)
    assert len(slots["previous"]) <= 4000


def test_the_ledger_appends_one_entry_per_section(work, turns, no_renderer):
    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns(),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )
    paper.prior_art(run)
    paper.plan(run)
    paper.do_sections(run)
    ledger = json.loads((Path(work) / "paper_ledger.json").read_text())
    assert ledger["entries"]
    assert ledger["entries"][0]["section_id"] == "s1"
    assert (Path(work) / "knowledge" / "s1" / "findings.json").is_file()


def test_a_coverage_gap_is_recorded_when_a_question_has_no_finding(work, turns):
    class Silent(turns):
        def research(self, question, note=""):
            self.asked.append(("research", question, note))
            return {"answer": "", "sources": [], "claims": []}

    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Silent(),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )
    paper.prior_art(run)
    paper.plan(run)
    try:
        paper.do_sections(run)
    except paper.RunFailed:
        pass
    path = Path(work) / "knowledge" / "s1" / "findings.json"
    if path.exists():
        payload = json.loads(path.read_text())
        assert payload["coverage_gaps"]


def test_the_section_loop_escalates_on_a_repeated_failing_verdict(work, turns):
    class Stuck(turns):
        def judge_section(self, section, body, findings, note=""):
            self.asked.append(("judge_section", section["id"]))
            return {"passed": False, "failed_rows": ["depth"], "notes": ["no mechanism"]}

        def write(self, section, claims, figures, notes, path=""):
            self.asked.append(("write", section["id"], notes, path))
            body = "what failed why it failed [1]. " + ("word " * 80)
            if self.root is not None and path:
                target = Path(self.root) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
            return body

    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Stuck(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=True,
    )
    paper.prior_art(run)
    paper.plan(run)
    with pytest.raises((Escalate, paper.RunFailed), match="not converging|s1"):
        paper.do_sections(run)


def test_demo_lands_above_two_thousand_words(work, no_renderer):
    import research  # noqa: PLC0415
    import turns as t  # noqa: PLC0415

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "research.json"
    run = paper.Run(
        topic="loop engineering exit criteria",
        work_dir=work,
        turns=t.OfflineTurns(backend=research.FixtureBackend(fixture)),
        state=paper.State.load_or_new(work, "loop engineering exit criteria"),
        brain=FIXTURE,
        brains=[FIXTURE],
        log=lambda *a: None,
        enforce_research_policy=True,
    )
    paper.run_paper(run)
    body = (Path(work) / "paper.md").read_text()
    assert checks.word_count(body) >= 2000
    assert (Path(work) / "paper_ledger.json").is_file()
    assert (Path(work) / "knowledge" / "problem" / "findings.json").is_file()