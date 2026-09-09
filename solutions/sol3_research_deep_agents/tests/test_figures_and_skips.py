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


def test_two_similar_captions_are_not_a_caveat_once_repeat():
    """Two auto-described diagrams of the same paper share enough
    boilerplate wording to Jaccard-match each other; the `Figure N.`
    caption line itself is exempt from the scan that finds a repeat.
    """
    body = (
        "# On a topic\n\n"
        "## Discussion\n\nA point. [1]\n\n"
        "![a](figures/a_imagen.png)\n\n"
        "Figure 1. A flowchart diagram of Exit conditions, showing Turn ends, Done?.\n\n"
        "## Limitations\n\nA different point. [1]\n\n"
        "![b](figures/b_imagen.png)\n\n"
        "Figure 2. A sequence diagram of Exit conditions, showing Maker, Checker.\n"
    )
    assert "caveat_once" not in paper_check.check(body, ["https://a"]).signature()


def test_a_caption_is_exempt_from_noun_stack():
    """A caption is system-generated from a diagram's own node labels, not
    prose a writer composed; it is not held to the STE noun-cluster
    advisory the way a written sentence is.
    """
    assert paper_check.noun_stacks("Figure 1. A loop harness gate ledger diagram.") == []
    assert paper_check.noun_stacks("A loop harness gate ledger diagram.") != []


def test_two_figure_mentions_never_collide_on_caveat_once():
    """A mention sentence for two different figures must not shingle
    identically once each figure's own number is dropped (`WORD` ignores
    a bare digit), or the two figures' own mentions read as the same
    repeated sentence.
    """
    one = paper._figure_mention_sentence(
        1, "A flowchart diagram of Exit conditions, showing Turn ends, Done?."
    )
    two = paper._figure_mention_sentence(
        2, "A sequence diagram of Exit conditions, showing Maker, Checker."
    )
    assert one != two
    body = f"# On a topic\n\n## Discussion\n\n{one} [1]\n\n## Limitations\n\n{two} [1]\n"
    assert "caveat_once" not in paper_check.check(body, ["https://a"]).signature()


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


def test_stage_trim_restamps_the_diagram_guard(run_dir):
    """#464. `diagram` now runs before `trim`, so the guard `stage_diagram`
    wrote reflects the pre-trim draft. `stage_trim` re-hashes it to the
    post-trim text, so a resume that reproduces the same trimmed section
    does not look like a section changed and redraw a figure for nothing.
    """
    sections = [{"id": "discussion", "heading": "Discussion", "figures": ["fig"]}]
    run = _paper(run_dir, Fixture(), sections)
    run.written = {"Discussion": "A point about the loop. [1]"}
    run.figures = [StubFigure("fig", alt="A diagram of the loop")]
    stale_sha = "stale-sha-from-before-the-trim"
    (run.work_dir / "diagrams.json").write_text(
        json.dumps({"figures": [{"name": "fig"}], "sections_sha": stale_sha}), encoding="utf-8"
    )

    run.stage_trim()

    guard = json.loads((run.work_dir / "diagrams.json").read_text())
    assert guard["sections_sha"] != stale_sha
    assert guard["sections_sha"] == paper._sections_sha(run.written)
    assert guard["figures"] == [{"name": "fig"}]


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
    outline = {
        "sections": [
            {"id": "discussion", "heading": "Discussion", "figures": []},
            {"id": "limitations", "heading": "Limitations", "figures": []},
        ]
    }
    written = {"Discussion": "A point. [1]", "Limitations": "A different point. [1]"}
    skips = [{"name": "token-cost", "section": "discussion", "reason": "no data"}]
    body = paper.stages.assemble(_plan(), outline, written, [], led, skipped_figures=skips)
    sections = paper_check.top_level_sections(body)
    assert "token-cost" in sections["discussion"]
    assert "no data" in sections["discussion"]
    assert "![" not in sections["discussion"]
    # Under the owning section, not merely somewhere on the page.
    assert "token-cost" not in sections["limitations"]
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


