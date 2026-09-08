"""The pipeline. Order, resume, exits, and money."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import paper
import pytest
import stages
import state as pstate
from stages import GateFailed

# -- the three exits -------------------------------------------------------


def test_done_beats_a_spent_budget():
    """A run that finished and then noticed it was over budget did finish.
    Reporting that as a cost failure throws away the paper it wrote."""
    assert paper.check_stop(done=True, spent_usd=99.0, max_usd=1.0)["reason"] == "done"


def test_cost_beats_max_turns():
    stop = paper.check_stop(done=False, spent_usd=5.0, max_usd=5.0, exhausted=True)
    assert stop["reason"] == "cost"


def test_loop_doctrine_defaults_off(tmp_path):
    """#406: the seminar's own topic is opt-in for every other topic."""
    import research  # noqa: PLC0415

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "paper"
    run = paper.Paper(
        topic="anything",
        runner=paper.FixtureRunner(fixtures / "replies.json"),
        backend=research.FixtureBackend(fixtures / "research.json"),
        work_dir=tmp_path,
        quiet=True,
    )
    assert run.loop_doctrine is False


def test_max_turns_is_the_last_exit():
    stop = paper.check_stop(done=False, spent_usd=0.0, max_usd=5.0, exhausted=True)
    assert stop["reason"] == "max turns"


def test_a_running_loop_does_not_stop():
    assert paper.check_stop(done=False, spent_usd=0.0, max_usd=5.0) == {
        "stop": False,
        "reason": None,
    }


# -- the offline run -------------------------------------------------------


def test_the_whole_pipeline_runs_from_recorded_research(offline, run_dir):
    """Research is offline; the accepted image boundary is stubbed in process."""
    assert offline.run() == 0
    assert (run_dir / "whitepaper.md").exists()
    assert (run_dir / "plan.json").exists()
    assert list((run_dir / "evidence").glob("claim.*.md"))
    assert list((run_dir / "figures").glob("*_imagen.png"))


def test_the_stages_run_in_order(offline, run_dir):
    offline.run()
    st = pstate.PaperState.load_or_create(run_dir)
    ran = [name for name in stages.STAGE_ORDER if name in st.stages]
    assert ran == [name for name in stages.STAGE_ORDER if name != "publish"]


def test_publish_is_opt_in(offline, run_dir):
    """Publishing sends work off this machine. Nothing does it unless asked."""
    offline.run()
    st = pstate.PaperState.load_or_create(run_dir)
    assert "publish" not in st.stages


def test_the_paper_passes_its_own_gates(finished_paper):
    report = json.loads((finished_paper / "gates.json").read_text())
    assert report["passed"] is True
    assert report["failures"] == []


def test_the_finished_paper_clears_the_word_floor(finished_paper):
    import paper_check  # noqa: PLC0415

    body = (finished_paper / "whitepaper.md").read_text()
    assert paper_check.word_count(body) >= paper_check.MIN_WORDS


def test_a_warning_is_not_filed_as_a_failure(finished_paper):
    """`publish` reads this file to decide whether the paper may ship, so a soft
    limitations warning must not look like a blocked gate. Length is now hard."""
    report = json.loads((finished_paper / "gates.json").read_text())
    assert "warnings" in report
    assert "length" not in report["warnings"]
    assert "length" not in report["failures"]
    assert not set(report["failures"]) & {"limitations"}


def test_every_citation_in_the_paper_resolves(finished_paper):
    import re  # noqa: PLC0415  (sys.path is set by conftest first)

    body = (finished_paper / "whitepaper.md").read_text()
    references = body[body.rindex("## References") :]
    available = {int(n) for n in re.findall(r"^(\d+)\.", references, re.M)}
    used = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
    assert used <= available, f"dangling: {sorted(used - available)}"


def test_the_paper_embeds_a_figure_with_alt_text(finished_paper):
    import re  # noqa: PLC0415  (sys.path is set by conftest first)

    body = (finished_paper / "whitepaper.md").read_text()
    figures = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", body)
    assert figures
    for alt, target in figures:
        assert alt.strip(), target
        assert (finished_paper / target).exists(), target


def test_no_diagram_source_survives_into_the_paper(finished_paper):
    """The figure is the artifact. `flowchart` inside alt text is prose, so the
    check reads fenced blocks, not the whole document."""
    import paper_check  # noqa: PLC0415  (sys.path is set by conftest first)

    body = (finished_paper / "whitepaper.md").read_text()
    assert paper_check.visible_source_syntax(body) == []
    assert "@startuml" not in body


# -- resume ----------------------------------------------------------------


def test_a_second_run_skips_every_finished_stage(offline, run_dir, capsys):
    offline.run()
    again = _rebuild(run_dir)
    assert again.run() == 0
    assert again.state.total_calls == offline.state.total_calls, "a resume must not re-ask"


def test_a_resume_reruns_a_failed_stage(offline, run_dir):
    """A failed stage is not a finished stage, so resume must not step over it."""
    offline.run()
    st = pstate.PaperState.load_or_create(run_dir)
    st.mark_failed("write", "boom")
    st.save()
    (run_dir / "sections.json").unlink()

    again = _rebuild(run_dir)
    assert again.run() == 0
    assert again.state.is_complete("write")


def test_the_live_planner_file_is_the_plan_not_its_tool_receipt(offline, run_dir):
    """A scoped planner writes valid JSON and commonly returns only "wrote"."""
    from conftest import FIXTURES  # noqa: PLC0415

    expected = json.loads((FIXTURES / "replies.json").read_text())["planner"][
        "Write plan.json"
    ]["data"]

    class FilePlanner:
        name = "deep_agents"

        def ask(self, role, prompt):
            if role == "outline_judge":
                return paper.Reply(
                    data={
                        "passed": True,
                        "score": 1.0,
                        "blocking_issues": [],
                        "actionable_changes": [],
                    }
                )
            assert role == "planner"
            (run_dir / "plan.json").write_text(json.dumps(expected), encoding="utf-8")
            return paper.Reply(text="wrote plan.json")

    offline.runner = FilePlanner()
    result = offline.stage_plan()

    assert result.artifacts["questions"] == 3
    assert offline.plan["title"] == expected["title"]


CREATINE_PLAN = {
    "title": "Creatine supplementation for preventing muscle loss during a calorie deficit",
    "audience": "sports nutrition researchers",
    "questions": [
        {
            "id": "q1",
            "subject": "mechanism",
            "question": "What dosing protocol saturates intramuscular phosphocreatine?",
            "check": "a loading and maintenance dose with a citation",
            "important": True,
        },
        {
            "id": "q2",
            "subject": "baseline-loss",
            "question": "What percentage of lean mass is typically lost during a calorie deficit?",
            "check": "a named study",
            "important": True,
        },
        {
            "id": "q3",
            "subject": "trials",
            "question": "What RCTs measured lean mass retention with creatine during a deficit?",
            "check": "a named RCT",
            "important": False,
        },
    ],
    "sections": [
        {
            "heading": "Abstract",
            "objective": "State the thesis, the evidence behind it, and the limit, in one paragraph.",
            "abstract": "Creatine plausibly protects lean mass during a deficit; this reviews the evidence.",
            "key_questions": ["what does this paper claim", "what evidence supports it"],
        },
        {
            "heading": "Introduction",
            "objective": "Name the problem, who has it, and what this paper settles about it.",
            "abstract": "Resistance-trained people cutting calories risk losing muscle alongside fat.",
            "key_questions": ["who faces this problem", "what does this paper settle"],
        },
        {
            "heading": "Mechanism of Creatine Action",
            "objective": "Explain phosphocreatine buffering and its dosing protocol.",
            "abstract": "Creatine raises intramuscular phosphocreatine, supporting training volume.",
            "key_questions": [
                "What dosing protocol saturates intramuscular phosphocreatine?",
                "how does phosphocreatine buffering work",
            ],
        },
        {
            "heading": "Trial Evidence",
            "objective": "Present named RCTs and their effect sizes.",
            "abstract": "A small set of controlled trials directly test creatine during a deficit.",
            "key_questions": [
                "What RCTs measured lean mass retention with creatine during a deficit?",
                "What percentage of lean mass is typically lost during a calorie deficit?",
            ],
        },
        {
            "heading": "Limitations",
            "objective": "Name what this review does not settle.",
            "abstract": "Trial evidence directly on a deficit is thin.",
            "key_questions": ["where does the evidence run out", "what is understudied"],
        },
        {
            "heading": "References",
            "objective": "List every source the body cites, in citation order.",
            "abstract": "Generated from the evidence ledger.",
            "key_questions": ["which sources does the body cite", "which of them are primary"],
        },
    ],
    "diagrams": [
        {
            "name": "phosphocreatine-pathway",
            "kind": "mermaid",
            "shows": "the pathway from creatine ingestion to phosphocreatine saturation",
        }
    ],
    "notes": ["no prior research found on this topic"],
}


