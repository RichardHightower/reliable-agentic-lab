"""P9: one caveat per finding, and a real whole-paper editor. #477."""

from __future__ import annotations

import evidence
import paper
import paper_check
import research


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


def test_a_back_reference_is_not_a_repeat():
    """D2, #477. The whole-paper pass replaces a repeat with a short
    sentence that points back to the section stating it first. That
    sentence is not itself a repeat, even when the exact same short
    sentence appears in two sections pointing at the same source.
    """
    body = (
        "# On a topic\n\n"
        f"## Discussion\n\n{CAVEAT} [1]\n\n"
        "## Limitations\n\n"
        "As stated in Discussion, this point also holds here. [1]\n\n"
        "## Conclusion\n\n"
        "As stated in Discussion, this point also holds here. [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def test_a_fourteen_word_back_reference_is_not_a_repeat():
    """#521. The exemption used to cap at 12 words. The pass's own fixed
    frame around the source section's name is already 8 words, so naming
    a five-word heading produced a 13-to-14-word sentence that failed the
    very row the pass was written to clear, on a live model-written
    outline whose headings run longer than the offline fixtures' one or
    two words. The cue still carries the exemption; the cap is 24 now.

    #531. The exemption now also requires the sentence to name one of the
    paper's own `##` headings, so this section is renamed to the long
    heading the reference points at, rather than pointing at an invented
    name no `##` in the body actually carries.
    """
    heading = "Independent Verification Under Bounded Budgets"
    reference = f"As stated in {heading}, this specific point still applies here."
    assert len(paper_check.WORD.findall(reference)) == 14
    body = (
        "# On a topic\n\n"
        f"## {heading}\n\n{CAVEAT} [1]\n\n"
        "## Limitations\n\n"
        f"{reference} [1]\n\n"
        "## Conclusion\n\n"
        f"{reference} [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" not in score.signature(), score.report()


def test_a_back_reference_naming_no_real_heading_still_repeats():
    """#531. The cue phrase and the word cap are not enough on their own: a
    manufactured "See ..." sentence that names no `##` heading the paper
    actually carries is still a restatement wearing a pointer's opening
    words, not a pointer.
    """
    fake = "See the earlier analysis of this exact same point in full detail."
    body = (
        "# On a topic\n\n"
        "## Discussion\n\nAn unrelated finding here. [1]\n\n"
        f"## Limitations\n\n{fake} [1]\n\n"
        f"## Conclusion\n\n{fake} [1]\n"
    )
    score = paper_check.check(body, ["https://a"])
    assert "caveat_once" in score.signature(), score.report()


def test_non_adjacent_stacked_pointers_collapse():
    """#531. Two pointers stacked in one paragraph with an unrelated
    sentence between them still collapse: the comparison checks every
    already-kept piece, not only the one immediately before it.
    """
    pointer = "As stated in Discussion, this point also holds here."
    body = (
        "# On a topic\n\n"
        "## Discussion\n\nA point. [1]\n\n"
        f"## Conclusion\n\n{pointer} An unrelated sentence sits between them. {pointer} [1]\n"
    )
    collapsed = paper_check.collapse_repeated_back_references(body)
    conclusion = paper_check.top_level_sections(collapsed)["conclusion"]
    assert conclusion.count(pointer) == 1
    assert "An unrelated sentence sits between them." in conclusion


def test_collapse_never_flattens_a_same_block_figure_line():
    """#531. A `![figure]` line with no blank line separating it from the
    prose above stays on its own line; the sentence join around a
    collapsed pointer must not sweep it into the flow.
    """
    pointer = "As stated in Discussion, this point also holds here."
    body = (
        "# On a topic\n\n"
        "## Discussion\n\nA point. [1]\n\n"
        f"## Conclusion\n\n{pointer} {pointer}\n"
        "![fig](figures/fig_imagen.png)\n"
    )
    collapsed = paper_check.collapse_repeated_back_references(body)
    conclusion = paper_check.top_level_sections(collapsed)["conclusion"]
    lines = [line for line in conclusion.splitlines() if line.strip()]
    assert lines[-1] == "![fig](figures/fig_imagen.png)"
    assert conclusion.count(pointer) == 1


def test_top_level_section_spans_ignores_subheadings():
    """`top_level_section_spans` shares `top_level_sections`' own fix: only
    a `##` heading opens a new span, so a `###` key-question sub-heading
    stays inside its `##` parent's span rather than closing it early. No
    revert-matrix row named this function until #521.
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
    spans = paper_check.top_level_section_spans(body)
    sections = paper_check.top_level_sections(body)
    assert set(spans) == {"introduction", "limitations"}
    for name, (start, end) in spans.items():
        assert body[start:end] == sections[name]
    assert "### What stops the loop from running forever" in body[slice(*spans["introduction"])]


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
    """A `Paper` ready for `stage_trim` alone: a plan and an outline so
    `_need_written` does not go looking for `plan.json`/`outline.json`, one
    ledger claim so `_need_ledger` does not treat the run as evidence-free,
    and no `sections.json` on disk, so `self.written` is exactly what the
    test sets.
    """
    p = paper.Paper(
        topic="a topic",
        runner=runner,
        backend=research.FixtureBackend(work_dir / "no-such-fixture.json"),
        work_dir=work_dir,
        quiet=True,
        loop_doctrine=False,
    )
    p.plan = {"title": "On a topic"}
    p.outline = {"sections": []}
    source = p.ledger.add_source(
        evidence.SourceDocument(title="a", url="https://example.invalid/doc", subject="x")
    )
    p.ledger.add_claim(evidence.Claim(text="A claim.", subject="x", source_ids=[source.id]))
    return p


def test_a_whole_paper_pass_clears_caveat_once(run_dir):
    asked = []

    class Trimmer:
        name = "deep_agents"

        def ask(self, role, prompt):
            # One turn sees the whole body, not one call per section: proven
            # by recording the call and checking it saw both headings.
            asked.append((role, prompt))
            edited = prompt.split("The paper body:\n", 1)[1]
            edited = edited.replace(
                f"## Conclusion\n\n{CAVEAT} [1]",
                "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]",
                1,
            )
            return paper.Reply(text=edited)

    run = _paper(run_dir, Trimmer())
    run.written = {"Discussion": f"{CAVEAT} [1]", "Conclusion": f"{CAVEAT} [1]"}

    result = run.stage_trim()
    assert result.artifacts == {"trimmed": True, "reverted": []}
    assert len(asked) == 1
    assert asked[0][0] == "writer"
    assert "## Discussion" in asked[0][1] and "## Conclusion" in asked[0][1]

    assert run.written["Discussion"] == f"{CAVEAT} [1]"
    combined = f"# T\n\n## Discussion\n\n{run.written['Discussion']}\n\n## Conclusion\n\n{run.written['Conclusion']}\n"
    assert not paper_check.caveat_once_violations(combined)


def test_the_pass_persists_to_the_section_files(run_dir):
    """`stage_trim` runs before `stage_assemble` exists to call, so it must
    write `self.written` and `sections.json` itself; nothing downstream
    reassembles for it the way the SDK's `assemble` does.
    """

    class Trimmer:
        name = "deep_agents"

        def ask(self, role, prompt):
            edited = prompt.split("The paper body:\n", 1)[1]
            edited = edited.replace(
                f"## Conclusion\n\n{CAVEAT} [1]",
                "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]",
                1,
            )
            return paper.Reply(text=edited)

    run = _paper(run_dir, Trimmer())
    run.written = {"Discussion": f"{CAVEAT} [1]", "Conclusion": f"{CAVEAT} [1]"}
    run.stage_trim()

    import json  # noqa: PLC0415

    saved = json.loads((run.work_dir / "sections.json").read_text(encoding="utf-8"))
    assert CAVEAT not in saved["Conclusion"]
    assert CAVEAT in saved["Discussion"]


def test_the_fixture_backend_trims_without_a_model(run_dir):
    """B4/F2, #477. The offline fallback (`self.runner.name == "fixture"`)
    edits `self.written` directly: no whole-body search, so it cannot land
    on the wrong section's copy, and no empty or marker-only paragraph
    remains because the repeat is replaced, never deleted.
    """

    class Fixture:
        name = "fixture"

        def ask(self, role, prompt):
            raise AssertionError("the fixture branch must not call a model")

    run = _paper(run_dir, Fixture())
    run.written = {
        "Discussion": f"{CAVEAT} [1]",
        "Limitations": f"{CAVEAT} [1]",
        "Conclusion": f"{CAVEAT} [1]",
    }

    result = run.stage_trim()
    assert result.artifacts["trimmed"] is True

    # The first statement stands, in full, exactly where it already was.
    assert run.written["Discussion"] == f"{CAVEAT} [1]"
    # Neither later section is empty, whitespace, or a bare citation marker.
    for heading in ("Limitations", "Conclusion"):
        text = run.written[heading].strip()
        assert text not in ("", "[1]")
        assert CAVEAT not in text
        assert text.lower().startswith("as stated in")

    combined = (
        "# T\n\n## Discussion\n\n"
        + run.written["Discussion"]
        + "\n\n## Limitations\n\n"
        + run.written["Limitations"]
        + "\n\n## Conclusion\n\n"
        + run.written["Conclusion"]
        + "\n"
    )
    assert not paper_check.caveat_once_violations(combined)


def test_stacked_identical_back_references_collapse_to_one(run_dir):
    """#521. Two different sentences in Discussion are both restated, word
    for word, in Conclusion. Each becomes its own back reference to
    Discussion; pointed at the same source, the two pointers read
    identically, so the trim collapses the stack to the one pointer a
    reader needs. Covers both branches of `stage_trim`: the fixture branch
    edits each match in place, same as the SDK's offline twin.
    """
    caveat_two = (
        "The observed effect held for one cohort only and may not generalize."
    )

    class Fixture:
        name = "fixture"

        def ask(self, role, prompt):
            raise AssertionError("the fixture branch must not call a model")

    run = _paper(run_dir, Fixture())
    run.written = {
        "Discussion": f"{CAVEAT} {caveat_two} [1]",
        "Conclusion": f"{CAVEAT} {caveat_two} [1]",
    }

    result = run.stage_trim()
    assert result.artifacts["trimmed"] is True

    pointer = "As stated in Discussion, this point also holds here."
    assert run.written["Conclusion"].count(pointer) == 1


def test_the_whole_paper_pass_reverts_an_invented_specific(run_dir):
    """Proves the copied `new_claims`: an invented number in the edited
    body reverts the whole edit, not only the one section it touched.
    """

    class Inventor:
        name = "deep_agents"

        def ask(self, role, prompt):
            edited = prompt.split("The paper body:\n", 1)[1]
            edited = edited.replace(
                f"## Conclusion\n\n{CAVEAT} [1]",
                "## Conclusion\n\nAs stated in Discussion, this point also holds here. [1]",
                1,
            )
            return paper.Reply(text=edited + "\n\nPython 9.9 shipped in 2099. [1]\n")

    run = _paper(run_dir, Inventor())
    run.written = {"Discussion": f"{CAVEAT} [1]", "Conclusion": f"{CAVEAT} [1]"}

    result = run.stage_trim()
    assert result.artifacts["trimmed"] is False
    assert "2099" in result.artifacts["reverted"]
    assert run.written["Conclusion"] == f"{CAVEAT} [1]"


def test_the_fixture_pipeline_runs_the_trim_stage(run_dir, stub_renderer):
    """F2, #477. A whole run through `Paper.run()`, on the fixture backend,
    so CI exercises `STAGE_ORDER`'s new `trim` stage and its fixture branch,
    not only a direct `stage_trim()` call built by hand.
    """
    from conftest import FIXTURES, build_run  # noqa: PLC0415

    class RepeatingWriter(paper.FixtureRunner):
        """Every section the writer stage stamps carries the same caveat
        sentence, verbatim, so the written draft genuinely repeats it
        before `trim` ever runs.
        """

        def ask(self, role, prompt):
            reply = super().ask(role, prompt)
            if role == "writer" and "Revise the existing" not in prompt:
                import re  # noqa: PLC0415

                # Reuse a marker the section already cites, so the gate
                # that checks every marker against the section's own
                # allowed claims still passes: the point here is the
                # repeated sentence, not a fresh citation.
                marker = re.search(r"\[(\d+)\]", reply.text)
                cite = f" [{marker.group(1)}]" if marker else ""
                return paper.Reply(
                    text=f"{reply.text}\n\n{CAVEAT}{cite}\n", usd=reply.usd, data=reply.data
                )
            return reply

    run = build_run(run_dir, runner=RepeatingWriter(FIXTURES / "replies.json"), loop_doctrine=False)
    assert run.run() == 0

    body = run.paper_path.read_text(encoding="utf-8")
    assert not paper_check.caveat_once_violations(body)
    assert run.state.stages["trim"].metadata.get("trimmed") is True


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