# -- PR #534 judge follow-ups ------------------------------------------


def test_captioned_fails_a_duplicate_figure_number():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n"
        "![a](figures/a_imagen.png)\n\nFigure 1. a\n\n"
        "## Limitations\n\nA different point [1].\n\n"
        "![b](figures/b_imagen.png)\n\nFigure 1. b\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "captioned" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "captioned")
    assert "not contiguous" in row.detail


def test_figure_referenced_mention_is_word_bounded():
    body = (
        "# T\n\n## Discussion\n\nSee Figure 12 for context. [1]\n\n"
        "![a](figures/a_imagen.png)\n\nFigure 1. a\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "figure_referenced" in score.signature(), score.report()


def test_drop_dangling_figure_mentions_preserves_a_same_block_figure_line():
    """#464 F2. The same block-flattening defect item (d) fixed elsewhere:
    dropping a dangling sentence must not sweep a same-block image line
    into the join.
    """
    body = (
        "# T\n\n## Discussion\n\nA point about the loop. Figure 3 shows this.\n"
        "![fig](figures/fig_imagen.png)\n"
    )
    result = paper_check.drop_dangling_figure_mentions(body, valid_numbers=set())
    discussion = paper_check.top_level_sections(result)["discussion"]
    lines = [line for line in discussion.splitlines() if line.strip()]
    assert lines[-1] == "![fig](figures/fig_imagen.png)"
    assert "Figure 3" not in discussion


def test_skip_noted_grades_the_reason_and_the_section():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n> token-cost was not shown: no data.\n\n"
        "## Limitations\n\nA different point [1].\n"
    )
    score = paper_check.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "a different reason"}],
    )
    assert "skip_noted" in score.signature(), score.report()
    score = paper_check.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "limitations", "reason": "no data"}],
    )
    assert "skip_noted" in score.signature(), score.report()


def test_a_caption_and_a_skip_note_do_not_count_toward_length_or_has_body():
    # "T" and "Discussion" are the only two words that are not inside a
    # caption or a skip note: the title and the section heading.
    body = (
        "# T\n\n## Discussion\n\nFigure 1. A description of the loop with plenty of words in it.\n\n"
        "> a-chart was not shown: no data.\n"
    )
    assert paper_check.word_count(body) == 2
    assert paper_check.sections_without_prose(body, min_words=1) == ["Discussion (0 words)"]


def test_a_back_reference_matches_the_whole_heading():
    """#464 F6. A substring match let a short heading ("AB") claim the
    exemption from inside an unrelated longer word ("Cable"): a sentence
    naming "Cable Routing", not a real heading, still repeats.
    """
    caveat = "This exact same specific finding restates fully across sections."
    body = (
        "# On a topic\n\n"
        "## AB\n\nAn unrelated finding here. [1]\n\n"
        f"## Limitations\n\nAs stated in Cable Routing, {caveat} [1]\n\n"
        f"## Conclusion\n\nAs stated in Cable Routing, {caveat} [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()


def test_stage_trim_spends_no_turn_when_every_figure_is_already_named(run_dir):
    """#464 F5. Once every placed figure is already named and there is no
    repeat and no dangling mention, the pass has no work: it must not
    spend a writer turn on every attempt regardless.
    """

    class Boom:
        name = "deep_agents"

        def ask(self, role, prompt):
            raise AssertionError("nothing to do; the model must not be asked")

    sections = [{"id": "discussion", "heading": "Discussion", "figures": ["fig"]}]
    run = _paper(run_dir, Boom(), sections)
    run.written = {"Discussion": "A point about the loop. Figure 1 shows the loop. [1]"}
    run.figures = [StubFigure("fig", alt="A diagram of the loop")]

    result = run.stage_trim()
    assert result.summary == "no repeat, no figure"
    assert result.artifacts == {}
    assert result.usd == 0.0
