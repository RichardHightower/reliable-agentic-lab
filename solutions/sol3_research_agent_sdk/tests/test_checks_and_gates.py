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


def test_a_rendered_diagram_absent_from_the_paper_fails_images():
    """Zero links used to pass, because the row only validated links that exist."""
    body = "A point [1]."
    diagrams = [
        {
            "name": "loop-and-harness-architecture",
            "path": "diagrams/loop-and-harness-architecture_imagen.png",
        }
    ]
    score = checks.check(body, ["https://a"], diagrams=diagrams)
    assert score.signature() == ("images",), score.report()
    placed = checks.check(
        body + "\n\n![loop](diagrams/loop-and-harness-architecture_imagen.png)\n",
        ["https://a"],
        diagrams=diagrams,
    )
    assert "images" not in placed.signature(), placed.report()


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


def test_the_doctrine_row_is_absent_when_the_flag_is_off():
    """#406: off by default, any topic's paper is not held to the local exit
    doctrine, and the row is never even graded."""
    body = (
        "# T\n\n## Mechanism\n\n"
        "Creatine raises intramuscular phosphocreatine stores [1].\n\n"
        "## References\n\n1. https://docs.langchain.com/oss/python/langchain/overview\n"
    )
    score = checks.check(body, ["https://docs.langchain.com/oss/python/langchain/overview"])
    assert "doctrine" not in [c.name for c in score.checks]
    assert score.passed, score.report()


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


# -- the paper gate on its first real paper (#371, run 18) ---------------------


def test_hosts_allows_the_seed_and_the_admitted_list_together():
    """The librarian's list replaced the seed, and the seed is where the GitHub
    orgs live. The paper was rejected for citing the vendors' own repositories.
    """
    from checks import disallowed_reference_hosts  # noqa: PLC0415

    sources = ["https://github.com/anthropics/claude-code/issues/1", "https://arxiv.org/abs/1"]
    assert disallowed_reference_hosts(sources, ["arxiv.org"]) == []


def test_hosts_ignores_anything_that_is_not_a_url():
    from checks import disallowed_reference_hosts  # noqa: PLC0415

    sources = ["not-found", "research/source-assets/abc/original.md (corpus file)", "corpus:x"]
    assert disallowed_reference_hosts(sources, ["arxiv.org"]) == []
    assert disallowed_reference_hosts(["https://medium.com/x"], ["arxiv.org"]) == ["https://medium.com/x"]


def test_section_bodies_run_to_the_next_heading_of_the_same_or_higher_level():
    """A writer that names its questions as sub-headings has a section whose
    text is under those sub-headings. Ending at any heading found nothing.
    """
    from checks import section_bodies  # noqa: PLC0415

    body = "## One\n\n### Q1?\n\nanswer one\n\n### Q2?\n\nanswer two\n\n## Two\n\nprose two\n"
    bodies = section_bodies(body)
    assert "answer one" in bodies["one"] and "answer two" in bodies["one"]
    assert "prose two" not in bodies["one"]
    assert "prose two" in bodies["two"]


def test_outline_coverage_finds_a_question_named_under_a_subheading():
    from checks import outline_coverage_gaps  # noqa: PLC0415

    outline = {"sections": [{"heading": "One", "key_questions": [
        "What stops the loop? (Answered by the pack: knowledge:claim.x.01M0.)"]}]}
    body = "## One\n\n### What stops the loop?\n\nA rubric [1].\n"
    assert outline_coverage_gaps(body, outline) == []


def test_has_body_counts_the_prose_under_a_sections_subheadings():
    from checks import sections_without_prose  # noqa: PLC0415

    body = "## One\n\n### Q1?\n\n" + ("word " * 60) + "\n\n## Two\n\n" + ("word " * 60)
    assert sections_without_prose(body, 50) == []


