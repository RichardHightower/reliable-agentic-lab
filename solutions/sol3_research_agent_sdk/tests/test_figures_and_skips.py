"""P10: captions, in-text references, and named skips. #464 #413 #386.

Also the PR #523/#531 judge follow-ups that could not land in a single
`checks.py` unit test: item (e), a skipped figure never demands a mention
and a stale one is removed. Items (a), (c), and (d) live in
`test_caveat_once.py`, beside the back-reference machinery they change.
"""

from __future__ import annotations

import json
from pathlib import Path

import checks
import paper


def _run(work: Path, turns_cls, *, sections=None) -> paper.Run:
    """A run with a two-section outline, real enough for `assemble` and
    `edit_whole_paper` to read and write against.
    """
    sections = sections or [
        {"id": "discussion", "heading": "Discussion", "key_questions": []},
        {"id": "limitations", "heading": "Limitations", "key_questions": []},
    ]
    (Path(work) / "sources.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (Path(work) / "claims.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    (Path(work) / "outline.approved.json").write_text(
        json.dumps({"outline": {"title": "On a topic", "sections": sections}}),
        encoding="utf-8",
    )
    section_dir = Path(work) / "sections"
    section_dir.mkdir(exist_ok=True)
    for section in sections:
        (section_dir / f"{section['id']}.md").write_text("Body text. [1]\n", encoding="utf-8")
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns_cls(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )


# -- captioned --------------------------------------------------------------


def test_an_image_without_a_caption_fails():
    body = "# T\n\n## Discussion\n\nA point [1].\n\n![fig](diagrams/fig_imagen.png)\n"
    score = checks.check(body, ["https://a"])
    assert "captioned" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "captioned")
    assert "fig_imagen.png" in row.detail


def test_figures_are_numbered_in_body_order(work, turns):
    run = _run(work, turns)
    (Path(work) / "diagrams.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "name": "fig-a",
                        "section": "discussion",
                        "path": "diagrams/fig-a_imagen.png",
                        "caption": "Figure A.",
                    },
                    {
                        "name": "fig-b",
                        "section": "limitations",
                        "path": "diagrams/fig-b_imagen.png",
                        "caption": "Figure B.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    placed = checks.placed_figures(body)
    assert [f["number"] for f in placed] == [1, 2]
    assert placed[0]["section"] == "discussion"
    assert placed[1]["section"] == "limitations"


def test_a_caption_is_exempt_from_noun_stack():
    """A caption is system-generated from a diagram's own node labels, not
    prose a writer composed; it is not held to the STE noun-cluster
    advisory the way a written sentence is.
    """
    assert checks.noun_stacks("Figure 1. A loop harness gate ledger diagram.") == []
    assert checks.noun_stacks("A loop harness gate ledger diagram.") != []


def test_two_similar_captions_are_not_a_caveat_once_repeat():
    """Two auto-described diagrams of the same paper share enough
    boilerplate wording to Jaccard-match each other; the `Figure N.`
    caption line itself is exempt from the scan that finds a repeat.
    """
    body = (
        "# On a topic\n\n"
        "## Discussion\n\nA point. [1]\n\n"
        "![a](diagrams/a_imagen.png)\n\n"
        "Figure 1. A flowchart diagram of Exit conditions, showing Turn ends, Done?.\n\n"
        "## Limitations\n\nA different point. [1]\n\n"
        "![b](diagrams/b_imagen.png)\n\n"
        "Figure 2. A sequence diagram of Exit conditions, showing Maker, Checker.\n"
    )
    assert "caveat_once" not in checks.check(body, ["https://a"]).signature()


# -- figure_referenced --------------------------------------------------


def test_a_figure_never_named_in_prose_fails():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n"
        "![fig](diagrams/fig_imagen.png)\n\nFigure 1. fig\n"
    )
    score = checks.check(body, ["https://a"])
    assert "figure_referenced" in score.signature(), score.report()


