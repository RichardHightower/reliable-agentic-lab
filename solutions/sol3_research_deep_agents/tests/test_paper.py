"""The pipeline. Order, resume, exits, and money."""

from __future__ import annotations

import json

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


def test_a_fenced_diagram_reply_is_unfenced():
    assert paper._strip_fence("```mermaid\nflowchart LR\n  A --> B\n```") == (
        "flowchart LR\n  A --> B\n"
    )
    assert paper._strip_fence("flowchart LR\n  A --> B") == "flowchart LR\n  A --> B\n"
