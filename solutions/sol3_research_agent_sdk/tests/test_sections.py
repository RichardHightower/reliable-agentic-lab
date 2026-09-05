"""Section loop: check rows, coverage, gap pass, stall, ledger, context cut."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import checks
import paper
import pytest
import sections
import turns as turns_mod
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


def test_section_check_cited_accepts_a_marker_with_no_hyphen():
    """The researcher named its findings `f1` and `f3b` on one live run.

    A pattern that required a hyphen read that whole section as uncited. The
    id scheme is the researcher's choice and it changes every run, so the row
    accepts any bracketed token and `grounded` decides whether it resolves.
    """
    body = "Python 3.13 shipped [f1]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "f1", "number": 1}],
    )
    assert "cited" not in score.signature()
    assert "grounded" not in score.signature()


def test_section_check_grounded_resolves_an_abbreviated_finding_id():
    """A writer shortens a long id in prose, the way #302's model wrote a bare ULID."""
    body = "Python 3.13 shipped [f14]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "why-prompting-does-not-scale-f14", "number": 1}],
    )
    assert "grounded" not in score.signature()


def test_section_check_grounded_rejects_an_ambiguous_abbreviation():
    body = "Python 3.13 shipped [f14]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[]),
        findings=[{"id": "a-f14", "number": 1}, {"id": "b-f14", "number": 2}],
    )
    assert "grounded" in score.signature()


def test_findings_from_research_names_every_finding_itself():
    """Two id schemes in one section taught the writer to abbreviate the long one."""
    result = {
        "claims": [
            {"id": "f1", "text": "The model named this one."},
            {"text": "The model named nothing here."},
        ]
    }
    out = sections.findings_from_research(result, "s1", "q1")
    assert [f["id"] for f in out] == ["s1-f1", "s1-f2"]


def test_section_check_figures_grades_what_the_writer_was_handed():
    """`diagram` runs after `sections`, so the first pass hands the writer none.

    Grading placement against the outline's plan failed the writer for a
    figure the harness never gave it. A live run escalated on that row.
    """
    body = "A thing is true [1]. " + ("word " * 80)
    section = _section(
        word_target=80,
        key_questions=[],
        figures=[{"name": "mast-failure-taxonomy", "kind": "chart"}],
    )
    handed_none = checks.section_check(
        body, section=section, findings=[{"number": 1}], figures_given=[]
    )
    assert "figures" not in handed_none.signature()

    handed_one = checks.section_check(
        body,
        section=section,
        findings=[{"number": 1}],
        figures_given=[{"name": "mast-failure-taxonomy", "path": "charts/m.png"}],
    )
    assert "figures" in handed_one.signature()


def test_section_check_figures_falls_back_to_the_plan_when_unstated():
    body = "A thing is true [1]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(
            word_target=80, key_questions=[], figures=[{"name": "a-chart"}]
        ),
        findings=[{"number": 1}],
    )
    assert "figures" in score.signature()


def test_coverage_ignores_the_researcher_note_appended_to_a_question():
    """A live run had to reproduce 460 characters of note, ULIDs included.

    The outliner appends its research notes to a key question. `coverage`
    matched the whole string, so the published paper had to carry the corpus
    ULIDs to pass. The writer was shown the same string, complied with an HTML
    comment, and `cited` then failed on the comment.
    """
    question = (
        "What are the five components of a reliable agent loop? "
        "(Already answered by the pack: knowledge:claim.loop.01M0Y8EYDJ and "
        "knowledge:claim.loop.01M0Y8EYDK name the five parts.)"
    )
    body = (
        "What are the five components of a reliable agent loop? "
        "The loop gathers, acts, verifies, remembers, and stops [1]. "
        + ("word " * 80)
    )
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[question]),
        findings=[{"number": 1, "id": "f1"}],
    )
    assert "coverage" not in score.signature(), score.to_dict()["checks"]


def test_coverage_still_fails_a_question_the_section_never_names():
    question = "What stops the loop? (Answered by the pack: knowledge:claim.loop.01M0.)"
    body = "This section is about something else entirely [1]. " + ("word " * 80)
    score = checks.section_check(
        body,
        section=_section(word_target=80, key_questions=[question]),
        findings=[{"number": 1, "id": "f1"}],
    )
    assert "coverage" in score.signature()


def test_question_text_keeps_a_parenthetical_inside_the_question():
    assert (
        checks.question_text("Does the loop (the outer one) stop?")
        == "Does the loop (the outer one) stop?"
    )
    assert checks.question_text("Plain question?") == "Plain question?"
    assert checks.question_text({"text": "From a dict? (a note.)"}) == "From a dict?"


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