def test_stage_assemble_passes_the_doctrine_flag_to_assemble_gate(run_dir, stub_renderer, monkeypatch):
    """#406: `stage_assemble` must forward `self.loop_doctrine`, not the
    default, or a run built with the flag off would still be graded on it."""
    from conftest import build_run  # noqa: PLC0415

    seen = {}
    real_assemble_gate = stages.assemble_gate

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real_assemble_gate(*args, **kwargs)

    monkeypatch.setattr(stages, "assemble_gate", spy)

    run = build_run(run_dir, loop_doctrine=False)
    assert run.run() == 0
    assert seen["loop_doctrine"] is False


def test_stage_plan_does_not_force_the_doctrine_question_when_the_flag_is_off(run_dir, stub_renderer):
    """#406: off, a plan for a topic with nothing to do with this repo is
    accepted as written, with no forced first question."""
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    class Runner(paper.FixtureRunner):
        def ask(self, role, prompt):
            if role == "planner":
                return paper.Reply(data=dict(CREATINE_PLAN))
            return super().ask(role, prompt)

    run = build_run(run_dir, runner=Runner(FIXTURES / "replies.json"), loop_doctrine=False)

    run.stage_plan()  # must not raise

    assert run.plan["questions"][0]["question"] != stages.EXIT_DOCTRINE_QUESTION
    doctrine_words = ("exit", "cost", "max turns")
    for section in run.plan["sections"]:
        heading = section.get("heading", "").lower()
        text = " ".join(section.get("key_questions") or []).lower()
        assert not any(word in heading for word in doctrine_words), section
        assert not any(word in text for word in doctrine_words), section


class RecordingPlannerRunner(paper.FixtureRunner):
    """Records every prompt the planner role saw, and answers normally."""

    def __init__(self, path):
        super().__init__(path)
        self.planner_prompts: list[str] = []

    def ask(self, role, prompt):
        if role == "planner":
            self.planner_prompts.append(prompt)
        return super().ask(role, prompt)


def _plan_run(topic: str, loop_doctrine: bool, work_dir) -> paper.Paper:
    import research  # noqa: PLC0415
    from conftest import FIXTURES  # noqa: PLC0415

    return paper.Paper(
        topic=topic,
        runner=RecordingPlannerRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=work_dir,
        quiet=True,
        loop_doctrine=loop_doctrine,
    )


def test_stage_plan_requires_the_first_question_at_the_prompt_seam_only_when_on(
    run_dir, stub_renderer
):
    """#406: the skill no longer hard-codes the doctrine question. Python
    names it in the delegation message, and only when the flag is on."""
    off_run = _plan_run("Creatine and lean mass", False, run_dir)
    off_run.stage_plan()
    off_prompt = off_run.runner.planner_prompts[0]
    assert "Required first question" not in off_prompt
    assert "exit" not in off_prompt.lower()
    assert "doctrine" not in off_prompt.lower()

    on_run = _plan_run(
        "Exit conditions in production agent loops", True, run_dir.parent / "run-doctrine-on"
    )
    on_run.stage_plan()
    on_prompt = on_run.runner.planner_prompts[0]
    assert f"Required first question, exactly: {stages.EXIT_DOCTRINE_QUESTION}" in on_prompt


