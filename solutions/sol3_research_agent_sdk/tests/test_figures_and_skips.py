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
