"""P9: one caveat per finding, and a real whole-paper editor. #477."""

from __future__ import annotations

import paper
import paper_check


CAVEAT = (
    "A single non-arxiv source reported this finding and it should not be "
    "generalized."
)


def test_the_same_caveat_in_three_sections_fails():
    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Limitations\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
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
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()


def test_a_referring_phrase_is_not_a_repeat():
    body = (
        "# On a topic\n\n"
        f"## Results\n\n{CAVEAT} [1]\n\n"
        "## Discussion\n\n"
        "As in the same trial, above, the effect remained modest. [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def test_the_abstract_may_restate_a_finding_but_two_body_sections_may_not():
    body = (
        "# On a topic\n\n"
        f"## Abstract\n\n{CAVEAT} [1]\n\n"
        "## Discussion\n\n"
        "This section is about something else entirely, at real length. [1]\n\n"
        "## Conclusion\n\n"
        "This section closes the paper with a different point altogether. [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()

    two_body_sections = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )
    score2 = paper_check.check(two_body_sections, ["https://a"])
    assert "caveat_once" in score2.signature(), score2.report()


def test_a_key_question_subheading_is_not_a_repeat_of_its_own_parent():
    """A `###` sub-heading nests inside its `##` parent's span for every
    other row. Handed that split, `caveat_once` graded the sub-heading's own
    sentence against the copy of itself sitting inside the parent's span and
    called it a repeat. `top_level_sections` is the fix: only `##` headings
    are sections.
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
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def _paper(work_dir, runner) -> paper.Paper:
    import research  # noqa: PLC0415

    return paper.Paper(
        topic="a topic",
        runner=runner,
        backend=research.FixtureBackend(work_dir / "no-such-fixture.json"),
        work_dir=work_dir,
        quiet=True,
        loop_doctrine=False,
    )


def test_a_whole_paper_pass_clears_caveat_once(run_dir):
    original = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )
    asked = []

    class Trimmer:
        name = "deep_agents"

        def ask(self, role, prompt):
            # One turn sees the whole body, not one call per section: proven
            # by recording the call and checking it saw both headings.
            asked.append((role, prompt))
            trimmed = prompt.split("The paper body, already assembled:\n", 1)[1]
            trimmed = trimmed.replace(f"\n\n{CAVEAT} [1]\n\n## Conclusion", "\n\n## Conclusion", 1)
            return paper.Reply(text=trimmed)

    run = _paper(run_dir, Trimmer())
    run.paper_path.write_text(original, encoding="utf-8")

    repeats = paper_check.repeat_shingles(paper_check.top_level_sections(original))
    assert repeats, "the fixture body must actually repeat, or this test proves nothing"

    result = run.stage_trim(repeats)
    assert result.artifacts == {"trimmed": True, "reverted": []}
    assert len(asked) == 1
    assert asked[0][0] == "writer"
    assert "## Discussion" in asked[0][1] and "## Conclusion" in asked[0][1]

    after = run.paper_path.read_text(encoding="utf-8")
    assert not paper_check.caveat_once_violations(after)


def test_the_whole_paper_pass_reverts_an_invented_specific(run_dir):
    """Proves the copied `new_claims`: an invented number in the edited
    body reverts the body, not only the trim.
    """
    original = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )

    class Inventor:
        name = "deep_agents"

        def ask(self, role, prompt):
            trimmed = prompt.split("The paper body, already assembled:\n", 1)[1]
            trimmed = trimmed.replace(f"\n\n{CAVEAT} [1]\n\n## Conclusion", "\n\n## Conclusion", 1)
            return paper.Reply(text=trimmed + "\n\nPython 9.9 shipped in 2099. [1]\n")

    run = _paper(run_dir, Inventor())
    run.paper_path.write_text(original, encoding="utf-8")

    repeats = paper_check.repeat_shingles(paper_check.top_level_sections(original))
    result = run.stage_trim(repeats)
    assert result.artifacts["trimmed"] is False
    assert "2099" in result.artifacts["reverted"]

    after = run.paper_path.read_text(encoding="utf-8")
    assert after == original


def test_new_claims_is_copied_and_working():
    """DA had no whole-paper edit pass before P9, so `new_claims` and
    `_specifics` are copied here from the SDK port. #477.
    """
    before = "The loop checks done first. [1]"
    after = "The loop checks done first. Python 3.13 shipped in 2024. [1]"
    novel = paper_check.new_claims(before, after)
    assert "3.13" in novel
    assert "2024" in novel
    assert paper_check.new_claims(before, before) == []