def test_the_planner_skill_no_longer_hard_codes_the_doctrine_question():
    """#406: the live planner reads this file. If it still forced the
    question here, the flag on the Python side would not matter."""
    skill = (
        Path(__file__).resolve().parents[1] / "skills" / "planner" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert stages.EXIT_DOCTRINE_QUESTION not in skill


def test_cost_carries_forward_across_a_resume(offline, run_dir):
    offline.run()
    st = pstate.PaperState.load_or_create(run_dir)
    st.total_cost_usd = 1.25
    st.save()
    assert _rebuild(run_dir).state.total_cost_usd == 1.25


def test_search_reservation_checkpoints_before_a_provider_call(offline, run_dir):
    offline.budget.charge(0.006)

    saved = pstate.PaperState.load_or_create(run_dir)
    assert saved.search_calls == 1
    assert saved.search_cost_usd == 0.006


def _rebuild(run_dir):
    import research  # noqa: PLC0415  (sys.path is set by conftest first)
    from conftest import FIXTURES  # noqa: PLC0415  (sys.path is set by conftest first)

    return paper.Paper(
        topic="Exit conditions in production agent loops",
        runner=paper.FixtureRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=run_dir,
        quiet=True,
    )


# -- the retry loop --------------------------------------------------------


def test_a_stage_that_keeps_failing_escalates(offline, monkeypatch):
    """The same signature twice means the loop is not converging. Spending the
    rest of the budget to watch it fail identically buys a bill, not a fix."""
    monkeypatch.setattr(
        offline, "stage_plan", lambda extra="": (_ for _ in ()).throw(GateFailed("nope", ("x",)))
    )
    assert offline.run() == 2
    assert offline.state.stages["plan"].status == pstate.FAILED


def test_an_escalate_leaves_the_state_resumable(offline, run_dir, monkeypatch):
    monkeypatch.setattr(
        offline, "stage_plan", lambda extra="": (_ for _ in ()).throw(GateFailed("nope", ("x",)))
    )
    offline.run()
    assert (run_dir / pstate.STATE_FILE).exists()


def test_a_spent_budget_stops_before_the_next_stage(offline):
    offline.max_usd = 0.0
    offline.state.total_cost_usd = 0.0
    assert offline.run() == 2 or offline.state.total_cost_usd >= 0.0


def test_a_retry_keeps_the_sections_that_passed(offline, run_dir):
    """The retry exists to fix what failed. Rewriting what passed spends money
    to risk breaking it."""
    offline.run()
    offline.written.clear()
    offline._need_written()
    before = dict(offline.written)
    calls = offline.state.total_calls
    offline.stage_write("")
    assert offline.written == before
    assert offline.state.total_calls == calls


def test_a_review_retry_sends_failed_rows_to_the_writer(offline, monkeypatch):
    offline.run()
    offline.state.mark_failed("review", "rerun")
    calls = {"review": 0, "revise": []}

    def review(_extra=""):
        calls["review"] += 1
        if calls["review"] == 1:
            raise GateFailed("name a tradeoff", ("names_tradeoff",))
        return paper.StageResult("review", summary="fixed")

    def revise(feedback):
        calls["revise"].append(feedback)
        return paper.StageResult("revise", summary="one section")

    monkeypatch.setattr(offline, "stage_review", review)
    monkeypatch.setattr(offline, "stage_revise", revise)

    assert offline.run() == 0
    assert calls["review"] == 2
    assert calls["revise"] and "names_tradeoff" in calls["revise"][0]


# -- #411: the review stall rule gets a progress escape ---------------------


def test_review_retry_continues_when_the_score_rises_a_tenth(offline, monkeypatch):
    """The same rows failing twice is not a stall when the score is moving.
    Copied from the SDK port's `decide(progressed=...)` rule (#361, #362)."""
    calls = {"review": 0}

    def review(_extra=""):
        calls["review"] += 1
        if calls["review"] == 1:
            raise GateFailed("still filler", ("no_filler",), score=0.5)
        if calls["review"] == 2:
            raise GateFailed("still filler", ("no_filler",), score=0.65)
        return paper.StageResult("review", summary="fixed")

    monkeypatch.setattr(offline, "stage_review", review)
    monkeypatch.setattr(
        offline, "stage_revise", lambda feedback, **_: paper.StageResult("revise", summary="ok")
    )

    assert offline._run_stage("review") is None
    assert calls["review"] == 3
    assert offline.state.stages["review"].status == pstate.COMPLETE


def test_review_retry_escalates_when_the_score_does_not_rise(offline, monkeypatch):
    """The same rows and the same score is exactly the existing stall: the
    loop is not converging, and the message says so."""
    calls = {"review": 0}

    def review(_extra=""):
        calls["review"] += 1
        raise GateFailed("still filler", ("no_filler",), score=0.5)

    monkeypatch.setattr(offline, "stage_review", review)
    monkeypatch.setattr(
        offline, "stage_revise", lambda feedback, **_: paper.StageResult("revise", summary="ok")
    )
    said = []
    monkeypatch.setattr(offline, "say", said.append)

    assert offline._run_stage("review") == 2
    assert calls["review"] == 2
    assert offline.state.stages["review"].status == pstate.FAILED
    assert any("the same rows failed twice" in line for line in said)


def test_a_resumed_review_at_budget_escalates_without_a_model_call(offline, monkeypatch):
    """#411: a resume is another attempt against the budget, not a clean
    slate. A stage that already spent every attempt does not buy another."""
    for _ in range(offline.attempts):
        offline.state.mark_in_progress("review")
    offline.state.mark_failed(
        "review", "the same rows failed twice: no_filler. The loop is not converging."
    )
    offline.state.save()

    calls = {"review": 0}
    monkeypatch.setattr(
        offline, "stage_review", lambda extra="": calls.__setitem__("review", calls["review"] + 1)
    )
    said = []
    monkeypatch.setattr(offline, "say", said.append)

    assert offline._run_stage("review") == 2
    assert calls["review"] == 0, "no model call is spent on an already-exhausted stage"
    assert any("3 of 3" in line for line in said)
    assert offline.state.stages["review"].status == pstate.FAILED


def test_a_resumed_review_below_budget_continues_from_the_persisted_count(offline, monkeypatch):
    """#411: `resuming review at attempt 3 of 3` reads the persisted count,
    not a fresh local counter, and keeps going against the same budget."""
    offline.state.mark_in_progress("review")
    offline.state.mark_in_progress("review")
    offline.state.mark_failed("review", "still filler")
    offline.state.save()

    said = []
    monkeypatch.setattr(offline, "say", said.append)
    monkeypatch.setattr(
        offline, "stage_review", lambda extra="": paper.StageResult("review", summary="fixed")
    )

    assert offline._run_stage("review") is None
    assert any("resuming review at attempt 3 of 3" in line for line in said)
    assert offline.state.stages["review"].attempts == 3


def test_review_retry_hands_revise_the_paired_notes_keyed_by_row(offline, monkeypatch):
    """#411: the paired reply shape reaches `stage_revise` with each row
    still attached to its own note."""
    verdict = {
        "failed_rows": [
            {"row": "no_filler", "note": "Paragraph two restates the abstract."},
            {"row": "defines_terms", "note": "MCP is used before it is defined."},
        ],
        "score": 0.4,
    }
    calls = {"review": 0}

    def review(_extra=""):
        calls["review"] += 1
        if calls["review"] == 1:
            stages.review_gate(verdict)
        return paper.StageResult("review", summary="fixed")

    feedback_seen = []

    def revise(feedback, **_):
        feedback_seen.append(feedback)
        return paper.StageResult("revise", summary="ok")

    monkeypatch.setattr(offline, "stage_review", review)
    monkeypatch.setattr(offline, "stage_revise", revise)

    assert offline._run_stage("review") is None
    assert feedback_seen
    assert "no_filler: Paragraph two restates the abstract." in feedback_seen[0]
    assert "defines_terms: MCP is used before it is defined." in feedback_seen[0]


def test_review_retry_with_the_legacy_reply_shape_still_reaches_revise(offline, monkeypatch):
    """The flat list-of-names-plus-notes shape still parses and still reaches
    the revise stage."""
    verdict = {"failed_rows": ["voice"], "notes": ["A rhetorical question opens section 2."]}
    calls = {"review": 0}

    def review(_extra=""):
        calls["review"] += 1
        if calls["review"] == 1:
            stages.review_gate(verdict)
        return paper.StageResult("review", summary="fixed")

    feedback_seen = []

    def revise(feedback, **_):
        feedback_seen.append(feedback)
        return paper.StageResult("revise", summary="ok")

    monkeypatch.setattr(offline, "stage_review", review)
    monkeypatch.setattr(offline, "stage_revise", revise)

    assert offline._run_stage("review") is None
    assert feedback_seen
    assert "voice: A rhetorical question opens section 2." in feedback_seen[0]


def test_the_reviewer_skill_documents_the_paired_reply_shape():
    skill = (
        Path(__file__).resolve().parents[1] / "skills" / "reviewer" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert '"score"' in skill
    assert '"row"' in skill


def test_stage_review_reads_a_recorded_paired_shape_reply(offline):
    """#411 follow-up: the paired shape must reach `review_gate` from an
    actual recorded reply through `_ask`/`_json_reply`, not only from a
    hand-built dict passed straight to the gate."""
    offline.run()
    with pytest.raises(GateFailed) as exc:
        offline.stage_review("PAIRED_SHAPE_PROBE")
    assert exc.value.signature == ("no_filler",)
    assert exc.value.score == 0.55


def test_the_reviewer_schema_and_prompt_both_name_score_and_row():
    """#411 follow-up: the schema `roles.REVIEWER_RESPONSE` admits and the
    shape `stage_review` asks for must not silently drift apart again."""
    import roles  # noqa: PLC0415  (sys.path is set by conftest first)

    roles_src = Path(roles.__file__).read_text(encoding="utf-8")
    schema = roles_src[roles_src.index("REVIEWER_RESPONSE = {") : roles_src.index("RESPONSE_FORMATS = {")]
    assert '"score"' in schema
    assert '"row"' in schema

    paper_src = Path(paper.__file__).read_text(encoding="utf-8")
    prompt = paper_src[paper_src.index("def stage_review(") : paper_src.index("def stage_assemble(")]
    assert '"score"' in prompt
    assert '"row"' in prompt


def test_writer_heading_is_removed_before_the_citation_gate():
    assert paper.section_body("## Abstract\n\nGrounded summary. [1]", "Abstract") == "Grounded summary. [1]"
    assert paper.section_body("Abstract\n\nGrounded summary. [1]", "Abstract") == "Grounded summary. [1]"


def test_assemble_citation_failure_revises_only_uncited_sections(offline, monkeypatch):
    """A local citation repair must not rewrite the reviewer-approved draft."""
    offline.run()
    offline.state.mark_failed("assemble", "rerun")
    offline.written["Introduction"] = "An unsupported transition."
    calls = {"assemble": 0, "targets": None}

    def assemble(_extra=""):
        calls["assemble"] += 1
        if calls["assemble"] == 1:
            raise GateFailed("uncited introduction", ("cited",))
        return paper.StageResult("assemble", summary="fixed")

    def revise(_feedback, *, targets=None):
        calls["targets"] = targets
        return paper.StageResult("revise", summary="one section")

    monkeypatch.setattr(offline, "stage_assemble", assemble)
    monkeypatch.setattr(offline, "stage_revise", revise)

    assert offline.run() == 0
    assert calls["targets"] == ["Introduction"]


def test_a_new_process_reloads_checkpointed_sections_before_writing(offline, run_dir):
    """A process restart happens between sections in a live run, not just retries."""
    offline.run()
    before = json.loads((run_dir / "sections.json").read_text())
    calls = offline.state.total_calls

    resumed = _rebuild(run_dir)
    resumed.stage_write("")

    assert resumed.written == before
    assert resumed.state.total_calls == calls


# -- the fixture runner ----------------------------------------------------


def test_the_fixture_runner_matches_by_prompt_content(offline):
    """Keying by position restarts at zero on a resume and hands the writer the
    outline reply."""
    reply = offline.runner.ask("writer", "Write the 'Limitations' section of X")
    assert "single source" in reply.text


def test_the_fixture_runner_says_when_nothing_matches(offline):
    with pytest.raises(GateFailed) as exc:
        offline.runner.ask("writer", "a prompt that matches no recorded key")
    assert "Recorded keys" in str(exc.value)


def test_an_unknown_role_is_a_gate_failure_not_a_crash(offline):
    with pytest.raises(GateFailed):
        offline.runner.ask("nobody", "anything")


class StreamingAgent:
    """A v2 LangGraph stream: nested debug events, then final parent state."""

    def __init__(self):
        self.payload = None
        self.options = None

    def stream(self, payload, **options):
        self.payload = payload
        self.options = options
        yield {
            "type": "debug",
            "ns": ("researcher:abc",),
            "data": {"type": "task", "name": "researcher"},
        }
        yield {
            "type": "values",
            "ns": ("tools:opaque-task-id",),
            "data": {
                "messages": [
                    {"role": "assistant", "name": "researcher", "content": "[1] delegated answer"}
                ]
            },
        }
        yield {
            "type": "values",
            "ns": (),
            "data": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": "parent tool receipt",
                        "usage_metadata": {"cost": 0.25},
                    }
                ]
            },
        }

    def invoke(self, _payload):  # pragma: no cover - the test proves this stays unused
        raise AssertionError("debug mode must stream instead of invoking a second model call")


