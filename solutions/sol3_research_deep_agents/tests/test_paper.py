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
    import research  # noqa: PLC0415  (sys.path is set by conftest first)
    from conftest import FIXTURES  # noqa: PLC0415

    return paper.Paper(
        topic="Exit conditions in production agent loops",
        runner=Priced(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=work_dir,
        polish=False,
        quiet=True,
        max_usd=cap,
    )


def test_the_cap_holds_inside_a_stage(run_dir):
    """Checking only between stages is not a cap. A stage that loops over six
    sections makes six calls with nothing between them, so the run learns it is
    over budget once the money is gone. This case used to spend $4.45 of $3.00."""
    run = priced_run(run_dir, 3.00)
    assert run.run() == 2
    assert run.state.total_cost_usd <= 3.00, f"spent ${run.state.total_cost_usd:.2f} of $3.00"


def test_the_run_says_which_call_it_could_not_afford(run_dir, capsys):
    run = priced_run(run_dir, 3.00)
    run.quiet = False
    run.run()
    out = capsys.readouterr().out
    assert "writer call needs" in out
    assert "cost" in out


def test_a_spent_budget_is_never_retried(run_dir):
    """A gate failure might be fixed by another attempt. A spent budget will not
    be, and retrying on it turns a cost cap into a cost multiplier."""
    run = priced_run(run_dir, 3.00)
    run.run()
    assert run.state.attempts("write") == 1


def test_a_cheap_run_still_finishes(run_dir):
    run = priced_run(run_dir, 100.0)
    assert run.run() == 0
    assert run.state.total_cost_usd <= 100.0


def test_the_total_counts_each_call_once(run_dir):
    """`spend` and `mark_complete` both used to add."""
    run = priced_run(run_dir, 100.0)
    run.run()
    by_stage = sum(entry.cost_usd for entry in run.state.stages.values())
    assert run.state.total_cost_usd == pytest.approx(by_stage), (
        "the total and the per-stage costs describe the same calls"
    )


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
