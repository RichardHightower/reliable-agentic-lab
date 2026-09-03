"""The deterministic rows and the exits. No model votes on either."""

from __future__ import annotations

import checks
import gates


def test_the_self_checks_run(capsys):
    """`task checks` is the framework-free layer. Keep the two in step."""
    assert checks.demo() == 0
    assert gates.demo() == 0


def test_a_fabricated_identifier_is_caught(tmp_path):
    """A web search cannot refute a citation that was never published."""
    corpus = "we retrieved arXiv:2401.00001 and it says things"
    body = "A real point [1].\n\nAnother point, see arXiv:2999.99999 [1]."
    score = checks.check(body, ["https://a"], corpus=corpus)
    assert not score.passed
    assert score.signature() == ("sourced",)


def test_an_identifier_that_was_retrieved_passes(tmp_path):
    corpus = "we retrieved arXiv:2401.00001 and it says things"
    score = checks.check("A point, see arXiv:2401.00001 [1].", ["https://a"], corpus=corpus)
    assert score.passed, score.report()


def test_no_corpus_means_no_opinion():
    """Absent evidence, the check abstains rather than failing every paper."""
    assert checks.check("See arXiv:2999.99999 [1].", ["https://a"], corpus="").passed


def test_a_missing_figure_fails(tmp_path):
    (tmp_path / "there.png").write_bytes(b"x")
    good = checks.check("A point [1].\n\n![f](there.png)", ["https://a"], base_dir=tmp_path)
    assert good.passed, good.report()
    bad = checks.check("A point [1].\n\n![f](gone.png)", ["https://a"], base_dir=tmp_path)
    assert bad.signature() == ("images",)


def test_a_remote_figure_is_not_this_checks_problem(tmp_path):
    body = "A point [1].\n\n![f](https://example.invalid/x.png)"
    assert checks.check(body, ["https://a"], base_dir=tmp_path).passed


def test_the_signature_is_what_failed_not_how_it_was_worded():
    first = checks.check("Uncited.", [])
    second = checks.check("A different uncited sentence.", [])
    assert first.signature() == second.signature() == ("cited", "sources")


def test_a_stall_is_reported_before_the_budget():
    """The actionable reason, not the one that happens to fire first."""
    decision = gates.decide(
        passed=False, iteration=1, budget=1, signature=("a",), previous_signature=("a",)
    )
    assert decision.repeat_failure
    assert "not converging" in decision.reason


def test_cost_stops_before_the_iteration_count():
    decision = gates.decide(passed=False, iteration=1, budget=9, usd_left=0.0)
    assert decision.gate == gates.ESCALATE
    assert "money" in decision.reason


def test_a_paper_with_no_body_does_not_pass(tmp_path):
    """A live run produced exactly this and the rubric called it green: the
    abstract is exempt from `cited`, the reference list is intact, and there is
    no prose left to break any other row."""
    hollow = "# T\n\n## Abstract\n\nAn abstract.\n\n## References\n\n1. https://a"
    assert checks.check(hollow, ["https://a"]).passed, "nothing to be missing yet"
    scored = checks.check(hollow, ["https://a"], headings=["The problem", "The approach"])
    assert scored.signature() == ("complete",)
    assert "never written" in scored.report()


def test_every_written_section_satisfies_the_row():
    body = "# T\n\n## The problem\n\nA point [1].\n\n## References\n\n1. https://a"
    assert checks.check(body, ["https://a"], headings=["The problem"]).passed


def test_a_short_paper_fails_the_hard_length_gate():
    """A structurally green brief is not a paper. Length ships as a hard row."""
    body = "The system is fast [1]."
    score = checks.check(body, ["https://a"], min_words=checks.MIN_WORDS)
    assert "length" in score.signature()
    assert not score.passed


def test_a_thin_section_fails_has_body_when_the_floor_is_on():
    body = "# T\n\n## The problem\n\nA point [1].\n\n## References\n\n1. https://a"
    score = checks.check(body, ["https://a"], min_section_words=checks.MIN_SECTION_WORDS)
    assert "has_body" in score.signature()
    assert "The problem" in score.report()


def test_the_assembler_abstract_is_not_held_to_the_section_floor():
    body = "# T\n\n## Abstract\n\nA short summary.\n\n## The problem\n\n" + ("A point [1]. " * 40)
    score = checks.check(body, ["https://a"], min_section_words=checks.MIN_SECTION_WORDS)
    assert "has_body" not in score.signature(), score.report()


def test_the_paper_gate_requires_done_then_cost_then_max_turns_in_figure_one():
    body = (
        "# T\n\n## Control\n\n"
        "The paper exits on done, then cost, then max turns [1].\n\n"
        "![Figure 1: done, then cost, then max turns](exits_imagen.png)\n\n"
        "Figure 1 shows done, then cost, then max turns."
    )
    score = checks.check(
        body,
        ["https://docs.langchain.com/oss/python/langchain/overview"],
        enforce_source_policy=True,
        enforce_loop_doctrine=True,
    )
    assert score.passed, score.report()


def test_the_exit_order_may_live_in_the_caption_after_a_block_image():
    body = (
        "# T\n\n## Control\n\n"
        "The paper exits on done, then cost, then max turns [1].\n\n"
        "![Figure 1: control loop](exits_imagen.png)\n\n"
        "Figure 1 shows done, then cost, then max turns."
    )
    score = checks.check(
        body,
        ["https://docs.langchain.com/oss/python/langchain/overview"],
        enforce_source_policy=True,
        enforce_loop_doctrine=True,
    )
    assert score.passed, score.report()


def test_the_paper_gate_rejects_whichever_fires_first_and_blog_references():
    body = (
        "# T\n\n## Control\n\n"
        "The loop has five exits and stops whichever fires first [1].\n\n"
        "![Figure 1: budget and attempt cap](exits_imagen.png)\n\n"
        "Figure 1 shows budget and an attempt cap."
    )
    score = checks.check(
        body,
        ["https://deepwiki.com/example"],
        enforce_source_policy=True,
        enforce_loop_doctrine=True,
    )
    assert score.signature() == ("doctrine", "hosts")


def test_the_paper_gate_rejects_svg_and_plain_png_diagrams():
    body = (
        "# T\n\n## Control\n\n"
        "The paper exits on done, then cost, then max turns [1].\n\n"
        "![Figure 1: done, then cost, then max turns](exits_imagen.png)\n\n"
        "Figure 1 shows done, then cost, then max turns."
    )
    for target in ("exits.svg", "exits.png"):
        score = checks.check(
            body.replace("exits_imagen.png", target),
            ["https://docs.langchain.com/oss/python/langchain/overview"],
            enforce_source_policy=True,
            enforce_loop_doctrine=True,
        )
        assert "figure_assets" in score.signature()


def test_heading_case_and_depth_are_noise():
    assert checks.missing_sections("### the PROBLEM", ["The problem"]) == []
    assert checks.missing_sections("## A\n\ntext\n\n## B", ["A", "B"]) == []