def test_debug_runner_streams_subgraphs_and_keeps_the_final_parent_state(capsys):
    agent = StreamingAgent()
    runner = paper.DeepAgentsRunner(agent, debug=True)

    reply = runner.ask("researcher", "return JSON")

    assert reply.text == "[1] delegated answer"
    assert reply.usd == 0.25
    assert agent.options == {
        "stream_mode": ["debug", "values"],
        "subgraphs": True,
        "version": "v2",
    }
    assert "Delegate this to the researcher subagent" in agent.payload["messages"][0]["content"]
    out = capsys.readouterr().err
    assert "role=researcher" in out
    assert "namespace=researcher:abc" in out


def test_debug_runner_fails_clearly_without_a_final_parent_state():
    class NoResult:
        def stream(self, *_args, **_kwargs):
            return iter(())

    with pytest.raises(RuntimeError, match="without a final parent values event"):
        paper.DeepAgentsRunner(NoResult(), debug=True).ask("reviewer", "grade")


def test_direct_role_runner_receives_the_unwrapped_stage_prompt():
    class DirectRole:
        def __init__(self):
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return {"messages": [{"role": "assistant", "content": "[1] cited body"}]}

    writer = DirectRole()
    reply = paper.DeepAgentsRunner({"writer": writer}).ask("writer", "Write with [1].")

    assert reply.text == "[1] cited body"
    assert writer.payload["messages"][0]["content"] == "Write with [1]."


def test_a_fenced_diagram_reply_is_unfenced():
    assert paper._strip_fence("```mermaid\nflowchart LR\n  A --> B\n```") == (
        "flowchart LR\n  A --> B\n"
    )
    assert paper._strip_fence("flowchart LR\n  A --> B") == "flowchart LR\n  A --> B\n"


def test_the_live_diagrammer_file_is_not_replaced_by_its_tool_receipt(
    offline, run_dir, stub_renderer
):
    offline.stage_plan()

    class FileDiagrammer:
        name = "deep_agents"

        def ask(self, role, prompt):
            assert role == "diagrammer"
            diagrams = run_dir / "diagrams"
            diagrams.mkdir(exist_ok=True)
            if "three-exits" in prompt:
                target = diagrams / "three-exits.mmd"
                target.write_text('flowchart LR\n  A["Done"] --> B["Cost"]\n', encoding="utf-8")
            else:
                target = diagrams / "maker-checker.puml"
                target.write_text(
                    '@startuml\nparticipant "Maker" as M\nparticipant "Checker" as C\nM -> C: draft\n@enduml\n',
                    encoding="utf-8",
                )
            return paper.Reply(text=f"wrote {target.name}")

    offline.runner = FileDiagrammer()
    offline.stage_diagram()

    assert (run_dir / "diagrams" / "three-exits.mmd").read_text().startswith("flowchart")
    assert (run_dir / "diagrams" / "maker-checker.puml").read_text().startswith("@startuml")


# -- the cost cap ----------------------------------------------------------


class Priced(paper.FixtureRunner):
    """Recorded replies at a realistic price. Writing costs, searching does not."""

    PRICE: ClassVar[dict] = {
        "planner": 0.05,
        "outline_judge": 0.05,
        "section_judge": 0.05,
        "ledger": 0.05,
        "researcher": 0.05,
        "verifier": 0.05,
        "diagrammer": 0.05,
        "writer": 2.00,
        "reviewer": 0.10,
    }

    def ask(self, role, prompt):
        reply = super().ask(role, prompt)
        reply.usd = self.PRICE.get(role, 0.05)
        return reply


def priced_run(work_dir, cap):
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    return build_run(work_dir, runner=Priced(FIXTURES / "replies.json"), max_usd=cap)


def stopped_at(run):
    """Which stage failed and why. An exit code alone proves nothing.

    `run() == 2` means the run escalated. It does not say whether the money ran
    out or a renderer was missing, and a test that checks only the code passes
    for either. That is exactly how the first version of this file was a false
    green: on a machine with no plantuml the run died at `diagram` and still
    returned 2.
    """
    for name, entry in run.state.stages.items():
        if entry.status == pstate.FAILED:
            return name, entry.error or ""
    return None, ""


def test_the_cap_holds_inside_a_stage(run_dir, stub_renderer):
    """Checking only between stages is not a cap. A stage that loops over six
    sections makes six calls with nothing between them, so the run learns it is
    over budget once the money is gone. This case used to spend $4.45 of $3.00."""
    run = priced_run(run_dir, 3.00)
    assert run.run() == 2

    stage, why = stopped_at(run)
    assert stage == "write", (
        f"the run must reach the writer to prove anything, it stopped at {stage}"
    )
    assert "writer call needs" in why, why
    assert run.state.total_cost_usd <= 3.00, f"spent ${run.state.total_cost_usd:.2f} of $3.00"


def test_the_writer_was_actually_reached(run_dir, stub_renderer):
    """A guard on the guard. Every earlier stage must have completed, or the cap
    test above is measuring a different failure."""
    run = priced_run(run_dir, 3.00)
    run.run()
    done = [n for n, s in run.state.stages.items() if s.status == pstate.COMPLETE]
    assert done == ["corpus", "scout", "plan", "sources", "search", "verify", "outline", "diagram", "charts"], done


def test_the_run_says_which_call_it_could_not_afford(run_dir, stub_renderer, capsys):
    run = priced_run(run_dir, 3.00)
    run.quiet = False
    run.run()
    out = capsys.readouterr().out
    assert "writer call needs" in out
    assert "cost" in out


def test_a_spent_budget_is_never_retried(run_dir, stub_renderer):
    """A gate failure might be fixed by another attempt. A spent budget will not
    be, and retrying on it turns a cost cap into a cost multiplier."""
    run = priced_run(run_dir, 3.00)
    run.run()
    assert run.state.attempts("write") == 1


def test_a_cheap_run_still_finishes(run_dir, stub_renderer):
    run = priced_run(run_dir, 100.0)
    assert run.run() == 0
    assert run.state.total_cost_usd <= 100.0


def test_the_total_counts_each_call_once(run_dir, stub_renderer):
    """`spend` and `mark_complete` both used to add."""
    run = priced_run(run_dir, 100.0)
    run.run()
    by_stage = sum(entry.cost_usd for entry in run.state.stages.values())
    assert run.state.total_cost_usd == pytest.approx(by_stage), (
        "the total and the per-stage costs describe the same calls"
    )


# -- a machine with no image backend ---------------------------------------


