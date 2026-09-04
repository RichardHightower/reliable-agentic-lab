"""Outline validator, plan lift, approval stamp, --approve exit."""

from __future__ import annotations

import json
import pathlib
from pathlib import Path

import outline as outlines
import paper
import pytest
import stages


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


def planned_section(heading, objective, first, second):
    return {
        "heading": heading,
        "objective": objective,
        "abstract": f"Two sentences about {heading.lower()}. A third names the stake.",
        "key_questions": [first, second],
    }


def sample_plan(**over):
    plan = {
        "title": "Exits",
        "audience": "engineers",
        "questions": [
            {"id": "q1", "question": "what three exits", "check": "done then cost"},
            {"id": "q2", "question": "what happens with no exit", "check": "a runtime limit"},
        ],
        "sections": [
            "Abstract",
            planned_section(
                "Exit conditions",
                "Show the three exits, in order, and why the order is that one.",
                "what three exits",
                "what happens with no exit",
            ),
            planned_section(
                "Limitations",
                "Name what this design does not solve.",
                "where the cost estimate stops being accurate",
                "what a green rubric fails to prove",
            ),
            "References",
        ],
        "diagrams": [{"name": "three-exits", "kind": "mermaid", "shows": "the order"}],
        "notes": ["the doctrine is local"],
    }
    plan.update(over)
    return plan


def test_plan_lifts_into_the_outline_schema():
    drafted = outlines.outline_from_plan(sample_plan(), word_target_total=2000)
    assert drafted["title"] == "Exits"
    assert {section["heading"] for section in drafted["sections"]} == {
        "Exit conditions",
        "Limitations",
    }
    assert outlines.validate(drafted, word_target_total=2000) == []
    assert outlines.diagrams(drafted)


# -- the planner writes the section, Python does not invent it --------------
#
# The live plan judge scored 0.35 three times with "Section headings and their
# key_questions/claims are systematically mismatched." Two causes: every
# objective read `Explain <heading>.`, and questions were assigned to headings
# by round robin (#306).


def test_the_planner_objective_survives_the_lift():
    drafted = outlines.outline_from_plan(sample_plan(), word_target_total=2000)
    by_heading = {section["heading"]: section for section in drafted["sections"]}
    assert by_heading["Exit conditions"]["objective"] == (
        "Show the three exits, in order, and why the order is that one."
    )
    assert "Explain Exit conditions." not in [s["objective"] for s in drafted["sections"]]


def test_every_section_keeps_its_own_questions():
    """Round robin gave section two the question that belonged to section one."""
    drafted = outlines.outline_from_plan(sample_plan(), word_target_total=2000)
    by_heading = {section["heading"]: section for section in drafted["sections"]}
    assert by_heading["Exit conditions"]["key_questions"] == [
        "what three exits",
        "what happens with no exit",
    ]
    assert by_heading["Limitations"]["key_questions"] == [
        "where the cost estimate stops being accurate",
        "what a green rubric fails to prove",
    ]


def test_an_objective_that_echoes_its_heading_fails_validation():
    drafted = outlines.outline_from_plan(
        sample_plan(
            sections=[
                planned_section("Exit conditions", "Explain Exit conditions.", "one", "two"),
                planned_section("Limitations", "Explain limitations", "three", "four"),
            ]
        ),
        word_target_total=2000,
    )
    errors = outlines.validate(drafted, word_target_total=2000)
    assert len(errors) == 2
    assert all("restates its heading" in item for item in errors), errors


def test_a_string_section_fails_with_the_missing_field_named():
    """An old plan still parses. It does not crash, and it does not pass."""
    drafted = outlines.outline_from_plan(
        sample_plan(sections=["Abstract", "Exit conditions", "References"]),
        word_target_total=2000,
    )
    errors = outlines.validate(drafted, word_target_total=2000)
    assert any("has no objective" in item for item in errors), errors
    assert any("has no abstract" in item for item in errors), errors
    assert any("key_questions" in item for item in errors), errors


