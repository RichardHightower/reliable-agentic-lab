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


def test_a_back_reference_is_not_a_repeat():
    """D2, #477. The whole-paper pass replaces a repeat with a short
    sentence that points back to the section stating it first. That
    sentence is not itself a repeat, even when the exact same short
    sentence appears in two sections pointing at the same source.
    """
    body = (
        "# On a topic\n\n"
        "## Discussion\n\n"
        "A single non-arxiv source reported this finding and it should not "
        "be generalized. [1]\n\n"
        "## Limitations\n\n"
        "As stated in Discussion, this point also holds here. [1]\n\n"
        "## Conclusion\n\n"
        "As stated in Discussion, this point also holds here. [1]\n"
    )
    score = checks.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def test_the_offline_dedup_keeps_the_first_and_never_leaves_a_bare_marker():
    """B4, #477. Three sections restate the same sentence. The first stays,
    in full, exactly where it was; the other two become a back reference,
    never a deletion, so no paragraph is left as only a citation marker.
    """
    import turns as turns_mod  # noqa: PLC0415

    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Limitations\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )
    repeats = checks.repeat_shingles(checks.top_level_sections(body))
    offline = turns_mod.OfflineTurns(backend=None)
    edited = offline.edit_whole_paper(body, repeats)

    sections = checks.top_level_sections(edited)
    assert sections["discussion"].strip() == f"{CAVEAT} [1]"
    for name in ("limitations", "conclusion"):
        text = sections[name].strip()
        assert text not in ("", "[1]")
        assert CAVEAT not in text
        assert text.lower().startswith("as stated in")
    assert not checks.caveat_once_violations(edited)


CAVEAT = (
    "A single non-arxiv source reported this finding and it should not "
    "be generalized."
)