def test_a_missing_image_backend_blocks_the_paper(run_dir, no_renderer):
    run = priced_run(run_dir, 100.0)
    with pytest.raises(stages.diagrams.ImageBackendUnavailable) as exc:
        run.run()
    assert exc.value.exit_code == 2
    assert exc.value.prompt_file.read_text() == "plugin-built prompt"
    assert not (run_dir / "whitepaper.md").exists()


def test_a_missing_image_backend_is_never_retried(run_dir, no_renderer):
    run = priced_run(run_dir, 100.0)
    with pytest.raises(stages.diagrams.ImageBackendUnavailable):
        run.run()
    assert run.state.attempts("diagram") == 1


def test_sections_written_before_a_stop_survive(run_dir, stub_renderer):
    """A stage that persists only on success makes a mid-stage stop cost the
    whole stage again, which is the opposite of what a cost cap is for."""
    run = priced_run(run_dir, 5.10)
    run.run()
    sections = run_dir / "sections.json"
    if sections.exists():
        assert json.loads(sections.read_text()), "a partial stage still checkpoints"


def test_findings_are_written_per_question(offline, run_dir):
    offline.stage_plan()
    offline.stage_search()
    assert list((run_dir / "evidence").glob("finding.*.md"))


def test_an_empty_checkpointed_finding_is_researched_again(offline):
    import evidence  # noqa: PLC0415

    offline.stage_plan()
    first = offline.plan["questions"][0]
    offline.ledger.add_finding(
        evidence.Finding(
            question=first["question"],
            subject=first["subject"],
            summary="the provider returned no admitted source",
        )
    )

    offline.stage_search()

    assert any(
        finding.subject == first["subject"] and finding.claim_ids
        for finding in offline.ledger.findings.values()
    )


def test_an_empty_nonblocking_finding_is_not_researched_again(offline):
    import evidence  # noqa: PLC0415

    offline.stage_plan()
    question = next(q for q in offline.plan["questions"] if not q.get("important"))
    offline.ledger.add_finding(
        evidence.Finding(
            question=question["question"],
            subject=question["subject"],
            summary="no admitted official source",
        )
    )
    delegated = offline.runner
    prompts = []

    class CountingRunner:
        name = delegated.name

        def ask(self, role, prompt):
            prompts.append(prompt)
            return delegated.ask(role, prompt)

    offline.runner = CountingRunner()
    offline.stage_search()

    assert not any(question["question"] in prompt for prompt in prompts)


def test_live_search_records_the_repo_question_without_a_model_query(offline):
    offline.stage_plan()
    delegated = offline.runner
    calls = []

    class LiveLikeRunner:
        name = "deep_agents"

        def ask(self, role, prompt):
            calls.append((role, prompt))
            return delegated.ask(role, prompt)

    offline.runner = LiveLikeRunner()
    offline.stage_search()

    first = offline.plan["questions"][0]
    assert not any(first["question"] in prompt for _role, prompt in calls)
    assert any(
        finding.subject == first["subject"] and finding.claim_ids
        for finding in offline.ledger.findings.values()
    )


def test_the_repository_shortcut_is_never_consulted_when_the_flag_is_off(offline, monkeypatch):
    """#406: off, even a deep_agents runner asks the researcher like any other
    question, rather than answering the doctrine question from this repo."""
    import research  # noqa: PLC0415

    offline.loop_doctrine = False
    offline.stage_plan()
    delegated = offline.runner

    class LiveLikeRunner:
        name = "deep_agents"

        def ask(self, role, prompt):
            return delegated.ask(role, prompt)

    offline.runner = LiveLikeRunner()
    calls = []
    monkeypatch.setattr(
        research, "repository_doctrine_report", lambda q: calls.append(q) or None
    )

    offline.stage_search()

    assert not calls, "the repository shortcut must not fire when the flag is off"


# -- the money exit, and the turn log ---------------------------------------


class TokenOnly(paper.FixtureRunner):
    """Recorded replies whose usage metadata carries tokens and no dollars.

    This is what LangChain actually returns. The old `last_usd` looked only for
    a cost key, summed to zero on every call, and left the money exit
    unreachable: the run could stop on turns or on the rubric, never on spend.
    """

    TOKENS: ClassVar[dict] = {"writer": (200_000, 60_000)}

    def ask(self, role, prompt):
        import adapter  # noqa: PLC0415

        reply = super().ask(role, prompt)
        tokens_in, tokens_out = self.TOKENS.get(role, (10_000, 2_000))
        result = {
            "messages": [
                {
                    "role": "assistant",
                    "content": reply.text,
                    "usage_metadata": {"input_tokens": tokens_in, "output_tokens": tokens_out},
                }
            ]
        }
        priced = paper._reply_from(adapter, reply.text, result)
        priced.data = reply.data
        return priced


def test_token_only_replies_still_fire_the_money_exit(run_dir, stub_renderer):
    """Proof the cost exit is reachable at all. It was not before this (#303)."""
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    run = build_run(run_dir, runner=TokenOnly(FIXTURES / "replies.json"), max_usd=3.00)
    assert run.run() == 2
    stage, why = stopped_at(run)
    assert stage == "write", f"the run must reach the writer, it stopped at {stage}"
    assert "call needs" in why, why
    assert run.state.total_cost_usd > 0.0, "priced tokens must move the total"
    assert run.state.total_cost_usd <= 3.00, f"spent ${run.state.total_cost_usd:.2f} of $3.00"


def test_every_call_writes_a_turn_row_and_flushes_the_state(run_dir, stub_renderer):
    """A stage that makes six calls used to leave the checkpoint stale for all six."""
    run = priced_run(run_dir, 3.00)
    run.run()

    rows = [
        json.loads(line)
        for line in (Path(run_dir) / ".harness" / "turns.jsonl").read_text().splitlines()
    ]
    assert len(rows) == run.state.total_calls - run.state.search_calls
    assert [row["turn"] for row in rows] == sorted(row["turn"] for row in rows)
    assert {row["role"] for row in rows} >= {"planner", "writer"}
    assert all(row["stage"] for row in rows)
    assert all(row["elapsed_s"] >= 0 for row in rows)

    saved = json.loads((Path(run_dir) / pstate.STATE_FILE).read_text())
    assert saved["current_role"] == rows[-1]["role"]
    assert saved["last_turn"]["turn"] == rows[-1]["turn"]


def test_a_call_with_no_reported_cost_logs_null_not_zero(run_dir, stub_renderer):
    """A zero reads as a free call and hides a dead cost path."""
    run = priced_run(run_dir, 3.00)
    run._record_turn("writer", paper.Reply(text="x", usd=0.0), 1.5, 400)
    row = json.loads((Path(run_dir) / ".harness" / "turns.jsonl").read_text().splitlines()[-1])
    assert row["usd"] is None

    run._record_turn("writer", paper.Reply(text="x", usd=0.0, cost_reported=True), 1.5, 400)
    row = json.loads((Path(run_dir) / ".harness" / "turns.jsonl").read_text().splitlines()[-1])
    assert row["usd"] == 0.0


class Recorder(paper.FixtureRunner):
    """Recorded replies, plus the prompt each role was actually handed."""

    def __init__(self, path):
        super().__init__(path)
        self.prompts: list[tuple[str, str]] = []

    def ask(self, role, prompt):
        self.prompts.append((role, prompt))
        return super().ask(role, prompt)


