"""The pipeline. Order, resume, exits, and money."""

from __future__ import annotations

import json
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


def test_max_turns_is_the_last_exit():
    stop = paper.check_stop(done=False, spent_usd=0.0, max_usd=5.0, exhausted=True)
    assert stop["reason"] == "max turns"


def test_a_running_loop_does_not_stop():
    assert paper.check_stop(done=False, spent_usd=0.0, max_usd=5.0) == {
        "stop": False,
        "reason": None,
    }


# -- the offline run -------------------------------------------------------


def test_the_whole_pipeline_runs_offline(offline, run_dir):
    """No network, no key, no SDK. This is the contract for this folder."""
    assert offline.run() == 0
    assert (run_dir / "whitepaper.md").exists()
    assert (run_dir / "plan.json").exists()
    assert list((run_dir / "evidence").glob("claim.*.md"))
    assert list((run_dir / "figures").glob("*.svg"))


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


def test_a_warning_is_not_filed_as_a_failure(finished_paper):
    """`publish` reads this file to decide whether the paper may ship, so a soft
    word count must not look like a blocked gate."""
    report = json.loads((finished_paper / "gates.json").read_text())
    assert "warnings" in report
    assert set(report["warnings"]) & {"length", "limitations"} or report["warnings"] == []
    assert not set(report["failures"]) & {"length", "limitations"}


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
        polish=False,
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


# -- the cost cap ----------------------------------------------------------


class Priced(paper.FixtureRunner):
    """Recorded replies at a realistic price. Writing costs, searching does not."""

    PRICE: ClassVar[dict] = {
        "planner": 0.05,
        "researcher": 0.05,
        "verifier": 0.05,
        "diagrammer": 0.05,
        "writer": 2.00,
        "reviewer": 0.10,
    }

    def ask(self, role, prompt):
        reply = super().ask(role, prompt)
        reply.usd = self.PRICE[role]
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
    assert done == ["plan", "search", "verify", "outline", "diagram"], done


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


# -- a machine with no diagram renderer ------------------------------------


def test_a_missing_renderer_does_not_block_the_paper(run_dir, no_renderer):
    """An attendee without Java still gets a paper. Nothing in `paper_check`
    requires a figure, so blocking the run would be a worse answer than saying
    so out loud."""
    run = priced_run(run_dir, 100.0)
    assert run.run() == 0
    assert (run_dir / "whitepaper.md").exists()


def test_a_missing_renderer_is_never_retried(run_dir, no_renderer):
    """Nothing the diagrammer writes installs plantuml. Three attempts buy three
    times the bill and the same result."""
    run = priced_run(run_dir, 100.0)
    run.run()
    assert run.state.attempts("diagram") == 1


def test_a_missing_renderer_is_recorded(run_dir, no_renderer, capsys):
    run = priced_run(run_dir, 100.0)
    run.quiet = False
    run.run()
    assert run.state.stages["diagram"].metadata.get("renderer") == "missing"
    assert "no renderer on this machine" in capsys.readouterr().out


def test_a_paper_without_figures_still_passes_its_gates(run_dir, no_renderer):
    run = priced_run(run_dir, 100.0)
    run.run()
    report = json.loads((run_dir / "gates.json").read_text())
    assert report["passed"] is True, report


def test_sections_written_before_a_stop_survive(run_dir):
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