def test_the_whole_paper_pass_adds_the_figure_mention(work, turns):
    import turns as turns_mod  # noqa: PLC0415

    original = (
        "# On a topic\n\n"
        "## Discussion\n\nA point about the loop. [1]\n\n"
        "![fig](diagrams/fig_imagen.png)\n\nFigure 1. fig\n\n"
        "## Limitations\n\nA different point. [1]\n"
    )
    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, lambda root: turns_mod.OfflineTurns(backend=None))
    figures = checks.placed_figures(original)
    assert figures == [{"number": 1, "section": "discussion", "caption": "fig"}]
    assert "figure_referenced" in checks.check(original, ["https://a"]).signature()

    result = paper.edit_whole_paper(run, [], figures)
    assert result == {"trimmed": True, "reverted": []}

    discussion = (Path(work) / "sections" / "discussion.md").read_text(encoding="utf-8")
    # In the prose, not only in the `Figure 1.` caption line the section
    # already carried: a naive "is Figure 1 already in this section"
    # check reads that caption as an existing mention and skips adding
    # one, the bug that shipped once already. #464.
    prose = discussion.split("![fig]", 1)[0]
    assert "Figure 1" in prose
    # Untouched: the pass adds a sentence, it does not touch the other
    # section's own file.
    limitations = (Path(work) / "sections" / "limitations.md").read_text(encoding="utf-8")
    assert "A different point." in limitations


def test_two_figure_mentions_never_collide_on_caveat_once():
    """A live run's two diagrams often carry near-identical boilerplate
    captions ("A flowchart diagram of <topic>, showing ..."). The mention
    sentence a whole-paper pass adds for each must not shingle identically
    once its own figure number is dropped (`WORD` ignores bare digits), or
    two different figures' own mentions read as the same repeated sentence.
    """
    import turns as turns_mod  # noqa: PLC0415

    one = turns_mod._figure_mention_sentence(
        1, "A flowchart diagram of Exit conditions, showing Turn ends, Done?."
    )
    two = turns_mod._figure_mention_sentence(
        2, "A sequence diagram of Exit conditions, showing Maker, Checker."
    )
    assert one != two
    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{one} [1]\n\n"
        f"## Limitations\n\n{two} [1]\n"
    )
    assert "caveat_once" not in checks.check(body, ["https://a"]).signature()


def test_figure_referenced_never_demands_a_skipped_figures_mention():
    body = "# T\n\n## Discussion\n\nA point [1].\n"
    score = checks.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "no data"}],
    )
    assert "figure_referenced" not in score.signature(), score.report()


def test_the_whole_paper_pass_drops_a_dangling_figure_mention(work, turns):
    import turns as turns_mod  # noqa: PLC0415

    original = (
        "# On a topic\n\n"
        "## Discussion\n\nA point about the loop. Figure 3 shows the same idea. [1]\n\n"
        "## Limitations\n\nA different point. [1]\n"
    )
    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, lambda root: turns_mod.OfflineTurns(backend=None))

    # Figure 3 is not in the current figure list at all: a mention an
    # earlier pass added for a diagram this attempt's own commissioning
    # then dropped (a claims mismatch, or #531's live-backend failure).
    result = paper.edit_whole_paper(run, [], [])
    assert result == {"trimmed": True, "reverted": []}

    discussion = (Path(work) / "sections" / "discussion.md").read_text(encoding="utf-8")
    assert "Figure 3" not in discussion


# -- skip_noted -----------------------------------------------------------


def test_a_skipped_figure_with_no_note_fails():
    body = "# T\n\n## Discussion\n\nA point [1].\n"
    score = checks.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "no data"}],
    )
    assert "skip_noted" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "skip_noted")
    assert "token-cost" in row.detail