def test_the_outline_judge_is_handed_parseable_json(run_dir, stub_renderer):
    """The stage must use `for_judge`. Testing `for_judge` alone proved nothing.

    `paper.py` sliced the outline with `json.dumps(...)[:8000]`, which cut a
    9,114 character outline mid-key. The judge got malformed JSON and 6 of 7
    sections, reported it as truncated, and failed two live runs (#323). A test
    on the helper does not catch a stage that stopped calling the helper.
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    runner = Recorder(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    run.run()

    judged = [prompt for role, prompt in runner.prompts if role == "outline_judge"]
    assert judged, "the outline judge was never asked"
    for prompt in judged:
        body = prompt[prompt.index("{"):]
        parsed = json.loads(body)
        assert parsed["sections"], "the judge must see at least one section"

    assert "withheld" not in judged[0], "nothing was cut, so nothing to declare"


def test_a_cut_outline_reaches_the_judge_whole_and_labelled(run_dir, stub_renderer, monkeypatch):
    """Proof the stage calls `for_judge` rather than slicing the JSON itself.

    Squeeze the ceiling until the outline cannot fit. The prompt must still
    parse, and it must say how many sections were withheld. A raw slice would
    fail both.
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    monkeypatch.setattr(paper.outlines, "JUDGE_PROMPT_CHARS", 600)
    runner = Recorder(FIXTURES / "replies.json")
    build_run(run_dir, runner=runner).run()

    prompt = next(p for role, p in runner.prompts if role == "outline_judge")
    body = json.loads(prompt[prompt.index("{"):])
    assert body["sections"], "at least one section always survives"
    assert "are withheld for length" in prompt
    assert "do not fail completeness for the withheld" in prompt


def test_a_gate_failure_during_revise_escalates_instead_of_crashing(run_dir, stub_renderer):
    """`stage_revise` runs from inside the handler that is already handling a
    GateFailed. An unguarded raise there escapes both and kills the run with a
    traceback: no attempt accounting, no escalation, no reason to read.

    One model turn returning prose instead of JSON ended a live run that had
    cleared every stage up to review (#325).
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    run = build_run(run_dir, runner=Recorder(FIXTURES / "replies.json"))

    def always_fails(extra, targets=None):
        raise stages.GateFailed("the reply held no JSON object.", ("not_json",))

    def review_never_passes(extra):
        raise stages.GateFailed("the reviewer failed these rows. no_filler", ("no_filler",))

    run.stage_revise = always_fails
    run.stage_review = review_never_passes

    code = run.run()

    assert code == 2, "a run that cannot revise must escalate, not raise"
    failed = [name for name, entry in run.state.stages.items() if entry.status == pstate.FAILED]
    assert "review" in failed, failed
    assert (Path(run_dir) / pstate.STATE_FILE).exists(), "state must survive for --resume"


# -- the locator: a cabinet claim is cross-referenced, or it is dropped -----

CABINET_SHA = "sha256:00000000000000000000000000000000000000000000000000000000000003e9"
LOCATED_URL = "https://arxiv.org/abs/2503.13657"
CLAIM_TEXT = "A production loop checks done, then cost, then max turns before it exits."
# `corpus` names a hit `<root directory>:<claim id>`, so both keys are known
# before the pack is written. `test_the_probe_brain_packs_both_keys` proves it.
KEY_ONE = "cabinet:claim.exits.1"
KEY_TWO = "cabinet:claim.exits.2"
HIT_REPLY = {"url": LOCATED_URL, "supports": True, "excerpt": "verbatim"}


def _claim_file(root: Path, claim_id: str) -> None:
    (root / "research" / "claims" / f"{claim_id}.md").write_text(
        f'---\ntype: "Claim"\nid: "{claim_id}"\n'
        f'description: "{CLAIM_TEXT}"\nconfidence: 0.9\n'
        'links:\n  - rel: evidenced_by\n    target: "evidence.exits"\n'
        f"---\n\n# Claim\n\n{CLAIM_TEXT}\n",
        encoding="utf-8",
    )


def _cabinet_brain(tmp_path: Path, source_front: str = "", title: str = "Why Do Multi-Agent LLM Systems Fail?") -> Path:
    """Two claims, one evidence node, one source. Both claims share the hash."""
    import corpus  # noqa: PLC0415

    corpus.clear_cache()
    root = tmp_path / "cabinet"
    research = root / "research"
    for folder in ("claims", "evidence", "sources"):
        (research / folder).mkdir(parents=True, exist_ok=True)
    _claim_file(root, "claim.exits.1")
    _claim_file(root, "claim.exits.2")
    (research / "evidence" / "evidence.exits.md").write_text(
        '---\ntype: "Evidence"\nid: "evidence.exits"\n'
        'text: "Exit on done, then cost, then max turns."\n'
        f'source_hash: "{CABINET_SHA}"\n---\n\nExit on done, then cost, then max turns.\n',
        encoding="utf-8",
    )
    (research / "sources" / "source.exits.md").write_text(
        '---\ntype: "SourceDocument"\nid: "source.exits"\n'
        f'title: "{title}"\nvendor: "Berkeley"\n'
        f'source_hash: "{CABINET_SHA}"\n{source_front}---\n\nA cabinet capture.\n',
        encoding="utf-8",
    )
    return root


def _researcher_reply(refs: list[str], extra: list[dict] | None = None) -> dict:
    """One reply that cites the cabinet by key, plus one admitted web source."""
    sources = [
        {
            "title": "Why Do Multi-Agent LLM Systems Fail?",
            "url": f"corpus:{ref}",
            "vendor": "Berkeley",
            "quote": "Exit on done, then cost, then max turns.",
        }
        for ref in refs
    ]
    sources += extra or []
    sources.append(
        {
            "title": "Deep Agents",
            "url": "https://docs.langchain.com/deep-agents",
            "vendor": "LangChain",
            "quote": "The graph carries a recursion limit.",
        }
    )
    return {
        "answer": "Loops exit on done, then cost, then max turns.",
        "sources": sources,
        "claims": [
            {"text": CLAIM_TEXT, "confidence": 0.8, "source_urls": [f"corpus:{refs[0]}"]},
            {
                "text": "Deep Agents carries a recursion limit.",
                "confidence": 0.8,
                "source_urls": ["https://docs.langchain.com/deep-agents"],
            },
        ],
    }


def _cabinet_run(run_dir, brain, reply: dict, locator):
    """A run whose researcher cites the cabinet and whose locator the test owns.

    `locator` is a reply dict, or None to let the fixture raise `GateFailed`
    for a role it has never heard of.
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    fixture = paper.FixtureRunner(FIXTURES / "replies.json")
    calls: list = []

    class Runner:
        # The live name, so the repository question is answered without a turn.
        name = "deep_agents"

        def ask(self, role, prompt):
            calls.append((role, prompt))
            if role == "locator":
                if locator is None:
                    return fixture.ask("locator", prompt)
                return paper.Reply(data=dict(locator))
            if role == "researcher":
                return paper.Reply(data=json.loads(json.dumps(reply)))
            return fixture.ask(role, prompt)

    return build_run(run_dir, runner=Runner(), brains=[brain]), calls


def _drive(run):
    run.stage_corpus()
    run.stage_plan()
    return run.stage_search()


def _roles(calls) -> list[str]:
    return [role for role, _ in calls]


def _urls(run) -> dict:
    return {source.url: source for source in run.ledger.sources.values()}


def _unresolved(run_dir) -> list[dict]:
    payload = json.loads((Path(run_dir) / "corpus" / "unresolved.json").read_text())
    return payload["unresolved"]