def test_a_plan_with_only_structural_sections_still_lifts():
    drafted = outlines.outline_from_plan(
        sample_plan(sections=["Abstract", "References"]), word_target_total=2000
    )
    assert [section["heading"] for section in drafted["sections"]] == ["The approach"]


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


# -- what the judge is shown -----------------------------------------------
#
# `json.dumps(drafted, indent=2)[:8000]` cut a 9,114 character outline mid-key.
# The judge received malformed JSON ending in `"depends_on": [], "c`, saw 6 of
# 7 sections, and reported the outline as truncated and incomplete. It was
# right, and the harness had done it. Two live runs escalated that way (#323).


def big_outline(count=12):
    sections = []
    for index in range(count):
        section = planned_section(
            f"Section {index}",
            f"Show what changes once a reader understands part {index}.",
            f"what does part {index} do",
            f"what breaks in part {index}",
        )
        section["id"] = f"s{index}"
        section["word_target"] = 200
        section["claims_to_support"] = ["A claim." + "x" * 400]
        section["required_evidence"] = ["a primary specification"]
        section["figures"] = []
        section["depends_on"] = []
        sections.append(section)
    return {
        "title": "On a topic",
        "audience": "engineers",
        "thesis": "A thesis.",
        "word_target_total": 200 * count,
        "sections": sections,
    }


def test_the_judge_sees_the_whole_outline_when_it_fits():
    drafted = sample_outline()
    shown = outlines.for_judge(drafted)
    assert json.loads(shown) == drafted


def test_the_judge_never_sees_malformed_json():
    """The old slice ended mid-key. Nothing could parse what the judge got."""
    drafted = big_outline()
    shown = outlines.for_judge(drafted, limit=2000)
    body = shown[shown.index("{"):]
    assert json.loads(body), "the judge must be able to parse what it grades"


def test_an_oversized_outline_drops_whole_sections_and_says_how_many():
    drafted = big_outline()
    shown = outlines.for_judge(drafted, limit=2000)
    body = json.loads(shown[shown.index("{"):])
    assert len(body["sections"]) < 12
    assert len(body["sections"]) >= 1
    withheld = 12 - len(body["sections"])
    assert f"The last {withheld} are withheld" in shown
    assert "do not fail completeness for the withheld" in shown


def test_the_dropped_sections_come_off_the_end():
    """A judge grades flow. Dropping from the middle would break the order."""
    drafted = big_outline()
    shown = outlines.for_judge(drafted, limit=2500)
    body = json.loads(shown[shown.index("{"):])
    headings = [section["heading"] for section in body["sections"]]
    assert headings == [f"Section {i}" for i in range(len(headings))]


def test_a_single_section_is_never_dropped():
    """One section is the floor. An empty outline tells the judge nothing."""
    shown = outlines.for_judge(big_outline(), limit=10)
    body = json.loads(shown[shown.index("{"):])
    assert len(body["sections"]) == 1


# -- the outline editor -----------------------------------------------------
#
# The planner plans. Sending a failed outline back to it produces a different
# plan with different defects, which is how a loop hovers instead of
# converging. The editor changes only what the judge named. Backfilled from the
# Agent SDK port, where it turned a hovering loop into a falling one.


class EditorRunner(paper.FixtureRunner):
    """Records what the editor was asked, and answers with a narrow repair."""

    def __init__(self, path, *, reply=None, boom=False):
        super().__init__(path)
        self.asked: list[tuple[str, str]] = []
        self.reply = reply
        self.boom = boom

    def ask(self, role, prompt):
        self.asked.append((role, prompt))
        if role != "outline_editor":
            return super().ask(role, prompt)
        if self.boom:
            raise RuntimeError("the editor is unavailable")
        return paper.Reply(text="", data=self.reply, usd=0.25)


def judged_outline(run_dir):
    """One validated outline on disk, as `_approve_outline` leaves it."""
    plan = json.loads((pathlib.Path(run_dir) / "plan.json").read_text())
    return outlines.outline_from_plan(plan)