def test_a_skipped_figure_is_named_with_its_reason(work, turns):
    run = _run(work, turns)
    (Path(work) / "charts.json").write_text(
        json.dumps(
            {
                "charts": [],
                "skipped": [
                    {"name": "token-cost", "section": "discussion", "reason": "no data"}
                ],
            }
        ),
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    discussion = checks.top_level_sections(body)["discussion"]
    assert "token-cost" in discussion
    assert "no data" in discussion
    # Not a fake image: the skip carries no `![...]` markup of its own.
    assert "![" not in discussion
    score = checks.check(body, ["https://a"], skipped_figures=paper._skipped_figures(run))
    assert "skip_noted" not in score.signature(), score.report()


def test_a_skipped_diagram_from_a_failed_backend_is_named(work, turns):
    """#531. `diagrams.draw` degrades a live backend failure to a named
    skip in `diagrams.json`, `path` empty and `misses` carrying the
    backend's own error. `assemble` names it the same way it names a
    skipped chart.
    """
    run = _run(work, turns)
    (Path(work) / "diagrams.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "name": "control-loop",
                        "section": "discussion",
                        "caption": "The control loop.",
                        "path": "",
                        "attempts": 1,
                        "misses": ["image backend unavailable: 503 from the backend"],
                        "dropped": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    discussion = checks.top_level_sections(body)["discussion"]
    assert "control-loop" in discussion
    assert "image backend unavailable" in discussion


def test_an_old_bare_name_skip_list_still_loads(work, turns):
    run = _run(work, turns)
    (Path(work) / "charts.json").write_text(
        json.dumps({"charts": [], "skipped": ["token-cost-multipliers"]}), encoding="utf-8"
    )
    skipped = paper._skipped_charts(run)
    assert skipped == [{"name": "token-cost-multipliers", "section": "", "reason": "no data"}]


# -- PR #534 judge follow-ups ------------------------------------------


def test_numbering_stays_contiguous_after_a_persisted_caption(work, turns):
    """#464 B2. `_persist_trim` writes a section's own image and caption
    line back into its file. A later `assemble` that reads that file must
    still charge that figure its number, or the next figure reuses it.
    """
    run = _run(work, turns)
    (Path(work) / "diagrams.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "name": "fig-a",
                        "section": "discussion",
                        "path": "diagrams/fig-a_imagen.png",
                        "caption": "Figure A.",
                    },
                    {
                        "name": "fig-b",
                        "section": "limitations",
                        "path": "diagrams/fig-b_imagen.png",
                        "caption": "Figure B.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    assert [f["number"] for f in checks.placed_figures(body)] == [1, 2]

    # Simulate `_persist_trim`: the "Discussion" section's own file now
    # carries its image and `Figure 1.` caption line, exactly as
    # `edit_whole_paper` would have written it back.
    discussion_block = checks.top_level_sections(body)["discussion"].strip()
    (Path(work) / "sections" / "discussion.md").write_text(discussion_block + "\n", encoding="utf-8")

    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text(encoding="utf-8")
    placed = checks.placed_figures(body)
    assert [f["number"] for f in placed] == [1, 2], placed
    assert not checks.captioned_violations(body)


def test_captioned_fails_a_duplicate_figure_number():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n"
        "![a](diagrams/a_imagen.png)\n\nFigure 1. a\n\n"
        "## Limitations\n\nA different point [1].\n\n"
        "![b](diagrams/b_imagen.png)\n\nFigure 1. b\n"
    )
    score = checks.check(body, ["https://a"])
    assert "captioned" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "captioned")
    assert "not contiguous" in row.detail


def test_figure_referenced_mention_is_word_bounded():
    body = (
        "# T\n\n## Discussion\n\nSee Figure 12 for context. [1]\n\n"
        "![a](diagrams/a_imagen.png)\n\nFigure 1. a\n"
    )
    score = checks.check(body, ["https://a"])
    assert "figure_referenced" in score.signature(), score.report()


def test_drop_dangling_figure_mentions_preserves_a_same_block_figure_line():
    """#464 F2. The same block-flattening defect item (d) fixed elsewhere:
    dropping a dangling sentence must not sweep a same-block image line
    into the join.
    """
    body = (
        "# T\n\n## Discussion\n\nA point about the loop. Figure 3 shows this.\n"
        "![fig](diagrams/fig_imagen.png)\n"
    )
    result = checks.drop_dangling_figure_mentions(body, valid_numbers=set())
    discussion = checks.top_level_sections(result)["discussion"]
    lines = [line for line in discussion.splitlines() if line.strip()]
    assert lines[-1] == "![fig](diagrams/fig_imagen.png)"
    assert "Figure 3" not in discussion


def test_skip_noted_grades_the_reason_and_the_section():
    body = (
        "# T\n\n## Discussion\n\nA point [1].\n\n> token-cost was not shown: no data.\n\n"
        "## Limitations\n\nA different point [1].\n"
    )
    # The name is on the page, under the right section, but the recorded
    # reason does not match what is actually printed.
    score = checks.check(
        body,
        ["https://a"],
        skipped_figures=[{"name": "token-cost", "section": "discussion", "reason": "a different reason"}],
    )
    assert "skip_noted" in score.signature(), score.report()
    # Named on the page, but recorded under a section that never carries it.
    score = checks.check(
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
    assert checks.word_count(body) == 2
    assert checks.sections_without_prose(body, min_words=1) == ["Discussion (0 words)"]


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
    score = checks.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()