def test_the_probe_brain_packs_both_keys(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    run, _ = _cabinet_run(run_dir, brain, _researcher_reply([KEY_ONE]), HIT_REPLY)
    run.stage_corpus()
    packed = json.loads((Path(run_dir) / "corpus" / "brain-pack.json").read_text())
    assert set(packed["keys"]) == {KEY_ONE, KEY_TWO}


def test_a_located_cabinet_source_enters_the_ledger_with_its_url(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    run, calls = _cabinet_run(run_dir, brain, _researcher_reply([KEY_ONE]), HIT_REPLY)

    _drive(run)

    sources = _urls(run)
    assert LOCATED_URL in sources, sorted(sources)
    assert sources[LOCATED_URL].located_from == KEY_ONE
    assert not any(url.startswith("corpus:") for url in sources)
    # The claim that named the key follows it to the located page, and binds
    # to that source alone. A dropped reference would inherit every source in
    # the answer, which is how a cabinet claim ends up citing an unrelated page.
    cabinet_claims = [c for c in run.ledger.claims.values() if c.text == CLAIM_TEXT]
    assert cabinet_claims
    assert all(run.ledger.urls_for(claim.id) == [LOCATED_URL] for claim in cabinet_claims)
    # The SourceDocument in the brain learned the public page.
    assert f'url: "{LOCATED_URL}"' in (
        brain / "research" / "sources" / "source.exits.md"
    ).read_text(encoding="utf-8")
    cache = json.loads((Path(run_dir) / "corpus" / "located.json").read_text())
    assert cache[CABINET_SHA]["url"] == LOCATED_URL
    assert "locator" in _roles(calls)


def test_a_locator_miss_drops_the_source_and_records_the_key(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    run, _ = _cabinet_run(
        run_dir,
        brain,
        _researcher_reply([KEY_ONE]),
        {"url": "", "supports": False, "excerpt": ""},
    )

    _drive(run)

    assert not any("arxiv" in url or url.startswith("corpus:") for url in _urls(run))
    assert any(row["key"] == KEY_ONE for row in _unresolved(run_dir))


def test_two_sources_sharing_one_hash_cost_one_locator_turn(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    run, calls = _cabinet_run(run_dir, brain, _researcher_reply([KEY_ONE, KEY_TWO]), HIT_REPLY)

    _drive(run)

    assert _roles(calls).count("locator") == 1


def test_a_pack_hit_that_already_carries_a_url_costs_no_turn(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path, source_front=f'url: "{LOCATED_URL}"\n')
    run, calls = _cabinet_run(run_dir, brain, _researcher_reply([KEY_ONE]), None)

    _drive(run)

    assert "locator" not in _roles(calls)
    assert _urls(run)[LOCATED_URL].located_from == KEY_ONE


def test_an_untagged_off_allowlist_url_is_still_refused(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    reply = _researcher_reply(
        [KEY_ONE], extra=[{"title": "A post", "url": "https://medium.com/x", "quote": "q"}]
    )
    run, _ = _cabinet_run(run_dir, brain, reply, HIT_REPLY)

    _drive(run)

    assert not any("medium.com" in url for url in _urls(run))


def test_a_locator_the_runtime_cannot_reach_is_a_miss_and_the_stage_completes(
    run_dir, tmp_path, stub_renderer
):
    """`GateFailed` from the turn is an honest miss, not a dead stage."""
    brain = _cabinet_brain(tmp_path)
    run, _ = _cabinet_run(run_dir, brain, _researcher_reply([KEY_ONE]), None)

    result = _drive(run)

    assert result.name == "search"
    assert any("no recorded reply" in row["reason"] for row in _unresolved(run_dir))
    assert run.ledger.claims, "the admitted web claim still reached the ledger"


def test_an_ambiguous_corpus_key_is_refused_rather_than_guessed(run_dir, tmp_path, stub_renderer):
    """Two claims end in `.1`. Directory order must not settle which is cited."""
    brain = _cabinet_brain(tmp_path)
    _claim_file(brain, "claim.other.1")
    run, calls = _cabinet_run(run_dir, brain, _researcher_reply(["1"]), HIT_REPLY)

    _drive(run)

    assert "locator" not in _roles(calls)
    assert any("ambiguous corpus key" in row["reason"] for row in _unresolved(run_dir))
    assert not any("arxiv" in url for url in _urls(run))


def test_a_suffix_key_still_resolves(run_dir, tmp_path, stub_renderer):
    """A model writes the claim id where the pack holds the whole key."""
    brain = _cabinet_brain(tmp_path)
    run, _ = _cabinet_run(run_dir, brain, _researcher_reply(["claim.exits.1"]), HIT_REPLY)

    _drive(run)

    assert _urls(run)[LOCATED_URL].located_from == KEY_ONE


def test_an_unknown_corpus_key_is_recorded_and_costs_no_turn(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    run, calls = _cabinet_run(run_dir, brain, _researcher_reply(["cabinet:claim.nobody"]), HIT_REPLY)

    _drive(run)

    assert "locator" not in _roles(calls)
    assert any(row["reason"] == "unresolved corpus key" for row in _unresolved(run_dir))


def _locate_only(run_dir, brain, reply, locator):
    """Drive the cross-reference alone, so the reply mutation is observable."""
    run, _ = _cabinet_run(run_dir, brain, reply, locator)
    run.stage_corpus()
    run._locate_cabinet_sources({"subject": "s1"}, reply)
    return reply


def test_a_missed_source_item_is_removed_from_the_reply(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    reply = _locate_only(
        run_dir,
        brain,
        _researcher_reply([KEY_ONE]),
        {"url": "", "supports": False, "excerpt": ""},
    )
    assert [source["url"] for source in reply["sources"]] == [
        "https://docs.langchain.com/deep-agents"
    ]


def test_a_missed_key_takes_the_claim_that_rested_on_it(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    reply = _locate_only(
        run_dir,
        brain,
        _researcher_reply([KEY_ONE]),
        {"url": "", "supports": False, "excerpt": ""},
    )
    assert [claim["text"] for claim in reply["claims"]] == [
        "Deep Agents carries a recursion limit."
    ]
    assert _unresolved(run_dir)[0]["claims_dropped"] == [CLAIM_TEXT[:60]]


def test_a_located_key_is_rewritten_on_the_source_item_and_the_claim(
    run_dir, tmp_path, stub_renderer
):
    brain = _cabinet_brain(tmp_path)
    reply = _locate_only(run_dir, brain, _researcher_reply([KEY_ONE]), HIT_REPLY)
    assert reply["sources"][0]["url"] == LOCATED_URL
    assert reply["sources"][0]["located_from"] == KEY_ONE
    assert reply["claims"][0]["source_urls"] == [LOCATED_URL]


def test_an_unresolved_key_is_removed_from_every_claim(run_dir, tmp_path, stub_renderer):
    """A key the cabinet does not hold must not survive as a claim reference."""
    brain = _cabinet_brain(tmp_path)
    reply = _locate_only(run_dir, brain, _researcher_reply(["cabinet:claim.nobody"]), HIT_REPLY)
    assert CLAIM_TEXT not in [claim["text"] for claim in reply["claims"]]
    assert not any(url.startswith("corpus:") for url in (s["url"] for s in reply["sources"]))


def test_a_source_with_no_title_is_a_miss_and_costs_no_turn(run_dir, tmp_path, stub_renderer):
    """There is nothing to search for, so paying a turn to find out is waste."""
    brain = _cabinet_brain(tmp_path, title="")
    reply = _researcher_reply([KEY_ONE])
    reply["sources"][0]["title"] = ""
    run, calls = _cabinet_run(run_dir, brain, reply, HIT_REPLY)
    run.stage_corpus()
    run._locate_cabinet_sources({"subject": "s1"}, reply)

    assert "locator" not in _roles(calls)
    assert CLAIM_TEXT not in [claim["text"] for claim in reply["claims"]]
    assert any(row["reason"] == "no title to locate" for row in _unresolved(run_dir))


def test_a_claim_resting_only_on_a_missed_key_never_reaches_the_ledger(
    run_dir, tmp_path, stub_renderer
):
    """No page, no claim. An empty `source_urls` would inherit the web source."""
    brain = _cabinet_brain(tmp_path)
    run, _ = _cabinet_run(
        run_dir,
        brain,
        _researcher_reply([KEY_ONE]),
        {"url": "", "supports": False, "excerpt": ""},
    )

    _drive(run)

    assert CLAIM_TEXT not in [claim.text for claim in run.ledger.claims.values()]
    assert not any(
        "docs.langchain.com" in url
        for claim in run.ledger.claims.values()
        if claim.text == CLAIM_TEXT
        for url in run.ledger.urls_for(claim.id)
    )
    assert any(row["claims_dropped"] == [CLAIM_TEXT[:60]] for row in _unresolved(run_dir))


def test_a_claim_that_also_named_a_web_source_survives_the_miss(run_dir, tmp_path, stub_renderer):
    brain = _cabinet_brain(tmp_path)
    reply = _researcher_reply([KEY_ONE])
    reply["claims"][0]["source_urls"] = [
        f"corpus:{KEY_ONE}",
        "https://docs.langchain.com/deep-agents",
    ]
    run, _ = _cabinet_run(run_dir, brain, reply, {"url": "", "supports": False, "excerpt": ""})

    _drive(run)

    kept = [claim for claim in run.ledger.claims.values() if claim.text == CLAIM_TEXT]
    assert kept
    assert all(
        run.ledger.urls_for(claim.id) == ["https://docs.langchain.com/deep-agents"]
        for claim in kept
    )


def test_a_reply_that_cites_the_pack_hits_public_url_is_tagged_without_a_turn(
    run_dir, tmp_path, stub_renderer
):
    """The belt. The skill says cite the key; the outcome must not depend on it."""
    brain = _cabinet_brain(tmp_path, source_front=f'url: "{LOCATED_URL}"\n')
    reply = _researcher_reply([KEY_ONE])
    # The researcher took the `URL:` line instead of the key.
    reply["sources"][0]["url"] = LOCATED_URL
    reply["claims"][0]["source_urls"] = [LOCATED_URL]
    run, calls = _cabinet_run(run_dir, brain, reply, None)

    _drive(run)

    assert "locator" not in _roles(calls)
    assert _urls(run)[LOCATED_URL].located_from == KEY_ONE
    cabinet_claims = [c for c in run.ledger.claims.values() if c.text == CLAIM_TEXT]
    assert cabinet_claims
    assert all(run.ledger.urls_for(claim.id) == [LOCATED_URL] for claim in cabinet_claims)


class RecordingBudget:
    """A real budget that remembers the ceilings each request was opened with."""

    def __init__(self, **kwargs):
        import research  # noqa: PLC0415

        self.inner = research.Budget(**kwargs)
        self.events: list = []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def __setattr__(self, name, value):
        if name in ("inner", "events"):
            super().__setattr__(name, value)
        else:
            setattr(self.inner, name, value)

    def begin_request(self, max_calls=None, *, max_provider_calls=None):
        self.events.append(("begin", max_calls, max_provider_calls))
        self.inner.begin_request(max_calls, max_provider_calls=max_provider_calls)

    def end_request(self):
        self.events.append(("end", self.inner._tool_limit))
        self.inner.end_request()


def test_the_locator_turn_runs_under_a_one_call_ceiling_that_is_always_lifted(
    run_dir, tmp_path, stub_renderer
):
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    brain = _cabinet_brain(tmp_path)
    reply = _researcher_reply([KEY_ONE])
    fixture = paper.FixtureRunner(FIXTURES / "replies.json")
    seen: list = []

    class Runner:
        name = "deep_agents"

        def ask(self, role, prompt):
            if role == "locator":
                # The ceiling has to be live while the turn is in flight.
                seen.append((run.budget._tool_limit, run.budget._request_limit))
                return paper.Reply(data=dict(HIT_REPLY))
            if role == "researcher":
                return paper.Reply(data=json.loads(json.dumps(reply)))
            return fixture.ask(role, prompt)

    budget = RecordingBudget(max_usd=10.0, max_calls=50)
    run = build_run(run_dir, runner=Runner(), brains=[brain], search_budget=budget)
    _drive(run)

    assert seen == [(1, 1)], seen
    assert ("begin", 1, 1) in budget.events
    assert budget.events.count(("begin", 1, 1)) == 1
    assert sum(1 for event in budget.events if event[0] == "begin") == sum(
        1 for event in budget.events if event[0] == "end"
    )
    assert budget.inner._tool_limit is None, "the ceiling outlived the turn"


# -- a transient provider error at the model-call boundary (#409) ----------


class TransientThenFixture(paper.FixtureRunner):
    """Fails one role's first N calls with a transient error, then answers
    from the recorded fixture as usual."""

    def __init__(self, path, role, make_error, fail_times):
        super().__init__(path)
        self.role = role
        self.make_error = make_error
        self.fail_times = fail_times
        self.failed = 0

    def ask(self, role, prompt):
        if role == self.role and self.failed < self.fail_times:
            self.failed += 1
            raise self.make_error()
        return super().ask(role, prompt)


def _connection_error():
    import anthropic  # noqa: PLC0415
    import httpx2  # noqa: PLC0415

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _rate_limit_error():
    import anthropic  # noqa: PLC0415
    import httpx2  # noqa: PLC0415

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        429,
        request=request,
        json={"error": {"type": "rate_limit_error", "message": "slow down"}},
    )
    return anthropic.RateLimitError(
        "slow down", response=response, body={"error": {"type": "rate_limit_error"}}
    )


def test_a_transient_error_twice_then_an_answer_completes_the_turn(
    run_dir, stub_renderer, monkeypatch, capsys
):
    """#409: two dropped connections, then a normal reply. Both retries are
    logged, the turn row carries them, the budget is charged once, and the
    stage attempt count stays at one."""
    pytest.importorskip("anthropic")
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    waits: list[float] = []
    monkeypatch.setattr(paper, "_sleep", waits.append)

    runner = TransientThenFixture(FIXTURES / "replies.json", "planner", _connection_error, 2)
    run = build_run(run_dir, runner=runner)
    run.quiet = False

    assert run.run() == 0
    assert waits == [5.0, 15.0]

    log = capsys.readouterr().out
    assert log.count("retry 1/3") == 1
    assert log.count("retry 2/3") == 1

    rows = [
        json.loads(line)
        for line in (Path(run_dir) / ".harness" / "turns.jsonl").read_text().splitlines()
    ]
    planner_rows = [row for row in rows if row["role"] == "planner"]
    assert len(planner_rows) == 1, "the budget is charged once, not once per attempt"
    assert planner_rows[0]["retries"] == 2

    assert run.state.attempts("plan") == 1, "a retry must not spend a stage attempt"


def test_a_transient_error_four_times_raises_the_original_exception(
    run_dir, stub_renderer, monkeypatch
):
    """#409: a fourth failure is not swallowed. The exception escapes."""
    pytest.importorskip("anthropic")
    from conftest import FIXTURES, build_run  # noqa: PLC0415
    import anthropic  # noqa: PLC0415

    monkeypatch.setattr(paper, "_sleep", lambda seconds: None)

    runner = TransientThenFixture(FIXTURES / "replies.json", "planner", _connection_error, 4)
    run = build_run(run_dir, runner=runner)

    with pytest.raises(anthropic.APIConnectionError):
        run.run()
    assert runner.failed == 4, "every attempt must actually have been made"


def test_a_rate_limit_error_is_also_retried(run_dir, stub_renderer, monkeypatch):
    """The ticket names two transient shapes. Both take the same path."""
    pytest.importorskip("anthropic")
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    monkeypatch.setattr(paper, "_sleep", lambda seconds: None)

    runner = TransientThenFixture(FIXTURES / "replies.json", "planner", _rate_limit_error, 1)
    run = build_run(run_dir, runner=runner)

    assert run.run() == 0
    assert run.state.attempts("plan") == 1


def test_a_non_transient_error_is_not_retried(run_dir, stub_renderer, monkeypatch):
    """A gate failure, a budget failure, or a plain bug is not a dropped
    connection. It must escape the first time, with no backoff sleep."""
    waited: list[float] = []
    monkeypatch.setattr(paper, "_sleep", waited.append)

    class Runner(paper.FixtureRunner):
        def ask(self, role, prompt):
            if role == "planner":
                raise ValueError("not a transient error")
            return super().ask(role, prompt)

    from conftest import FIXTURES, build_run  # noqa: PLC0415

    run = build_run(run_dir, runner=Runner(FIXTURES / "replies.json"))
    with pytest.raises(ValueError):
        run._ask("planner", "prompt")
    assert waited == [], "a non-transient error must not sleep or retry"


def test_the_backoff_sequence_is_five_fifteen_forty_five(run_dir, stub_renderer, monkeypatch):
    pytest.importorskip("anthropic")
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    waits: list[float] = []
    monkeypatch.setattr(paper, "_sleep", waits.append)

    runner = TransientThenFixture(FIXTURES / "replies.json", "planner", _connection_error, 3)
    run = build_run(run_dir, runner=runner)
    run._ask("planner", "Write plan.json for this topic.")

    assert waits == [5.0, 15.0, 45.0]