def test_the_hosts_row_grades_only_the_references_the_caller_hands_it():
    """A located cabinet source is a public copy of a paper the brain held.

    The librarian was asked which hosts to search. It was never asked about
    arxiv.org, so the wall rejected the paper's own primary source. The
    `sources` row still counts every reference.
    """
    body = "# T\n\n## A\n\nA claim [1]. Another claim [2].\n"
    arxiv = "https://arxiv.org/abs/2503.13657"
    langchain = "https://docs.langchain.com/oss/python/langchain/overview"

    exempt = checks.check(
        body,
        [arxiv, langchain],
        enforce_source_policy=True,
        allowed_domains=(),
        host_sources=[langchain],
    )
    rows = {row.name: row for row in exempt.checks}
    assert rows["hosts"].passed, rows["hosts"]
    assert rows["sources"].detail == "2 sources retrieved", rows["sources"]

    walled = checks.check(
        body,
        [arxiv, langchain],
        enforce_source_policy=True,
        allowed_domains=(),
    )
    rows = {row.name: row for row in walled.checks}
    assert not rows["hosts"].passed, rows["hosts"]
    assert "arxiv.org" in rows["hosts"].detail, rows["hosts"]
    assert rows["sources"].detail == "2 sources retrieved", rows["sources"]


# -- P1, the STE belt: contractions, Latin abbreviations, noun stacks --------


def test_a_contraction_in_body_prose_fails():
    """`don't` fails `ste_language`, and the detail names the sentence."""
    body = "The writer doesn't skip a step [1]."
    score = checks.check(body, ["https://a"])
    assert "ste_language" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "ste_language")
    assert "doesn't" in row.detail
    assert "skip a step" in row.detail


def test_a_latin_abbreviation_fails():
    """`e.g.` fails, and a clean body still passes."""
    dirty = "The writer names the actor, e.g. the host [1]."
    score = checks.check(dirty, ["https://a"])
    assert "ste_language" in score.signature(), score.report()

    clean = "The writer names the actor, for example the host [1]."
    score = checks.check(clean, ["https://a"])
    assert "ste_language" not in score.signature(), score.report()


def test_four_nouns_in_a_row_fail():
    """`noun_stack` fires on a four-noun phrase. It is advisory (a deviation
    from #456, stated in the P1-fix PR body): it reports and never blocks the
    gate, so it never appears in `signature()` and never flips `passed`.
    """
    body = "A loop harness gate ledger ships every seminar [1]."
    score = checks.check(body, ["https://a"])
    assert "noun_stack" not in score.signature(), score.report()
    assert "noun_stack" in score.advisories(), score.report()
    row = next(c for c in score.checks if c.name == "noun_stack")
    assert not row.passed
    assert "loop harness gate ledger" in row.detail
    assert score.passed, "an advisory row never fails the gate"


def test_may_on_an_unverified_claim_still_passes():
    """STE-S9 stays off. A hedge on an unverified claim is not a procedure step."""
    body = "The approach may reduce cost on some workloads [1]."
    score = checks.check(body, ["https://a"])
    assert score.passed, score.report()


def test_a_contraction_inside_a_code_fence_passes():
    """The mask works: a contraction inside a fenced code block is not prose."""
    body = "A real point [1].\n\n```\nassert doesn't_exist == False\n```\n"
    score = checks.check(body, ["https://a"])
    assert "ste_language" not in score.signature(), score.report()


def test_a_genitive_is_not_a_contraction():
    """"the writer's card" is a possessive, not `it's`/`don't`."""
    body = "The writer's card names the actor [1]."
    score = checks.check(body, ["https://a"])
    assert "ste_language" not in score.signature(), score.report()


def test_the_recorded_fixture_paper_passes_the_ste_belt(tmp_path):
    """The paper `task demo` writes carries no contraction, no Latin
    abbreviation, and no four-noun stack. Same command as the Taskfile:
    `--backend fixture --fresh --brain tests/fixtures/brain`.
    """
    from pathlib import Path  # noqa: PLC0415

    import loop  # noqa: PLC0415

    folder = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    code = loop.main(
        [
            "--topic", "loop engineering exit criteria",
            "--out", str(work),
            "--backend", "fixture",
            "--brain", str(folder / "tests" / "fixtures" / "brain"),
            "--fresh",
        ]
    )
    assert code == 0, "the recorded fixture must still assemble and pass its gate"
    body = (work / "paper.md").read_text(encoding="utf-8")
    assert checks.ste_language_violations(body) == []
    assert checks.noun_stacks(body) == []


# -- P2, person and marketing verbs -------------------------------------------