def test_the_section_writer_context_is_the_bound_list(work, turns, no_renderer, monkeypatch):
    """assemble_context used to get raw findings. The writer then cited ids
    with no number, and a contradicted claim sat in the blob (#339).

    Recorded at the stage call, not the helper. A test that only calls
    assemble_context stays green when the call site is reverted.
    """
    seen = {}
    original = sections.assemble_context

    def wrap(**kwargs):
        seen["findings"] = kwargs["findings"]
        return original(**kwargs)

    monkeypatch.setattr(sections, "assemble_context", wrap)

    class Mixed(turns):
        def __init__(self):
            super().__init__(
                claims=[
                    {
                        "text": "A thing is true.",
                        "source_url": "https://example.invalid/doc",
                        "quote": "a thing is true",
                    },
                    {
                        "text": "A false thing.",
                        "source_url": "https://example.invalid/x",
                        "quote": "",
                    },
                ]
            )

        def verify(self, claim):
            self.asked.append(("verify", claim))
            if "false" in claim.lower():
                return {
                    "verdict": "contradicts",
                    "source_url": "",
                    "excerpt": "no",
                }
            return {
                "verdict": "supports",
                "source_url": "https://example.invalid/other",
                "excerpt": "a thing is true",
            }

    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Mixed(),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )
    paper.prior_art(run)
    paper.plan(run)
    paper.do_sections(run)

    assert seen.get("findings"), "the section writer must assemble context"
    assert all("number" in row for row in seen["findings"])
    assert all(row.get("status") != "contradicted" for row in seen["findings"])
    assert "A false thing." not in [row.get("text") for row in seen["findings"]]


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

        def _body(self, section):
            # Python must pass, or the judge never runs and this test escalates
            # on a repeated Python signature instead of a repeated verdict.
            named = ". ".join(section.get("key_questions") or ["what failed"])
            target = int(section.get("word_target") or 0)
            return f"{named} [1]. " + ("word " * max(target, 60))

        def write(self, section, claims, figures, notes, path=""):
            self.asked.append(("write", section["id"], notes, path))
            body = self._body(section)
            if self.root is not None and path:
                target = Path(self.root) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
            return body

        def edit_section(self, section, body, verdict, path="", note="", claims=None):
            self.asked.append(("edit_section", section["id"]))
            body = self._body(section)
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
    # The judge must actually have graded. Without this the test passes on a
    # repeated Python signature and stops covering the verdict path.
    assert any(call[0] == "judge_section" for call in run.turns.asked), run.turns.asked


def test_the_section_loop_does_not_demand_a_figure_it_never_handed_over(work, turns):
    """`diagram` runs after `sections`, so `diagrams.json` is absent on pass one.

    The stage must grade placement against what the writer received, not the
    outline's plan. A live run escalated on this row at $11.47.
    """
    recorded = []

    class Recorder(turns):
        def write(self, section, claims, figures, notes, path=""):
            body = "what failed why it failed [1]. " + ("word " * 80)
            if self.root is not None and path:
                target = Path(self.root) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
            return body

        def judge_section(self, section, body, findings, note=""):
            return {"passed": True, "failed_rows": []}

    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=Recorder(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=True,
    )
    paper.prior_art(run)
    paper.plan(run)
    stamped = json.loads((Path(work) / "outline.approved.json").read_text())
    outline = stamped["outline"] if isinstance(stamped.get("outline"), dict) else stamped
    for section in outline["sections"]:
        section["figures"] = [{"name": "a-chart-nobody-drew", "kind": "chart"}]
    (Path(work) / "outline.approved.json").write_text(json.dumps(stamped), encoding="utf-8")
    assert not (Path(work) / "diagrams.json").exists()

    # The stub body fails `coverage` and `length` and the loop gives up on
    # those. This test is about one row, so the escalation is not the subject.
    with contextlib.suppress(Escalate, paper.RunFailed):
        paper.do_sections(run)

    written = list((Path(work) / "knowledge").glob("*/section-check.json"))
    assert written, "the stage never wrote a section check"
    for check_path in written:
        signature = json.loads(check_path.read_text())["signature"]
        assert "figures" not in signature, check_path


# -- the retry loop shows the writer what the gate grades (#347) -------------


