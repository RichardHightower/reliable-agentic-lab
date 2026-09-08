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


def test_a_heading_inside_a_fence_is_not_a_heading():
    """#509. A `##` line inside a fenced code block is not paper structure,
    in every row that scans headings: `question_heading`, `next_step`'s
    own `last_prose_heading`, `outline_coverage`, `has_body`
    (`sections_without_prose`), and `section_bodies`, the boundary helper
    the others build on. The same line outside the fence still fails
    `question_heading`.
    """
    from checks import (  # noqa: PLC0415
        last_prose_heading,
        outline_coverage_gaps,
        question_headings,
        section_bodies,
        sections_without_prose,
    )

    fenced = (
        "## Real heading\n\n"
        "Real prose describes a heading question with a rubric here today [1].\n\n"
        "```markdown\n"
        "## Is this a heading?\n"
        "more fence text\n"
        "```\n\n"
        "## Another heading\n\n"
        "More real prose closes the section out today [1].\n"
    )
    outline = {"sections": [{"heading": "Real heading", "key_questions": ["Is this a heading?"]}]}

    assert question_headings(fenced, outline) == []
    assert set(section_bodies(fenced)) == {"real heading", "another heading"}
    assert last_prose_heading(fenced) == "Another heading"
    assert outline_coverage_gaps(fenced, outline) == []
    assert sections_without_prose(fenced, 5) == []

    unfenced = (
        "## Real heading\n\n"
        "Real prose describes a heading question with a rubric here today [1].\n\n"
        "## Is this a heading?\n\n"
        "more fence text\n\n"
        "## Another heading\n\n"
        "More real prose closes the section out today [1].\n"
    )
    assert "Is this a heading?" in question_headings(unfenced, outline)


def test_a_fenced_heading_does_not_satisfy_the_complete_row():
    """#509. A fenced markdown example naming a plan section must not let
    `missing_sections` (`complete`) believe that section was actually
    written.
    """
    from checks import missing_sections  # noqa: PLC0415

    body = (
        "## Abstract\n\nSummary text here today [1].\n\n"
        "```markdown\n"
        "## Introduction\n"
        "example only\n"
        "```\n\n"
        "## References\n\n1. https://a\n"
    )
    assert missing_sections(body, ["Abstract", "Introduction", "References"]) == ["Introduction"]


def test_a_long_question_needs_a_third_of_its_terms():
    """#510. A judge on PR #508 found the #385 gist question "Which trace
    counts were reported by the MAST taxonomy paper?" scored covered by
    "This paper does not report any of it.", on the single incidental word
    "paper". Scaling the requirement to a third of the question's content
    terms, not a flat floor of two, closes that gap; a nine-term question
    used to need the same two incidental matches a two-term question did.
    """
    from checks import outline_coverage_gaps  # noqa: PLC0415

    mast_question = "Which trace counts were reported by the MAST taxonomy paper?"
    outline = {"sections": [{"heading": "One", "key_questions": [mast_question]}]}

    unrelated = "## One\n\nThis paper does not report any of it [1].\n"
    gaps = outline_coverage_gaps(unrelated, outline)
    assert gaps and mast_question in gaps[0], gaps

    covering = "## One\n\nThe section names the trace counts and cites the MAST taxonomy directly [1].\n"
    assert outline_coverage_gaps(covering, outline) == []

    long_question = (
        "How does the retry ledger track a stale approval stamp across a "
        "resumed run and an escalation boundary?"
    )
    outline2 = {"sections": [{"heading": "One", "key_questions": [long_question]}]}
    two_terms = "## One\n\nThe retry path checks a stamp before it runs again [1].\n"
    gaps2 = outline_coverage_gaps(two_terms, outline2)
    assert gaps2 and long_question in gaps2[0], gaps2

    three_terms = "## One\n\nThe retry ledger checks a stamp before an escalation [1].\n"
    assert outline_coverage_gaps(three_terms, outline2) == []