def test_second_person_fails_the_whole_paper():
    """`you should` fails `person` at paper level, and the detail names the
    sentence."""
    body = "You should charge the budget before the writer runs [1]."
    score = checks.check(body, ["https://a"])
    assert "person" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "person")
    assert "You should" in row.detail


def test_we_will_and_in_this_article_fail():
    """Both first-person phrases fail the same row."""
    will_body = "We will now look at the retry budget in detail [1]."
    assert "person" in checks.check(will_body, ["https://a"]).signature()

    article_body = "In this article, the orchestrator sequences every role [1]."
    assert "person" in checks.check(article_body, ["https://a"]).signature()


def test_a_marketing_verb_fails():
    """`leverage` fails, `robust` fails, and an inflected form fails."""
    leverage = checks.check("The design will leverage existing infrastructure [1].", ["https://a"])
    assert "marketing" in leverage.signature(), leverage.report()

    robust = checks.check("The retry loop stays robust under load [1].", ["https://a"])
    assert "marketing" in robust.signature(), robust.report()

    unlocks = checks.check("The change unlocks new throughput for the pipeline [1].", ["https://a"])
    assert "marketing" in unlocks.signature(), unlocks.report()


def test_a_marketing_word_inside_code_or_a_url_passes():
    """A code span and a reference-list URL are not body prose."""
    body = (
        "A real point [1].\n\n"
        "The adapter uses `a seamless robust retry loop` internally.\n\n"
        "## References\n\n1. https://example.com/unlock-guide\n"
    )
    score = checks.check(body, ["https://example.com/unlock-guide"])
    assert "marketing" not in score.signature(), score.report()


def test_the_recorded_fixture_paper_passes_the_person_and_marketing_rows(tmp_path):
    """The paper `task demo` writes carries no second person, no first person
    tour, and none of the six marketing verbs. Same command as the Taskfile:
    `--backend fixture --fresh --brain tests/fixtures/brain`.
    """
    from pathlib import Path  # noqa: PLC0415

    import loop  # noqa: PLC0415

    folder = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    code = loop.main(
        [
            "--topic", "loop engineering exit criteria",
            "--out", str(work),
            "--backend", "fixture",
            "--brain", str(folder / "tests" / "fixtures" / "brain"),
            "--fresh",
        ]
    )
    assert code == 0, "the recorded fixture must still assemble and pass its gate"
    body = (work / "paper.md").read_text(encoding="utf-8")
    assert checks.person_violations(body) == []
    assert checks.marketing_violations(body) == []


def test_a_leverage_ratio_is_not_a_marketing_verb():
    """Follow-up from the P2 judge: a finance section may name a leverage
    ratio without tripping the marketing row. `leveraging`/`leveraged` are
    still banned outright."""
    ok = checks.check("The bank's leverage ratio fell in the quarter [1].", ["https://a"])
    assert "marketing" not in ok.signature(), ok.report()
    bad = checks.check("We leverage the SDK for every call [1].", ["https://a"])
    assert "marketing" in bad.signature(), bad.report()


def test_an_inline_url_is_not_body_prose_for_person_or_marketing():
    """Follow-up from the P2 judge: a citation URL outside the reference list
    must not fabricate a hit on a path segment."""
    ok = checks.check("See https://example.org/your-account for the record [1].", ["https://a"])
    assert "person" not in ok.signature(), ok.report()
    bad = checks.check("See the record at your account page [1].", ["https://a"])
    assert "person" in bad.signature(), bad.report()


# -- P3, the glossary ----------------------------------------------------