def _long_body(words: int = 400) -> str:
    """A body over the old 8000-character prompt ceiling."""
    para = "The harness bounds the loop and the checker reads the artifact [1]. "
    return "\n\n".join(para * 10 for _ in range(words // 40))


def test_whole_does_not_cut_a_body_that_fits():
    body = "one [1].\n\ntwo [1]."
    assert turns_mod.whole(body) == body


def test_whole_cuts_on_a_paragraph_boundary_and_says_what_went():
    body = "\n\n".join(f"paragraph {n} " + "word " * 20 for n in range(200))
    cut = turns_mod.whole(body, limit=500)
    kept = cut.split("\n\n[The section continues")[0]
    assert len(kept) < len(body)
    assert "more characters" in cut
    assert "withheld for length" in cut
    # A whole number of paragraphs, never a sentence cut in half.
    assert all(part in body for part in kept.split("\n\n"))


def test_whole_reads_its_ceiling_at_call_time(monkeypatch):
    """A default argument binds once, and a test that lowers it proves nothing."""
    body = "a" * 100
    assert turns_mod.whole(body) == body
    monkeypatch.setattr(turns_mod, "BODY_PROMPT_CHARS", 10)
    assert "withheld for length" in turns_mod.whole(body)


class _Recorder:
    """Records which turn the section loop reached, and with what."""

    def __init__(self, base, root, judge_passes=True):
        self.base = base
        self.root = root
        self.judge_passes = judge_passes
        self.calls: list[tuple] = []
        self.edit_notes: list[str] = []
        self.judged_bodies: list[str] = []

    def __getattr__(self, name):
        return getattr(self.base, name)

    def write(self, section, claims, figures, notes, path=""):
        self.calls.append(("write", section["id"]))
        body = "what failed why it failed [1]. " + ("word " * 400)
        target = Path(self.root) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return body

    def edit_section(self, section, body, verdict, path="", note="", claims=None):
        self.calls.append(("edit_section", section["id"]))
        self.edit_notes.append(note)
        target = Path(self.root) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return body

    def judge_section(self, section, body, findings, note=""):
        self.calls.append(("judge_section", section["id"]))
        self.judged_bodies.append(body)
        if self.judge_passes:
            return {"passed": True, "failed_rows": []}
        return {"passed": False, "failed_rows": ["depth"], "notes": ["no mechanism"]}


def _loop(work, turns_cls, **kwargs):
    recorder = _Recorder(turns_cls(root=work), work, **kwargs)
    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=recorder,
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
        enforce_research_policy=True,
    )
    paper.prior_art(run)
    paper.plan(run)
    recorder.escalation = ""
    try:
        paper.do_sections(run)
    except (Escalate, paper.RunFailed) as stop:
        recorder.escalation = str(stop)
    return recorder


def test_a_python_only_failure_edits_instead_of_rewriting(work, turns):
    """A full rewrite of an over-long section returns another over-long one."""
    recorder = _loop(work, turns)
    kinds = [c[0] for c in recorder.calls]
    assert kinds[0] == "write", kinds
    assert "edit_section" in kinds, kinds
    assert kinds.count("write") == 1, kinds


def test_the_editor_is_told_the_deterministic_row_it_must_fix(work, turns):
    """`length` never reaches the judge's failed_rows, so the editor never heard it."""
    recorder = _loop(work, turns)
    assert recorder.edit_notes, "the editor never ran"
    assert any("length" in note for note in recorder.edit_notes), recorder.edit_notes
    assert any("words" in note for note in recorder.edit_notes), recorder.edit_notes


def test_the_judge_does_not_grade_a_section_python_already_rejected(work, turns):
    """Python first, model second. The outline gate already holds this rule."""
    recorder = _loop(work, turns)
    assert "judge_section" not in [c[0] for c in recorder.calls], recorder.calls
    # The stall detector now sees Python rows only. It must still escalate on a
    # repeated signature, or skipping the judge would buy an endless loop.
    assert "not converging" in recorder.escalation, recorder.escalation


def test_an_edit_keeps_the_claims_the_offline_writer_cites_with():
    """`edit_section` delegated to `write` with an empty claim list.

    That was harmless while an edit only followed a judge verdict. Editing any
    existing draft makes it the common path, and `OfflineTurns.write` with no
    claims emits blockquote stubs carrying no citation marker.
    """
    import research  # noqa: PLC0415

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "research.json"
    turn = turns_mod.OfflineTurns(backend=research.FixtureBackend(fixture))
    section = {
        "id": "s1",
        "heading": "The problem",
        "key_questions": ["what failed"],
        "figures": [],
    }
    claims = [{"number": 1, "id": "s1-f1", "text": "A thing is true."}]
    edited = turn.edit_section(section, "old body", {"failed_rows": ["length"]}, claims=claims)
    assert "[1]" in edited, edited
    assert "would have answered" not in edited, edited


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