def test_a_short_question_still_passes_on_two_terms():
    """#510. The floor of two survives the scaling: a two-term question
    still needs both of its terms, and passes once the body names both.
    """
    from checks import outline_coverage_gaps  # noqa: PLC0415

    question = "What blocks retries?"
    outline = {"sections": [{"heading": "One", "key_questions": [question]}]}

    one_term = "## One\n\nA stale lock blocks the writer today [1].\n"
    gaps = outline_coverage_gaps(one_term, outline)
    assert gaps and question in gaps[0], gaps

    both_terms = "## One\n\nA stale lock blocks retries until it clears [1].\n"
    assert outline_coverage_gaps(both_terms, outline) == []


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


# #524. The claim this recorded fixture's counter-evidence pass drives, by
# id. `sections._shares_terms`'s coincidental overlap on the four-letter
# word "paper" is what selects it today, between the "approach" section's
# claim text and its own `claims_to_support` entry "The researcher cannot
# write the paper." A future `fixtures/research.json` re-key can change
# that coincidence without changing anything this test is meant to guard,
# so the test below asserts on this id, not on the coincidence.
PINNED_COUNTER_CLAIM_ID = "approach-f2"


def test_the_recorded_fixture_paper_runs_a_claim_through_the_counter_pass(tmp_path):
    """#474 follow-up F7: the counter-evidence pass runs for real against
    the recorded fixture, offline, no network. No claim's text in this
    fixture matches the `GENERALIZING` regex, so the candidate this run
    finds comes from the SDK-only selection criterion,
    `generalizing_claims`'s sole-support-for-a-`claims_to_support`-item
    branch, in the "approach" section. `OfflineTurns` inherits the base
    `counter_search` miss, so the candidate resolves to "miss", not "hit".

    #524: pinned to a named claim id, not to whether the candidate set is
    merely non-empty. `_shares_terms`'s own coincidental overlap picks this
    claim today; the id is now the contract, not the coincidence, so a
    `fixtures/research.json` re-key that swaps which claim happens to
    share a word with its `claims_to_support` entry fails this test on the
    row that actually matters."""
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
    assert code == 0
    generalizing = []
    for path in (work / "knowledge").glob("*/findings.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        generalizing.extend(f for f in payload.get("findings") or [] if f.get("generalizing"))
    ids = {f.get("id") for f in generalizing}
    assert PINNED_COUNTER_CLAIM_ID in ids, (
        f"the pinned claim {PINNED_COUNTER_CLAIM_ID!r} is missing from the recorded "
        f"fixture's generalizing candidates: {sorted(ids)}"
    )
    assert all(f.get("counter") in ("hit", "miss", "capped") for f in generalizing)
    named = next(f for f in generalizing if f.get("id") == PINNED_COUNTER_CLAIM_ID)
    assert named.get("counter") == "miss"


def test_the_counter_pass_fixture_test_names_its_claim():
    """#524. The test above must assert on `PINNED_COUNTER_CLAIM_ID`, not on
    whether the candidate set is merely non-empty: `assert generalizing`
    would still pass against today's fixture, by the same coincidence #524
    closes. This test inspects the other test's own source for the pinned
    constant, rather than re-running the whole offline pipeline a second
    time to say the same thing.
    """
    import inspect  # noqa: PLC0415

    source = inspect.getsource(test_the_recorded_fixture_paper_runs_a_claim_through_the_counter_pass)
    assert "PINNED_COUNTER_CLAIM_ID" in source


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
    """`enforce_structure` defaults false, so a body carrying glossary
    defects, a bare-Conclusion close, and a selling CTA passes when the
    caller does not opt in, and an existing narrow snippet's signature is
    unchanged."""
    body = (
        "A point [1].\n\n"
        "## Conclusion\n\n- Unlock the platform for every team today. [1]\n\n"
        "## Glossary\n\n"
        "**widget.** A term the body never uses.\n\n"
        "## References\n\n1. https://a\n"
    )
    off = checks.check(body, ["https://a"])
    assert "glossary_complete" not in off.signature()
    assert "glossary_exact" not in off.signature()
    assert "next_step" not in off.signature()
    assert "cta_language" not in off.signature()

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


# -- P4, the next-step section --------------------------------------------


def test_a_conclusion_heading_with_no_next_step_verb_fails():
    """`next_step` fires when the last prose heading is a bare Conclusion."""
    body = (
        "A point [1].\n\n"
        "## Conclusion\n\nThis paper reviewed the same point again. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "next_step" in score.signature(), score.report()


def test_unlock_in_the_next_step_section_fails():
    """`cta_language` is scoped to the next-step section. `unlock` in a body
    section is the unconditional `marketing` row's business, not this one."""
    body = (
        "A point [1].\n\n"
        "## Next step\n\n"
        "- Unlock the platform for every team.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "cta_language" in score.signature(), score.report()

    elsewhere = (
        "This paper does not unlock every runtime [1].\n\n"
        "## Next step\n\n"
        "- Evaluate the design on a live ticket.\n\n"
        "## References\n\n1. https://a\n"
    )
    scored = checks.check(elsewhere, ["https://a"], enforce_structure=True)
    assert "marketing" in scored.signature(), scored.report()
    assert "cta_language" not in scored.signature(), scored.report()


def test_evaluate_x_on_a_live_ticket_passes():
    """The house style's own allowed CTA shape passes both new rows."""
    body = (
        "A point [1].\n\n"
        "## Next step\n\n"
        "- Evaluate X on a live ticket.\n"
        "- Run the fixture with --doer none.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "next_step" not in score.signature(), score.report()
    assert "cta_language" not in score.signature(), score.report()


def test_a_figures_appendix_after_next_step_still_passes():
    """A rendered figure no section claimed lands in an orphan `## Figures`
    appendix between the last body section and Glossary. That appendix is
    assembled, not written, so it must not read as the paper's last prose
    section."""
    body = (
        "A point [1].\n\n"
        "## Next step\n\n"
        "- Evaluate X on a live ticket.\n\n"
        "## Figures\n\n"
        "![orphan](diagrams/orphan_imagen.png)\n\n"
        "## Glossary\n\n**widget.** A term the body uses.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "next_step" not in score.signature(), score.report()


def test_the_rest_of_the_460_ban_list_fails_in_the_next_step_section():
    """Ticket #460 also names these four; `CTA_PHRASE` was missing them."""
    for phrase in ("subscribe", "get started", "only solution", "contact sales"):
        body = (
            "A point [1].\n\n"
            f"## Next step\n\n- {phrase.capitalize()} today.\n\n"
            "## References\n\n1. https://a\n"
        )
        score = checks.check(body, ["https://a"], enforce_structure=True)
        assert "cta_language" in score.signature(), (phrase, score.report())


def test_a_step_over_twenty_words_fails():
    """Each step in the next-step section is 20 words or fewer."""
    long_step = "- " + " ".join(["evaluate"] * 21) + "."
    body = (
        "A point [1].\n\n"
        f"## Next step\n\n{long_step}\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], enforce_structure=True)
    assert "cta_language" in score.signature(), score.report()


def test_a_body_with_no_heading_passes_next_step_by_construction():
    """A heading-less snippet, the shape other rows' tests build, has
    nothing to grade and passes rather than fails."""
    score = checks.check("A point [1].", ["https://a"], enforce_structure=True)
    assert "next_step" not in score.signature(), score.report()


def test_the_recorded_fixture_paper_passes_the_next_step_rows(tmp_path):
    """After the fixture repair, `task demo` assembles a paper whose last
    prose section is the next step, and `next_step`/`cta_language` both pass
    under the harness's own `require_next_step=True`/`enforce_structure=True`.
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
    assert body.index("## Next step") < body.index("## References")
    assert "Evaluate the three exits on a live ticket" in body, "the CTA steps, not a coverage stub"
    report = json.loads((work / "check.json").read_text(encoding="utf-8"))
    names = {row["name"] for row in report["checks"]}
    assert "next_step" in names
    assert "cta_language" in names


# -- P5, headings are answers -------------------------------------------------


def test_a_raw_key_question_as_a_heading_fails():
    """A section that pastes its outline key question as an H3 fails
    `question_heading`, and the detail names the offending heading."""
    outline = {
        "sections": [
            {
                "heading": "One",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }
    body = (
        "## One\n\n"
        "### What stops the loop from running forever?\n\n"
        "A rubric computed in code, not left to the model, stops it [1].\n"
    )
    score = checks.check(body, ["https://a"], outline=outline)
    assert "question_heading" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "question_heading")
    assert "What stops the loop from running forever?" in row.detail


def test_a_repunctuated_key_question_as_a_heading_still_fails():
    """PR #508 judge follow-up: the old version stripped only a trailing
    `?` from the wanted set, so a writer that closed the pasted question
    with a period or a colon instead slipped past `question_heading`."""
    outline = {
        "sections": [
            {
                "heading": "One",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }
    period = (
        "## One\n\n"
        "### What stops the loop from running forever.\n\n"
        "A rubric computed in code, not left to the model, stops it [1].\n"
    )
    colon = (
        "## One\n\n"
        "### What stops the loop from running forever:\n\n"
        "A rubric computed in code, not left to the model, stops it [1].\n"
    )
    assert "question_heading" in checks.check(period, ["https://a"], outline=outline).signature()
    assert "question_heading" in checks.check(colon, ["https://a"], outline=outline).signature()


def test_a_heading_ending_in_a_question_mark_fails():
    """The row is unconditional: a heading ending in `?` fails with no
    outline handed to `check` at all."""
    body = (
        "## Is the harness safe to run unattended?\n\n"
        "A rubric computed in code stops it, not a model's own judgment [1].\n"
    )
    score = checks.check(body, ["https://a"])
    assert "question_heading" in score.signature(), score.report()


def test_a_clean_heading_passes_question_heading():
    """A heading that answers the question, rather than asking it, passes."""
    outline = {
        "sections": [
            {
                "heading": "One",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }
    body = (
        "## One\n\n"
        "### A rubric in code stops the loop\n\n"
        "The rubric decides when the loop stops, never a model's own "
        "judgment [1].\n"
    )
    score = checks.check(body, ["https://a"], outline=outline)
    assert "question_heading" not in score.signature(), score.report()


def test_coverage_passes_when_the_body_answers_the_question():
    """`outline_coverage_gaps` no longer requires the verbatim question. Token
    overlap between the question and the section body carries it. #385."""
    from checks import outline_coverage_gaps  # noqa: PLC0415

    outline = {
        "sections": [
            {
                "heading": "One",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }
    body = (
        "## One\n\n"
        "A deterministic rubric in code decides when the loop stops, never a "
        "model's own judgment. [1]\n"
    )
    assert outline_coverage_gaps(body, outline) == []


def test_coverage_still_fails_a_paper_section_that_never_answers_the_question():
    """A body with no term overlap with the question is still a gap."""
    from checks import outline_coverage_gaps  # noqa: PLC0415

    outline = {
        "sections": [
            {
                "heading": "One",
                "key_questions": ["What stops the loop from running forever?"],
            }
        ]
    }
    body = "## One\n\nThis section is about something else entirely [1].\n"
    gaps = outline_coverage_gaps(body, outline)
    assert gaps and "One" in gaps[0]


def test_the_recorded_fixture_paper_passes_question_heading(tmp_path):
    """The paper `task demo` writes has no heading that pastes a key
    question, under the harness's own outline. Same command as the
    Taskfile: `--backend fixture --fresh --brain tests/fixtures/brain`."""
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
    report = json.loads((work / "check.json").read_text(encoding="utf-8"))
    names = {row["name"] for row in report["checks"]}
    assert "question_heading" in names
    assert report["passed"], report


# -- P6, the paper does not narrate the harness --------------------------------


def test_the_creatine_sentence_fails_policy_leak():
    """The exact sentence from #412. The finished creatine paper spent whole
    paragraphs reporting that no preprint was found, and this is the one the
    ticket quotes. `arxiv.org` was the host admitted for that run, the same
    way a biomedical librarian would admit it today."""
    body = (
        "A point about creatine [1].\n\n"
        "No study identified for this mechanism was hosted on arxiv.org.\n"
    )
    score = checks.check(body, ["https://a"], allowed_domains=("arxiv.org",))
    assert "policy_leak" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "policy_leak")
    assert "arxiv.org" in row.detail


def test_an_allowlist_host_in_body_prose_fails():
    """A host from the run's allowlist in a body section fails. The same
    host in Methods or References passes: #478 fills Methods with the
    admitted-host list by design, and References is the citation list."""
    host = "example-journal.org"
    body_hit = f"The team searched {host} for evidence [1].\n"
    assert "policy_leak" in checks.check(body_hit, ["https://a"], allowed_domains=(host,)).signature()

    methods_ok = (
        "A point [1].\n\n"
        f"## Methods\n\nThe run searched {host} for evidence.\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "policy_leak" not in checks.check(methods_ok, ["https://a"], allowed_domains=(host,)).signature()

    references_ok = f"A point [1].\n\n## References\n\n1. https://{host}/x\n"
    assert (
        "policy_leak"
        not in checks.check(references_ok, [f"https://{host}/x"], allowed_domains=(host,)).signature()
    )


def test_methods_may_name_admitted_hosts():
    """The Methods exemption, on its own: #478 writes Methods from the run
    record, and it names the admitted hosts by design."""
    host = "example-journal.org"
    body = (
        "A point [1].\n\n"
        f"## Methods\n\nSources were retrieved from {host} and {host}/archive.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"], allowed_domains=(host,))
    assert "policy_leak" not in score.signature(), score.report()


def test_the_references_section_may_name_hosts():
    """The References exemption, on its own: the reference list is where a
    host name belongs."""
    host = "example-journal.org"
    body = f"A point [1].\n\n## References\n\n1. https://{host}/paper\n"
    score = checks.check(body, [f"https://{host}/paper"], allowed_domains=(host,))
    assert "policy_leak" not in score.signature(), score.report()


def test_the_three_phrases_fail():
    """The three retrieval phrases #412 names, each in an otherwise ordinary
    sentence."""
    sentences = {
        "preprint search": "The preprint search turned up nothing usable here [1].",
        "search scope": "The search scope excluded several relevant databases [1].",
        "no study was hosted on": "No study was hosted on a site this run could reach [1].",
    }
    for phrase, body in sentences.items():
        score = checks.check(body, ["https://a"])
        assert "policy_leak" in score.signature(), (phrase, score.report())


def test_a_paper_that_never_names_a_host_passes():
    """A clean paper, with no search host and no retrieval language, passes
    by construction."""
    body = (
        "Creatine reduces lean mass loss during immobilization [1].\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "policy_leak" not in checks.check(body, ["https://a"]).signature()


def test_the_writer_message_names_no_allowlist_host_belt():
    """`policy_leak` is the belt behind the stripped delegation message
    (`tests/test_research_and_turns.py`). This is the Python-side row that
    still catches a leak if the strip is ever bypassed."""
    body = "The result came from arxiv.org, which this run searched [1].\n"
    assert "policy_leak" in checks.check(body, ["https://a"], allowed_domains=("arxiv.org",)).signature()


def test_the_recorded_fixture_paper_passes_policy_leak(tmp_path):
    """The paper `task demo` writes names no search host and narrates no
    retrieval boundary. Same command as the Taskfile:
    `--backend fixture --fresh --brain tests/fixtures/brain`."""
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
    hits = checks.policy_leak_violations(body)
    assert hits == [], hits


# -- P7, the abstract is written last -------------------------------------


def test_an_unhedged_single_source_abstract_fails():
    """A hedge-free sentence in the abstract, beside a `[n]` whose claim is
    single-source, fails and names the sentence."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices. [1]\n\n"
        "## Introduction\n\nThe loop halts before a person notices, one trial supporting it. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    claims = [{"number": 1, "source_url": "https://a", "verifier_url": ""}]
    score = checks.check(body, ["https://a"], claims=claims)
    assert "abstract_matches_body" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert "halts before a person notices" in row.detail


def test_a_number_shared_by_a_corroborated_claim_is_not_forced_to_hedge():
    """Two claims can share one reference number. A single-source claim on
    it must not force a hedge onto a sentence citing the other, corroborated
    claim on the same number."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices. [1]\n\n"
        "## Introduction\n\nThe loop halts before a person notices. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    claims = [
        {"number": 1, "source_url": "https://a", "verifier_url": ""},
        {"number": 1, "source_url": "https://a", "verifier_url": "https://b"},
    ]
    score = checks.check(body, ["https://a"], claims=claims)
    assert "abstract_matches_body" not in score.signature(), score.report()


def test_an_abstract_number_absent_from_the_body_fails():
    """A citation the abstract uses, and no other section does, fails."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices [1]. It also cites [2].\n\n"
        "## Introduction\n\nThe loop halts before a person notices [1].\n\n"
        "## References\n\n1. https://a\n2. https://b\n"
    )
    score = checks.check(body, ["https://a", "https://b"])
    assert "abstract_matches_body" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert "[2]" in row.detail


def test_an_overclaim_in_the_abstract_fails():
    """The fixed overclaim list, whatever the ledger says about the claim."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThis paper proves the loop halts before a person notices. [1]\n\n"
        "## Introduction\n\nThe loop halts before a person notices. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"])
    assert "abstract_matches_body" in score.signature(), score.report()


def test_improves_is_not_an_overclaim():
    """`ABSTRACT_OVERCLAIM` matches whole words: `improves` is not `proves`."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nCreatine improves lean mass. [1]\n\n"
        "## Introduction\n\nCreatine improves lean mass, on a single source. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"])
    assert "abstract_matches_body" not in score.signature(), score.report()


def test_the_introduction_first_paragraph_is_graded_too():
    """The same row runs on the introduction's first paragraph, not only the
    abstract."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices, one trial supporting it. [1]\n\n"
        "## Introduction\n\nThis paper proves the loop halts before a person notices. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = checks.check(body, ["https://a"])
    assert "abstract_matches_body" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert "introduction" in row.detail


def test_a_body_with_no_abstract_heading_is_inert():
    """The row runs on every check, and a snippet another row's test built
    has no `## Abstract` heading and nothing to grade. `signature()` only
    ever lists failing rows, so absence there is not proof the row ran;
    check the row itself, on a body that would fail the overclaim rule if
    it were graded."""
    body = "# Title\n\n## Introduction\n\nThis paper proves nothing yet. [1]\n\n## References\n\n1. https://a\n"
    score = checks.check(body, ["https://a"])
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert row.passed, row.detail


def test_the_recorded_fixture_paper_passes_abstract_matches_body(tmp_path):
    """The paper `task demo` writes assembles with the abstract last, and it
    matches the body it summarizes. Same command as the Taskfile:
    `--backend fixture --fresh --brain tests/fixtures/brain`."""
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
    report = json.loads((work / "check.json").read_text(encoding="utf-8"))
    names = {row["name"] for row in report["checks"]}
    assert "abstract_matches_body" in names
    assert report["passed"], report