def test_a_defined_term_missing_from_the_glossary_fails():
    """`glossary_complete` fires when a captured term never reached the
    glossary. Production strips every marker at assembly, so this row is a
    defence: a marker that survives into the body is itself the defect."""
    body = (
        "The orchestrator sequences roles [1]. "
        "<!-- TERM: orchestrator: the process that sequences roles -->"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "glossary_complete" in score.signature(), score.report()


def test_a_glossary_only_term_fails():
    """`glossary_exact` fires on a glossary entry the body prose never uses."""
    body = (
        "A point [1].\n\n"
        "## Glossary\n\n"
        "**widget.** A term the body never uses.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "glossary_exact" in score.signature(), score.report()


def test_a_search_host_in_the_glossary_fails():
    """`glossary_exact` also fires on a search-host name, even one the body
    prose does use, because a host is a place the run searched, not a term
    about the subject."""
    body = (
        "This paper names docs.langchain.com as a retrieved source [1].\n\n"
        "## Glossary\n\n"
        "**docs.langchain.com.** A vendor documentation site.\n\n"
        "## References\n\n1. https://docs.langchain.com/x\n"
    )
    score = checks.check(body, ["https://docs.langchain.com/x"], enforce_structure=True)
    assert "glossary_exact" in score.signature(), score.report()


def test_a_plural_or_self_defined_term_does_not_fail_glossary_exact():
    """Follow-up from the PR #499 judge: a literal phrase match rejected
    "one exit criterion" for a glossary term used only in its plural. A
    stemmed match counts, and so does a term repeated inside its own
    definition, which is the writer's own marked sentence."""
    plural_only = (
        "A point about workflows [1].\n\n"
        "## Glossary\n\n"
        "**workflow.** A sequence of steps a run executes.\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "glossary_exact" not in checks.check(plural_only, ["https://a"], enforce_structure=True).signature()

    self_defined = (
        "A point about the process [1].\n\n"
        "## Glossary\n\n"
        "**orchestrator.** The orchestrator sequences roles.\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "glossary_exact" not in checks.check(self_defined, ["https://a"], enforce_structure=True).signature()


def test_an_irregular_plural_matches_its_singular():
    """Follow-up from the PR #499 judge: the regular suffix fold cannot turn
    "criteria" into "criterion", since neither ends in s, es, or ies. A
    fixed table of irregular pairs is checked first."""
    body = (
        "The run checks one exit criterion [1].\n\n"
        "## Glossary\n\n"
        "**exit criteria.** What a run must clear before it stops.\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "glossary_exact" not in checks.check(body, ["https://a"], enforce_structure=True).signature()


def test_structural_rows_are_off_by_default():
    """`enforce_structure` defaults false, so a body carrying both glossary
    defects passes when the caller does not opt in, and an existing narrow
    snippet's signature is unchanged."""
    body = (
        "A point [1].\n\n"
        "## Glossary\n\n"
        "**widget.** A term the body never uses.\n\n"
        "## References\n\n1. https://a\n"
    )
    off = checks.check(body, ["https://a"])
    assert "glossary_complete" not in off.signature()
    assert "glossary_exact" not in off.signature()

    corpus = "we retrieved arXiv:2401.00001 and it says things"
    unrelated = "A real point [1].\n\nAnother point, see arXiv:2999.99999 [1]."
    assert checks.check(unrelated, ["https://a"], corpus=corpus).signature() == ("sourced",)


def test_no_terms_means_no_glossary_and_both_rows_pass():
    """No captured term means nothing missing and nothing extra. The row
    exists and passes, it does not simply stay absent."""
    score = checks.check("A point [1].", ["https://a"], enforce_structure=True)
    names = {c.name for c in score.checks}
    assert {"glossary_complete", "glossary_exact"} <= names
    assert score.passed, score.report()


def test_the_recorded_fixture_paper_passes_the_glossary_rows(tmp_path):
    """The paper `task demo` writes carries no leftover TERM marker and no
    glossary section, since the recorded writer never marks a term. Both rows
    still run, under the harness's own `enforce_research_policy=True`, and
    both pass on the empty set. Same command as the Taskfile:
    `--backend fixture --fresh --brain tests/fixtures/brain`.
    """
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    import loop  # noqa: PLC0415

    folder = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    code = loop.main(
        [
            "--topic", "loop engineering exit criteria",
            "--out", str(work),
            "--backend", "fixture",
            "--brain", str(folder / "tests" / "fixtures" / "brain"),
            "--fresh",
        ]
    )
    assert code == 0, "the recorded fixture must still assemble and pass its gate"
    body = (work / "paper.md").read_text(encoding="utf-8")
    assert "TERM" not in body
    report = json.loads((work / "check.json").read_text(encoding="utf-8"))
    names = {row["name"] for row in report["checks"]}
    assert "glossary_complete" in names
    assert "glossary_exact" in names
    assert report["passed"], report