def failing_verdict():
    return {
        "passed": False,
        "summary": "the outline restates one claim twice",
        "blocking_issues": ["limitations/redundancy: the claim appears in two sections"],
        "actionable_changes": ["limitations.claims_to_support[1]: delete the duplicate"],
    }


def test_the_editor_gets_the_outline_and_the_objections(run_dir, stub_renderer):
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    runner = EditorRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    run.run()
    # `outline.json` holds the writer's schema by the end of a run. The editor
    # is handed the outliner's schema, which is what `outline_from_plan` makes.
    drafted = judged_outline(run_dir)

    runner.reply = drafted
    edited, usd = run._edit_outline(drafted, failing_verdict())

    role, prompt = runner.asked[-1]
    assert role == "outline_editor"
    assert "the claim appears in two sections" in prompt, "the objection must reach it"
    assert "delete the duplicate" in prompt, "the actionable change must too"
    assert "Do not rewrite, reorder, or renumber" in prompt
    assert usd == 0.25
    assert edited == drafted


def test_an_invalid_edit_is_refused_and_the_outline_survives(run_dir, stub_renderer):
    """The outline in hand already validates. Losing it to a bad edit is worse."""
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    runner = EditorRunner(FIXTURES / "replies.json", reply={"sections": "not an array"})
    run = build_run(run_dir, runner=runner)
    run.run()
    drafted = judged_outline(run_dir)

    edited, usd = run._edit_outline(drafted, failing_verdict())
    assert edited is None
    assert usd == 0.25, "the call still cost money and must be counted"


def test_an_editor_that_raises_does_not_lose_the_round(run_dir, stub_renderer):
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    runner = EditorRunner(FIXTURES / "replies.json", boom=True)
    run = build_run(run_dir, runner=runner)
    run.run()
    drafted = judged_outline(run_dir)

    edited, usd = run._edit_outline(drafted, failing_verdict())
    assert edited is None
    assert usd == 0.0


def test_the_editor_holds_no_write_path():
    """Same separation as the judge. It returns JSON; Python writes the file."""
    import roleplan  # noqa: PLC0415

    editor = roleplan.plan(None, "paper")["outline_editor"]
    assert not editor.can_write
    assert "Write" not in editor.tools and "Edit" not in editor.tools


def test_a_rejected_outline_is_edited_before_the_next_attempt(run_dir, stub_renderer):
    """Proof `_approve_outline` calls the editor. Calling it directly proved nothing.

    The offline judge always passes, so a fixture run never reaches this path.
    Removing the call from `_approve_outline` left every other editor test
    green, which is how a stage that stopped calling its helper hides.

    The editor here reads the outline out of its own prompt, which also proves
    the prompt carries the document rather than only the complaints.
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    class RejectingRunner(paper.FixtureRunner):
        def __init__(self, path):
            super().__init__(path)
            self.roles: list[str] = []

        def ask(self, role, prompt):
            self.roles.append(role)
            if role == "outline_judge":
                return paper.Reply(text="", data=failing_verdict(), usd=0.1)
            if role == "outline_editor":
                body = prompt[prompt.index("The outline:") + len("The outline:") :]
                drafted = json.loads(body[body.index("{") : body.rindex("}") + 1])
                drafted["sections"][0]["objective"] = "Repaired by the editor."
                return paper.Reply(text="", data=drafted, usd=0.25)
            return super().ask(role, prompt)

    runner = RejectingRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    run.stage_corpus("")

    with pytest.raises(stages.GateFailed):
        run.stage_plan("")

    assert "outline_editor" in runner.roles, "the judge failed and nobody edited"
    written = json.loads((pathlib.Path(run_dir) / "outline.json").read_text())
    assert written["sections"][0]["objective"] == "Repaired by the editor.", (
        "the repair must be on disk for the next attempt to judge"
    )
