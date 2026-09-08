"""P9: one caveat per finding, and a real whole-paper editor. #477."""

from __future__ import annotations

import json
from pathlib import Path

import checks
import paper


def test_the_same_caveat_in_three_sections_fails():
    caveat = (
        "A single non-arxiv source reported this finding and it should not "
        "be generalized."
    )
    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{caveat} [1]\n\n"
        f"## Limitations\n\n{caveat} [1]\n\n"
        f"## Conclusion\n\n{caveat} [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "caveat_once")
    assert "discussion" in row.detail.lower()
    assert "limitations" in row.detail.lower()
    assert "conclusion" in row.detail.lower()


def test_a_numeric_finding_in_full_twice_fails():
    body = (
        "# On a topic\n\n"
        "## Results\n\n"
        "The treatment group improved by 2.4 percent versus 1.4 percent in "
        "the control group. [1]\n\n"
        "## Discussion\n\n"
        "Across every measure, the study reported a 2.4 percent gain "
        "compared to a 1.4 percent gain among controls. [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()


def test_a_referring_phrase_is_not_a_repeat():
    body = (
        "# On a topic\n\n"
        "## Results\n\n"
        "A single non-arxiv source reported this finding and it should not "
        "be generalized. [1]\n\n"
        "## Discussion\n\n"
        "As in the same trial, above, the effect remained modest. [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def test_the_abstract_may_restate_a_finding_but_two_body_sections_may_not():
    caveat = (
        "A single non-arxiv source reported this finding and it should not "
        "be generalized."
    )
    body = (
        "# On a topic\n\n"
        f"## Abstract\n\n{caveat} [1]\n\n"
        "## Discussion\n\n"
        "This section is about something else entirely, at real length. [1]\n\n"
        "## Conclusion\n\n"
        "This section closes the paper with a different point altogether. [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()

    body_two_body_sections = (
        "# On a topic\n\n"
        f"## Discussion\n\n{caveat} [1]\n\n"
        f"## Conclusion\n\n{caveat} [1]\n"
    )
    score2 = checks.check(body_two_body_sections, ["https://a"])
    assert "caveat_once" in score2.signature(), score2.report()


def test_a_key_question_subheading_is_not_a_repeat_of_its_own_parent():
    """`section_bodies` nests a `###` sub-heading's text inside its `##`
    parent's span, by design, for every other row. Handed that split,
    `caveat_once` graded the sub-heading's own sentence against the copy of
    itself sitting inside the parent's span and called it a repeat.
    `top_level_sections` is the fix: only `##` headings are sections.
    """
    body = (
        "# On a topic\n\n"
        "## Introduction\n\n"
        "Three exits cover the observed cases. [1]\n\n"
        "### What stops the loop from running forever\n\n"
        "A rubric computed in code decides when the loop stops. [1]\n\n"
        "## Limitations\n\n"
        "This paper measures two runtimes only. [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def _run(work: Path, turns_cls) -> paper.Run:
    (Path(work) / "sources.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (Path(work) / "claims.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns_cls(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )


def test_a_whole_paper_pass_clears_caveat_once(work, turns):
    caveat = (
        "A single non-arxiv source reported this finding and it should not "
        "be generalized."
    )
    original = (
        "# On a topic\n\n"
        f"## Discussion\n\n{caveat} [1]\n\n"
        f"## Conclusion\n\n{caveat} [1]\n"
    )

    class Trimmer(turns):
        def edit_whole_paper(self, body, repeats, figures=None):
            # The whole body is handed to one turn, not one call per
            # section: proven by recording the call and checking it saw
            # both headings at once.
            self.asked.append(("edit_whole_paper", body, repeats, figures))
            return body.replace(f"\n\n{caveat} [1]\n\n## Conclusion", "\n\n## Conclusion", 1)

    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, Trimmer)

    repeats = checks.repeat_shingles(checks.section_bodies(original))
    assert repeats, "the fixture body must actually repeat, or this test proves nothing"

    result = paper.edit_whole_paper(run, repeats)
    assert result == {"trimmed": True, "reverted": []}

    calls = [item for item in run.turns.asked if item[0] == "edit_whole_paper"]
    assert len(calls) == 1
    _, seen_body, seen_repeats, seen_figures = calls[0]
    assert "## Discussion" in seen_body and "## Conclusion" in seen_body
    assert seen_repeats == repeats
    assert seen_figures == []

    after = (Path(work) / "paper.md").read_text(encoding="utf-8")
    assert not checks.caveat_once_violations(after)


def test_the_whole_paper_pass_reverts_an_invented_specific(work, turns):
    caveat = (
        "A single non-arxiv source reported this finding and it should not "
        "be generalized."
    )
    original = (
        "# On a topic\n\n"
        f"## Discussion\n\n{caveat} [1]\n\n"
        f"## Conclusion\n\n{caveat} [1]\n"
    )

    class Inventor(turns):
        def edit_whole_paper(self, body, repeats, figures=None):
            trimmed = body.replace(f"\n\n{caveat} [1]\n\n## Conclusion", "\n\n## Conclusion", 1)
            return trimmed + "\n\nPython 9.9 shipped in 2099. [1]\n"

    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, Inventor)

    repeats = checks.repeat_shingles(checks.section_bodies(original))
    result = paper.edit_whole_paper(run, repeats)
    assert result["trimmed"] is False
    assert "2099" in result["reverted"]

    after = (Path(work) / "paper.md").read_text(encoding="utf-8")
    assert after == original