def _run(work: Path, turns_cls) -> paper.Run:
    """A run with a two-section outline (`Discussion`, `Conclusion`), a
    section file per section holding the caveat, and an assembled `paper.md`
    built from them the same way `assemble` would. Real enough for
    `_persist_trim` to find the sections it writes back to, and for
    `assemble` to prove the trim survives a rebuild.
    """
    (Path(work) / "sources.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (Path(work) / "claims.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    (Path(work) / "outline.approved.json").write_text(
        json.dumps(
            {
                "outline": {
                    "title": "On a topic",
                    "sections": [
                        {"id": "discussion", "heading": "Discussion", "key_questions": []},
                        {"id": "conclusion", "heading": "Conclusion", "key_questions": []},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    sections = Path(work) / "sections"
    sections.mkdir(exist_ok=True)
    (sections / "discussion.md").write_text(f"{CAVEAT} [1]\n", encoding="utf-8")
    (sections / "conclusion.md").write_text(f"{CAVEAT} [1]\n", encoding="utf-8")
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns_cls(root=work),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        log=lambda *a: None,
    )


def _original_body() -> str:
    return (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )


def test_a_whole_paper_pass_clears_caveat_once(work, turns):
    original = _original_body()

    class Trimmer(turns):
        def edit_whole_paper(self, body, repeats, figures=None):
            # The whole body is handed to one turn, not one call per
            # section: proven by recording the call and checking it saw
            # both headings at once.
            self.asked.append(("edit_whole_paper", body, repeats, figures))
            return body.replace(f"## Conclusion\n\n{CAVEAT} [1]", "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]", 1)

    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, Trimmer)

    repeats = checks.repeat_shingles(checks.top_level_sections(original))
    assert repeats, "the fixture body must actually repeat, or this test proves nothing"

    result = paper.edit_whole_paper(run, repeats)
    assert result == {"trimmed": True, "reverted": []}

    calls = [item for item in run.turns.asked if item[0] == "edit_whole_paper"]
    assert len(calls) == 1
    _, seen_body, seen_repeats, seen_figures = calls[0]
    assert "## Discussion" in seen_body and "## Conclusion" in seen_body
    assert seen_repeats == repeats
    assert seen_figures == []


def test_the_pass_persists_so_assemble_keeps_the_trim(work, turns):
    """P9 wiring bug: the pass used to edit only `paper.md`. `assemble`
    rebuilds `paper.md` from `sections/*.md` on every call, including the
    unrelated `edit_paper` flow pass that already runs after the first
    green check, so a trim that never reached the section files was undone
    by the next thing that called `assemble`. `_persist_trim` writes the
    edit back to `sections/discussion.md` and `sections/conclusion.md`, so
    a fresh `assemble` reproduces the trimmed body instead of the original.
    """
    original = _original_body()

    class Trimmer(turns):
        def edit_whole_paper(self, body, repeats, figures=None):
            return body.replace(f"## Conclusion\n\n{CAVEAT} [1]", "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]", 1)

    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, Trimmer)
    repeats = checks.repeat_shingles(checks.top_level_sections(original))

    result = paper.edit_whole_paper(run, repeats)
    assert result == {"trimmed": True, "reverted": []}

    # The section file that lost its caveat no longer carries it, in the
    # file `assemble` reads, not only in `paper.md`.
    assert CAVEAT not in (Path(work) / "sections" / "conclusion.md").read_text(encoding="utf-8")
    assert CAVEAT in (Path(work) / "sections" / "discussion.md").read_text(encoding="utf-8")

    # A completely fresh assemble, from the section files alone, still
    # clears the row: the trim did not only patch `paper.md` in place.
    paper.assemble(run)
    rebuilt = (Path(work) / "paper.md").read_text(encoding="utf-8")
    assert not checks.caveat_once_violations(rebuilt)
    assert rebuilt.count(CAVEAT) == 1


def test_the_whole_paper_pass_reverts_an_invented_specific(work, turns):
    original = _original_body()

    class Inventor(turns):
        def edit_whole_paper(self, body, repeats, figures=None):
            trimmed = body.replace(f"## Conclusion\n\n{CAVEAT} [1]", "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]", 1)
            return trimmed + "\n\nPython 9.9 shipped in 2099. [1]\n"

    (Path(work) / "paper.md").write_text(original, encoding="utf-8")
    run = _run(work, Inventor)

    repeats = checks.repeat_shingles(checks.top_level_sections(original))
    result = paper.edit_whole_paper(run, repeats)
    assert result["trimmed"] is False
    assert "2099" in result["reverted"]

    # Neither the assembled body nor the section file the pass would have
    # touched was changed: a reverted edit reverts everywhere.
    after = (Path(work) / "paper.md").read_text(encoding="utf-8")
    assert after == original
    assert CAVEAT in (Path(work) / "sections" / "conclusion.md").read_text(encoding="utf-8")


def test_sdk_turns_edit_whole_paper_prompt_carries_the_repeats_and_the_body():
    """F7, #477. `SdkTurns.edit_whole_paper` has no direct test today; this
    proves the turn sends the repeat list and the whole body to the
    `research-writer` agent, and returns its reply.
    """
    import turns as turns_mod  # noqa: PLC0415

    class Backend:
        def __init__(self, results):
            self.results = list(results)
            self.prompts = []

        def run(self, *, root, prompt, allow, **extra):
            self.prompts.append((prompt, allow, extra.get("output_format")))
            return self.results.pop(0)

    def result(**kwargs):
        from adapter import TurnResult  # noqa: PLC0415

        return TurnResult(**kwargs)

    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        f"## Conclusion\n\n{CAVEAT} [1]\n"
    )
    repeats = checks.repeat_shingles(checks.top_level_sections(body))
    backend = Backend([result(output="edited body")])
    turn = turns_mod.SdkTurns(backend=backend, work_dir=".")

    edited = turn.edit_whole_paper(body, repeats, figures=[])

    assert edited == "edited body"
    prompt, allow, _ = backend.prompts[0]
    assert not allow, "the turn only returns text; it does not write paper.md itself"
    assert "As stated in" in prompt
    assert "## Discussion" in prompt and "## Conclusion" in prompt
    assert repeats[0]["section"] in prompt
