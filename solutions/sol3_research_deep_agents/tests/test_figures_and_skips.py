"""P10: captions, in-text references, and named skips. #464 #413 #386.

Also the PR #523/#531 judge follow-ups that could not land in a single
`paper_check.py` unit test: item (e), a skipped figure never demands a
mention and a stale one is removed. Items (a), (c), and (d) live in
`test_caveat_once.py`, beside the back-reference machinery they change.
"""

from __future__ import annotations

import json

import evidence
import paper
import paper_check
import research


class StubFigure:
    """A judged, publication-ready figure, the shape `figure_block` needs."""

    def __init__(self, name, alt=None):
        self.name = name
        self.alt = alt or f"A diagram of {name}"
        self.polished = True
        self.png = type("P", (), {"name": f"{name}_imagen.png"})()

    @property
    def best(self):
        return self.png


def _plan():
    return {"title": "On a topic"}


def _outline(sections):
    return {"sections": sections}


def _ledger():
    led = evidence.Ledger(":memory:")
    source = led.add_source(
        evidence.SourceDocument(title="a", url="https://example.invalid/doc", subject="x")
    )
    led.add_claim(evidence.Claim(text="A claim.", subject="x", source_ids=[source.id]))
    return led


def _paper(work_dir, runner, sections) -> paper.Paper:
    p = paper.Paper(
        topic="a topic",
        runner=runner,
        backend=research.FixtureBackend(work_dir / "no-such-fixture.json"),
        work_dir=work_dir,
        quiet=True,
        loop_doctrine=False,
    )
    p.plan = _plan()
    p.outline = _outline(sections)
    p.ledger = _ledger()
    return p


class Fixture:
    name = "fixture"

    def ask(self, role, prompt):
        raise AssertionError("the fixture branch must not call a model")


# -- captioned --------------------------------------------------------------


def test_an_image_without_a_caption_fails():
    body = "# T\n\n## Discussion\n\nA point [1].\n\n![fig](figures/fig_imagen.png)\n"
    score = paper_check.check(body, ["https://a"])
    assert "captioned" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "captioned")
    assert "fig_imagen.png" in row.detail


def test_figures_are_numbered_in_body_order():
    led = _ledger()
    outline = {
        "sections": [
            {"id": "discussion", "heading": "Discussion", "figures": ["fig-a"]},
            {"id": "limitations", "heading": "Limitations", "figures": ["fig-b"]},
        ]
    }
    written = {"Discussion": "A point. [1]", "Limitations": "A different point. [1]"}
    figures = [StubFigure("fig-a"), StubFigure("fig-b")]
    body = paper.stages.assemble(_plan(), outline, written, figures, led)
    placed = paper_check.placed_figures(body)
    assert [f["number"] for f in placed] == [1, 2]
    assert placed[0]["section"] == "discussion"
    assert placed[1]["section"] == "limitations"


# -- figure_referenced --------------------------------------------------


def test_a_figure_never_named_in_prose_fails():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n"
        "![fig](figures/fig_imagen.png)\n\nFigure 1. fig\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "figure_referenced" in score.signature(), score.report()


def test_the_whole_paper_pass_adds_the_figure_mention(run_dir):
    sections = [{"id": "discussion", "heading": "Discussion", "figures": ["fig"]}]
    run = _paper(run_dir, Fixture(), sections)
    run.written = {"Discussion": "A point about the loop. [1]"}
    run.figures = [StubFigure("fig", alt="A diagram of the loop")]

    preview = paper.stages.assemble(run.plan, run.outline, run.written, run.figures, run.ledger)
    assert "figure_referenced" in paper_check.check(preview, ["https://a"]).signature()

    result = run.stage_trim()
    assert result.artifacts["trimmed"] is True
    assert "Figure 1" in run.written["Discussion"]


def test_figure_referenced_never_demands_a_skipped_figures_mention():
    body = "# T\n\n## Discussion\n\nA point [1].\n"
    score = paper_check.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "no data"}],
    )
    assert "figure_referenced" not in score.signature(), score.report()


def test_the_whole_paper_pass_drops_a_dangling_figure_mention(run_dir):
    """#531. A "Figure 3" mention an earlier attempt added survives in
    `self.written` alone (no image, no caption line lives there), but this
    attempt's own figure list no longer has a number 3: the pass drops it.
    """
    sections = [{"id": "discussion", "heading": "Discussion", "figures": []}]
    run = _paper(run_dir, Fixture(), sections)
    run.written = {"Discussion": "A point about the loop. Figure 3 shows the same idea. [1]"}
    run.figures = []

    result = run.stage_trim()
    assert result.artifacts["trimmed"] is True
    assert "Figure 3" not in run.written["Discussion"]


# -- skip_noted -----------------------------------------------------------


def test_a_skipped_figure_with_no_note_fails():
    body = "# T\n\n## Discussion\n\nA point [1].\n"
    score = paper_check.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "no data"}],
    )
    assert "skip_noted" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "skip_noted")
    assert "token-cost" in row.detail


def test_a_skipped_figure_is_named_with_its_reason():
    led = _ledger()
    outline = {"sections": [{"id": "discussion", "heading": "Discussion", "figures": []}]}
    written = {"Discussion": "A point. [1]"}
    skips = [{"name": "token-cost", "section": "discussion", "reason": "no data"}]
    body = paper.stages.assemble(_plan(), outline, written, [], led, skipped_figures=skips)
    discussion = paper_check.top_level_sections(body)["discussion"]
    assert "token-cost" in discussion
    assert "no data" in discussion
    assert "![" not in discussion
    score = paper_check.check(body, ["https://a"], skipped_figures=skips)
    assert "skip_noted" not in score.signature(), score.report()


def test_a_skipped_diagram_from_a_failed_backend_is_named(run_dir):
    """#531. `stage_diagram`'s backend-failure record (`reason` prefixed
    `BACKEND_FAILURE_MARK`, `section` the owning section it captured
    before dropping the reference) is named the same way a skipped chart
    is.
    """
    sections = [{"id": "discussion", "heading": "Discussion", "figures": []}]
    run = _paper(run_dir, Fixture(), sections)
    (run.work_dir / "diagrams.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "name": "control-loop",
                        "attempts": 1,
                        "dropped": False,
                        "section": "discussion",
                        "reason": "image backend unavailable: 503 from the backend",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    skipped = run._skipped_figures()
    assert skipped == [
        {
            "name": "control-loop",
            "section": "discussion",
            "reason": "image backend unavailable: 503 from the backend",
        }
    ]


def test_an_old_bare_name_skip_list_still_loads(run_dir):
    sections = [{"id": "discussion", "heading": "Discussion", "figures": []}]
    run = _paper(run_dir, Fixture(), sections)
    (run.work_dir / "charts.json").write_text(
        json.dumps({"charts": [], "skipped": ["token-cost-multipliers"]}), encoding="utf-8"
    )
    assert run._skipped_charts() == [
        {"name": "token-cost-multipliers", "section": "", "reason": "no data"}
    ]
