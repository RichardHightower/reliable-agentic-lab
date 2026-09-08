"""The hard gates. Everything here is settled without asking anyone."""

from __future__ import annotations

import evidence
import paper_check
import pytest

URLS = ["https://docs.langchain.com/one", "https://docs.claude.com/two"]
GOOD = (
    "# Exit conditions\n\n"
    "## Abstract\n\nA loop without an exit spends until someone notices. [1]\n\n"
    "## Introduction\n\nThree exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
    "![A flowchart of the three exits](figures/exits_imagen.png)\n\n"
    "## Limitations\n\nThis paper measures two runtimes only. [2]\n\n"
    "## Next step\n\n"
    "- Evaluate the three exits on a live ticket before adopting them.\n"
    "- Run the fixture with --backend fixture, then again with a live backend.\n"
    "- Compare this port against the sibling runtime on the same topic.\n\n"
    "## References\n\n1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
)


def gate(body, urls=URLS, **kwargs):
    """Structural checks keep the old short-paper floor."""
    kwargs.setdefault("min_words", 0)
    kwargs.setdefault("min_section_words", 5)
    kwargs.setdefault("enforce_structure", False)
    return paper_check.check(body, urls, **kwargs)


def test_demo_assertions_hold():
    paper_check.demo()


def test_a_clean_paper_passes():
    assert gate(GOOD, URLS).passed


def test_cli_uses_the_evidence_bibliography_when_sources_are_not_separate(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(paper_check, "MIN_WORDS", 0)
    monkeypatch.setattr(paper_check, "MIN_SECTION_WORDS", 5)
    # This test is about the CLI reading a bibliography from `--evidence`, not
    # about single-source status, so the claims are left `proposed`: calling
    # `corroborate()` on a one-source claim would mark it single-source, and
    # `GOOD`'s own abstract citation would then need a hedge it does not carry
    # for this unrelated claim text. #472.
    ledger = evidence.Ledger(tmp_path / "evidence")
    for url in URLS:
        source = ledger.add_source(evidence.SourceDocument(title=url, url=url, subject="exits"))
        ledger.add_claim(
            evidence.Claim(text=f"Claim from {url}", subject="exits", source_ids=[source.id])
        )
    ledger.write()
    paper = tmp_path / "paper.md"
    paper.write_text(GOOD, encoding="utf-8")

    assert paper_check.main([str(paper), "--evidence", str(ledger.root)]) == 0
    output = capsys.readouterr().out
    assert "PASS  has_sources" in output
    assert "2 sources retrieved" in output


def test_a_deepwiki_reference_blocks_the_paper_but_docs_passes():
    rejected = GOOD.replace("https://docs.langchain.com/one", "https://deepwiki.com/langchain")
    score = gate(rejected, ["https://deepwiki.com/langchain", URLS[1]])
    assert "reference_hosts" in score.signature()
    assert gate(GOOD, URLS).passed


def test_exit_doctrine_requires_done_then_cost_then_max_turns():
    wrong = GOOD.replace(
        "done, then cost, then max turns", "cost, then done, then max turns"
    )
    assert "exit_doctrine" in gate(wrong, URLS).signature()
    assert "exit_doctrine" not in gate(GOOD, URLS).signature()


def test_exit_doctrine_is_local_not_the_first_terms_in_the_whole_paper():
    body = GOOD.replace(
        "A loop without an exit spends until someone notices. [1]",
        "Cost appears in the abstract before the ordered doctrine. [1]",
    )

    assert "exit_doctrine" not in gate(body, URLS).signature()


def test_exit_doctrine_is_opt_in_off_by_default_for_any_other_topic():
    """#406: the doctrine is the seminar's own topic, not every paper's."""
    creatine = (
        "# Creatine and lean mass\n\n"
        "## Abstract\n\nCreatine plausibly protects lean mass in a deficit. [1]\n\n"
        "## Introduction\n\nA calorie deficit risks lean mass loss during training. [1]\n\n"
        "## Limitations\n\nTrial evidence is thin. [2]\n\n"
        "## References\n\n1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
    )
    off = gate(creatine, URLS, loop_doctrine=False)
    assert "exit_doctrine" not in [c.name for c in off.checks]
    assert off.passed, off.report()

    on = gate(creatine, URLS, loop_doctrine=True)
    assert "exit_doctrine" in on.signature()


def test_exit_doctrine_still_grades_the_recorded_topic_with_the_flag_on():
    """Flag on is unchanged: the seminar's own paper still names the order
    and still passes the row."""
    assert "exit_doctrine" not in gate(GOOD, URLS, loop_doctrine=True).signature()


def test_limitations_cannot_deny_a_cited_official_langgraph_page():
    contradiction = GOOD.replace(
        "This paper measures two runtimes only.",
        "There is no official LangGraph page for this topic.",
    )
    assert "langgraph_limitations" in gate(contradiction, URLS).signature()


@pytest.mark.parametrize(
    "body,row",
    [
        (GOOD.replace("[2]", "[9]"), "grounded"),
        (GOOD.replace("## Abstract", "## Overview"), "sections"),
        (GOOD.replace("[A flowchart of the three exits]", "[]"), "figure_alt"),
        (GOOD.replace("## References\n\n1. https", "## Sources\n\n1. https"), "references"),
    ],
)
def test_each_hard_gate_blocks(body, row):
    score = gate(body, URLS)
    assert not score.passed
    assert row in score.signature()


def test_an_em_dash_is_replaced_not_argued_about():
    score = gate(GOOD.replace("spends until", "spends — until"), URLS)
    assert "style" in score.signature()


def test_diagram_source_in_the_body_blocks():
    """The figure is the artifact. A reader never sees `flowchart TB`."""
    leaked = GOOD.replace("![A", "```mermaid\nflowchart TB\n  A --> B\n```\n\n![A")
    assert "no_diagram_source" in gate(leaked, URLS).signature()


def test_svg_and_plain_png_figure_fallbacks_block_publication():
    for target in ("figures/exits.svg", "figures/exits.png"):
        body = GOOD.replace("figures/exits_imagen.png", target)
        assert "figure_assets" in gate(body, URLS).signature()


def test_charts_png_is_a_publication_asset():
    body = GOOD.replace(
        "![A flowchart of the three exits](figures/exits_imagen.png)",
        "![A flowchart of the three exits](figures/exits_imagen.png)\n\n"
        "![the three exits](charts/three-exits.png)",
    )
    assert "figure_assets" not in gate(body, URLS).signature()


def test_a_figure_is_not_an_uncited_claim():
    """An image paragraph asserts nothing, so demanding a citation on it would
    fail every paper that has a figure."""
    assert "cited" not in gate(GOOD, URLS).signature()


def test_a_numbered_procedure_is_not_a_reference_list():
    assert paper_check.reference_rows("## Steps\n\n1. do this\n2. do that\n") == []
    assert len(paper_check.reference_rows(GOOD)) == 2


def test_missing_limitations_warns_but_ships():
    trimmed = GOOD.replace("## Limitations\n\nThis paper measures two runtimes only. [2]\n\n", "")
    score = gate(trimmed, URLS)
    assert score.passed, score.report()
    assert "limitations" in score.warnings()
    assert "limitations" not in score.signature(), "a warning must not drive a retry"


def ledger_with_single_source():
    ledger = evidence.Ledger("/nonexistent")
    src = ledger.add_source(evidence.SourceDocument(title="One", url=URLS[0], subject="exits"))
    claim = ledger.add_claim(
        evidence.Claim(
            text="Three exits cover the observed cases",
            subject="exits",
            source_ids=[src.id],
            important=True,
        )
    )
    evidence.corroborate(claim)
    return ledger, claim


def test_a_single_source_claim_must_admit_it_in_its_own_section():
    ledger, _ = ledger_with_single_source()
    assert "single_source_caveat" in gate(GOOD, URLS, ledger=ledger).signature()

    caveated = GOOD.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]",
        "Three exits cover the observed cases: done, then cost, then max turns, on a single source. [1][2]",
    )
    assert (
        "single_source_caveat" not in gate(caveated, URLS, ledger=ledger).signature()
    )


def test_the_caveat_must_be_local_to_the_claim():
    """A caveat in the abstract does not cover a claim four sections later."""
    ledger, _ = ledger_with_single_source()
    elsewhere = GOOD.replace(
        "A loop without an exit spends until someone notices. [1]",
        "A loop without an exit spends until someone notices, on a single source. [1]",
    )
    assert "single_source_caveat" in gate(elsewhere, URLS, ledger=ledger).signature()


def test_the_reference_list_is_not_searched_for_a_caveat():
    """Every URL appears there, so scanning it would test the bibliography."""
    sections = paper_check.body_sections(GOOD)
    assert not any("References" in section for section in sections)


def test_a_contradicted_claim_never_reaches_the_paper():
    ledger, claim = ledger_with_single_source()
    evidence.corroborate(claim, contradicted=True)
    body = GOOD.replace("Three exits cover", f"{claim.id} Three exits cover")
    assert "no_contradicted" in gate(body, URLS, ledger=ledger).signature()


def test_the_signature_is_what_failed_not_how_it_was_worded():
    """`gates.decide` compares two signatures to spot a loop that is not
    converging, so the signature must be stable across retries."""
    first = gate(GOOD.replace("[2]", "[9]"), URLS).signature()
    second = gate(GOOD.replace("[2]", "[8]"), URLS).signature()
    assert first == second == ("grounded",)


# -- the body --------------------------------------------------------------

HOLLOW = (
    # P7, #472: the abstract's citation needs a matching mention outside the
    # abstract, or `abstract_matches_body` calls it orphaned. The introduction
    # restates the same sentence rather than adding content the has_body test
    # does not want; Limitations stays empty, so has_body still fires there.
    "# Exit conditions\n\n## Abstract\n\ndone, then cost, then max turns. [1]\n\n"
    "## Introduction\n\ndone, then cost, then max turns. [1]\n\n## Limitations\n\n"
    "## References\n\n1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
)


def test_a_paper_with_no_body_is_blocked():
    """Every other gate checks content that is not there. Grounding passes with
    no citations to dangle, `cited` passes with no claim paragraphs, and style
    passes with no text to hold an em dash. Only the soft word count noticed."""
    score = gate(HOLLOW, URLS)
    assert not score.passed
    assert score.signature() == ("has_body",)


def test_every_other_hard_gate_passes_on_the_hollow_paper():
    """This is why `has_body` had to be added rather than tightened."""
    score = gate(HOLLOW, URLS)
    green = {c.name for c in score.checks if c.passed}
    assert {"grounded", "cited", "style", "sections", "references"} <= green


def test_a_stub_section_is_blocked():
    thin = GOOD.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]", "Yes. [1]"
    )
    assert "has_body" in gate(thin, URLS).signature()


def test_a_section_of_only_a_figure_is_blocked():
    """A figure still owes the reader an explanation."""
    figure_only = GOOD.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]\n\n"
        "![A flowchart of the three exits](figures/exits_imagen.png)",
        "![A flowchart of the three exits](figures/exits_imagen.png)",
    )
    assert "has_body" in gate(figure_only, URLS).signature()


def test_references_and_figures_owe_no_prose():
    appendix = GOOD.replace(
        "## References",
        "## Figures\n\n![A sequence of the roles](figures/roles_imagen.png)\n\n## References",
    )
    assert "has_body" not in gate(appendix, URLS).signature()


def test_a_real_paper_still_passes():
    assert gate(GOOD, URLS).passed


def test_a_short_paper_fails_the_hard_length_gate():
    """A structurally green brief is not a paper. Length ships as a hard row."""
    score = paper_check.check(GOOD, URLS)
    assert not score.passed
    assert "length" in score.signature()
    assert "length" not in score.warnings()


# -- a located cabinet reference is not the allowlist's business ------------

ARXIV = "https://arxiv.org/abs/2503.13657"
LOCATED = GOOD.replace("https://docs.langchain.com/one", ARXIV)


def test_reference_hosts_passes_a_located_url():
    score = gate(LOCATED, [ARXIV, URLS[1]], located=[ARXIV])
    assert "reference_hosts" not in score.signature(), score.report()


def test_reference_hosts_fails_the_same_url_untagged():
    score = gate(LOCATED, [ARXIV, URLS[1]])
    assert "reference_hosts" in score.signature()


def test_assemble_gate_exempts_a_located_source_from_the_allowlist(monkeypatch):
    """End to end: the ledger carries the tag, `assemble_gate` passes it down."""
    import stages  # noqa: PLC0415

    monkeypatch.setattr(paper_check, "MIN_WORDS", 0)
    monkeypatch.setattr(paper_check, "MIN_SECTION_WORDS", 5)
    ledger = evidence.Ledger("/nonexistent")
    located = ledger.add_source(
        evidence.SourceDocument(
            title="MAST", url=ARXIV, subject="exits", located_from="knowledge:claim.mast"
        )
    )
    plain = ledger.add_source(
        evidence.SourceDocument(title="Docs", url=URLS[1], subject="exits")
    )
    ledger.add_claim(
        evidence.Claim(text="a fact", subject="exits", source_ids=[located.id, plain.id])
    )

    assert stages.assemble_gate(LOCATED, ledger).passed

    ledger.sources[located.id].located_from = ""
    with pytest.raises(stages.GateFailed) as exc:
        stages.assemble_gate(LOCATED, ledger)
    assert "reference_hosts" in str(exc.value)


# -- P1, the STE belt: contractions, Latin abbreviations, noun stacks --------


def test_a_contraction_in_body_prose_fails():
    """`don't` fails `ste_language`, and the detail names the sentence."""
    body = GOOD.replace(
        "A loop without an exit spends until someone notices. [1]",
        "The loop doesn't exit until someone notices. [1]",
    )
    score = gate(body, URLS)
    assert "ste_language" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "ste_language")
    assert "doesn't" in row.detail
    assert "exit until someone notices" in row.detail


def test_a_latin_abbreviation_fails():
    """`e.g.` fails, and a clean body still passes."""
    dirty = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, e.g. LangGraph. [2]",
    )
    assert "ste_language" in gate(dirty, URLS).signature()

    clean = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, for example LangGraph. [2]",
    )
    assert "ste_language" not in gate(clean, URLS).signature()


def test_four_nouns_in_a_row_fail():
    """`noun_stack` fires on a four-noun phrase. It is advisory (a deviation
    from #456, stated in the P1-fix PR body): it reports and never blocks the
    gate, so it never appears in `signature()` and never flips `passed`.
    """
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "A loop harness gate ledger ships every seminar. [2]",
    )
    score = gate(body, URLS)
    assert "noun_stack" not in score.signature(), score.report()
    assert "noun_stack" in score.warnings(), score.report()
    row = next(c for c in score.checks if c.name == "noun_stack")
    assert not row.passed
    assert "loop harness gate ledger" in row.detail
    assert score.passed, "an advisory row never fails the gate"


def test_may_on_an_unverified_claim_still_passes():
    """STE-S9 stays off. A hedge on an unverified claim is not a procedure step."""
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The approach may reduce cost on some workloads. [2]",
    )
    assert gate(body, URLS).passed, gate(body, URLS).report()


def test_a_contraction_inside_a_code_fence_passes():
    """The mask works: a contraction inside a fenced code block is not prose."""
    body = GOOD.replace(
        "## Limitations",
        "```\nassert doesnt_exist == False\n```\n\n## Limitations",
    )
    assert "ste_language" not in gate(body, URLS).signature(), gate(body, URLS).report()


def test_a_genitive_is_not_a_contraction():
    """"the writer's card" is a possessive, not `it's`/`don't`."""
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The writer's card names the actor. [2]",
    )
    assert "ste_language" not in gate(body, URLS).signature()


def test_the_recorded_fixture_paper_passes_the_ste_belt(run_dir, stub_renderer):
    """The paper `task paper` writes carries no contraction, no Latin
    abbreviation, and no four-noun stack.
    """
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    assert paper_check.ste_language_violations(body) == []
    assert paper_check.noun_stacks(body) == []


# -- P2, person and marketing verbs -------------------------------------------


def test_second_person_fails_the_whole_paper():
    """`you should` fails `person` at paper level, and the detail names the
    sentence."""
    body = GOOD.replace(
        "A loop without an exit spends until someone notices. [1]",
        "You should notice that a loop without an exit spends until it stops. [1]",
    )
    score = gate(body, URLS)
    assert "person" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "person")
    assert "You should" in row.detail


def test_we_will_and_in_this_article_fail():
    """Both first-person phrases fail the same row."""
    will_body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "We will now look at the retry budget in detail. [2]",
    )
    assert "person" in gate(will_body, URLS).signature()

    article_body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "In this article, the orchestrator sequences every role. [2]",
    )
    assert "person" in gate(article_body, URLS).signature()


def test_a_marketing_verb_fails():
    """`leverage` fails, `robust` fails, and an inflected form fails."""
    leverage = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The design will leverage existing infrastructure. [2]",
    )
    assert "marketing" in gate(leverage, URLS).signature()

    robust = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The retry loop stays robust under load. [2]",
    )
    assert "marketing" in gate(robust, URLS).signature()

    unlocks = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The change unlocks new throughput for the pipeline. [2]",
    )
    assert "marketing" in gate(unlocks, URLS).signature()


def test_a_marketing_word_inside_code_or_a_url_passes():
    """A fenced code block and a reference-list URL are not body prose."""
    body = GOOD.replace(
        "## Limitations",
        "```\na seamless robust retry loop\n```\n\n## Limitations",
    ).replace(
        "1. https://docs.langchain.com/one",
        "1. https://example.com/unlock-guide",
    )
    score = gate(body, [URLS[1], "https://example.com/unlock-guide"])
    assert "marketing" not in score.signature(), score.report()


def test_the_recorded_fixture_paper_passes_the_person_and_marketing_rows(run_dir, stub_renderer):
    """The paper `task paper` writes carries no second person, no first person
    tour, and none of the six marketing verbs.
    """
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    assert paper_check.person_violations(body) == []
    assert paper_check.marketing_violations(body) == []


def test_a_leverage_ratio_is_not_a_marketing_verb():
    """Follow-up from the P2 judge: a finance section may name a leverage
    ratio without tripping the marketing row. `leveraging`/`leveraged` are
    still banned outright."""
    ok = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "The bank's leverage ratio fell in the quarter. [2]",
    )
    assert "marketing" not in gate(ok, URLS).signature(), gate(ok, URLS).report()
    bad = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "We leverage the SDK for every call. [2]",
    )
    assert "marketing" in gate(bad, URLS).signature(), gate(bad, URLS).report()


def test_an_inline_url_is_not_body_prose_for_person_or_marketing():
    """Follow-up from the P2 judge: a citation URL outside the reference list
    must not fabricate a hit on a path segment."""
    ok = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "See https://example.org/your-account for the record. [2]",
    )
    assert "person" not in gate(ok, URLS).signature(), gate(ok, URLS).report()
    bad = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "See the record at your account page. [2]",
    )
    assert "person" in gate(bad, URLS).signature(), gate(bad, URLS).report()


# -- P3, the glossary ----------------------------------------------------


def test_a_defined_term_missing_from_the_glossary_fails():
    """`glossary_complete` fires when a captured term never reached the
    glossary. Production strips every marker at assembly, so this row is a
    defence: a marker that survives into the body is itself the defect."""
    body = GOOD.replace(
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2]",
        "Three exits cover the observed cases: done, then cost, then max turns. [1][2] "
        "<!-- TERM: orchestrator: the process that sequences roles -->",
    )
    score = gate(body, enforce_structure=True)
    assert "glossary_complete" in score.signature(), score.report()


def test_a_glossary_only_term_fails():
    """`glossary_exact` fires on a glossary entry the body prose never uses."""
    body = GOOD.replace(
        "## References",
        "## Glossary\n\n**widget.** A term the body never uses.\n\n## References",
    )
    score = gate(body, enforce_structure=True)
    assert "glossary_exact" in score.signature(), score.report()


def test_a_search_host_in_the_glossary_fails():
    """`glossary_exact` also fires on a search-host name, even one the body
    prose does use, because a host is a place the run searched, not a term
    about the subject."""
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, retrieved from docs.langchain.com. [2]",
    ).replace(
        "## References",
        "## Glossary\n\n**docs.langchain.com.** A vendor documentation site.\n\n## References",
    )
    score = gate(body, enforce_structure=True)
    assert "glossary_exact" in score.signature(), score.report()


def test_a_plural_or_self_defined_term_does_not_fail_glossary_exact():
    """Follow-up from the PR #499 judge: a literal phrase match rejected
    "one exit criterion" for a glossary term used only in its plural. A
    stemmed match counts, and so does a term repeated inside its own
    definition, which is the writer's own marked sentence."""
    plural_only = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, across several workflows. [2]",
    ).replace(
        "## References",
        "## Glossary\n\n**workflow.** A sequence of steps a run executes.\n\n## References",
    )
    assert "glossary_exact" not in gate(plural_only, enforce_structure=True).signature()

    self_defined = GOOD.replace(
        "## References",
        "## Glossary\n\n**orchestrator.** The orchestrator sequences roles.\n\n## References",
    )
    assert "glossary_exact" not in gate(self_defined, enforce_structure=True).signature()


def test_an_irregular_plural_matches_its_singular():
    """Follow-up from the PR #499 judge: the regular suffix fold cannot turn
    "criteria" into "criterion", since neither ends in s, es, or ies. A
    fixed table of irregular pairs is checked first."""
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, against one exit criterion. [2]",
    ).replace(
        "## References",
        "## Glossary\n\n**exit criteria.** What a run must clear before it stops.\n\n## References",
    )
    assert "glossary_exact" not in gate(body, enforce_structure=True).signature()


def test_a_term_used_only_inside_inline_code_still_fails_glossary_exact():
    """Finding #3: the SDK masks inline code before this search with
    `_mask_code`. This port must too, so a term seen only inside a single
    backtick span is not credited as used."""
    body = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper measures two runtimes only, per `workflow` config. [2]",
    ).replace(
        "## References",
        "## Glossary\n\n**workflow.** A sequence of steps a run executes.\n\n## References",
    )
    score = gate(body, enforce_structure=True)
    assert "glossary_exact" in score.signature(), score.report()


def test_structural_rows_are_off_by_default():
    """`enforce_structure` defaults false, so a body carrying glossary
    defects, a bare-Conclusion close, and a selling CTA passes when the
    caller does not opt in, and an existing narrow snippet's assertions are
    unchanged."""
    body = GOOD.replace(
        "## References",
        "## Glossary\n\n**widget.** A term the body never uses.\n\n## References",
    ).replace(
        "## Next step\n\n"
        "- Evaluate the three exits on a live ticket before adopting them.\n"
        "- Run the fixture with --backend fixture, then again with a live backend.\n"
        "- Compare this port against the sibling runtime on the same topic.\n\n",
        "## Conclusion\n\n- Unlock the platform for every team today. [2]\n\n",
    )
    off = gate(body)
    assert "glossary_complete" not in off.signature()
    assert "glossary_exact" not in off.signature()
    assert "next_step" not in off.signature()
    assert "cta_language" not in off.signature()
    assert gate(GOOD, URLS).passed


def test_no_terms_means_no_glossary_and_both_rows_pass():
    """No captured term means nothing missing and nothing extra. The row
    exists and passes, it does not simply stay absent."""
    score = gate(GOOD, enforce_structure=True)
    names = {c.name for c in score.checks}
    assert {"glossary_complete", "glossary_exact"} <= names
    assert score.passed, score.report()


def test_the_recorded_fixture_paper_passes_the_glossary_rows(run_dir, stub_renderer):
    """The paper `task paper` writes carries no leftover TERM marker and no
    glossary section, since the recorded writer never marks a term. Both rows
    still run, under `assemble_gate`'s own `enforce_structure=True`, and both
    pass on the empty set."""
    import stages  # noqa: PLC0415
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    assert "TERM" not in body
    score = stages.assemble_gate(
        body, run.ledger, allowed_domains=run.allowed_domains, loop_doctrine=run.loop_doctrine
    )
    names = {c.name for c in score.checks}
    assert "glossary_complete" in names
    assert "glossary_exact" in names
    assert score.passed, score.report()


# -- P4, the next-step section --------------------------------------------


def test_a_conclusion_heading_with_no_next_step_verb_fails():
    """`next_step` fires when the last prose heading is a bare Conclusion."""
    body = GOOD.replace(
        "## Next step\n\n"
        "- Evaluate the three exits on a live ticket before adopting them.\n"
        "- Run the fixture with --backend fixture, then again with a live backend.\n"
        "- Compare this port against the sibling runtime on the same topic.\n\n",
        "## Conclusion\n\nThis paper reviewed the same three exits again. [2]\n\n",
    )
    score = gate(body, enforce_structure=True)
    assert "next_step" in score.signature(), score.report()


def test_unlock_in_the_next_step_section_fails():
    """`cta_language` is scoped to the next-step section. `unlock` in a body
    section is the unconditional `marketing` row's business, not this one."""
    body = GOOD.replace(
        "- Evaluate the three exits on a live ticket before adopting them.\n",
        "- Unlock the platform for every team.\n",
    )
    score = gate(body, enforce_structure=True)
    assert "cta_language" in score.signature(), score.report()

    elsewhere = GOOD.replace(
        "This paper measures two runtimes only. [2]",
        "This paper does not unlock every runtime. [2]",
    )
    scored = gate(elsewhere, enforce_structure=True)
    assert "marketing" in scored.signature(), scored.report()
    assert "cta_language" not in scored.signature(), scored.report()


def test_evaluate_x_on_a_live_ticket_passes():
    """The house style's own allowed CTA shape passes both new rows."""
    score = gate(GOOD, enforce_structure=True)
    assert "next_step" not in score.signature(), score.report()
    assert "cta_language" not in score.signature(), score.report()


def test_a_figures_appendix_after_next_step_still_passes():
    """A rendered figure no section claimed lands in an orphan `## Figures`
    appendix between the last body section and Glossary. That appendix is
    assembled, not written, so it must not read as the paper's last prose
    section."""
    body = GOOD.replace(
        "## References",
        "## Figures\n\n![orphan](diagrams/orphan_imagen.png)\n\n## References",
    )
    score = gate(body, enforce_structure=True)
    assert "next_step" not in score.signature(), score.report()


def test_the_rest_of_the_460_ban_list_fails_in_the_next_step_section():
    """Ticket #460 also names these four; `CTA_PHRASE` was missing them."""
    for phrase in ("subscribe", "get started", "only solution", "contact sales"):
        body = GOOD.replace(
            "- Evaluate the three exits on a live ticket before adopting them.\n",
            f"- {phrase.capitalize()} today.\n",
        )
        score = gate(body, enforce_structure=True)
        assert "cta_language" in score.signature(), (phrase, score.report())


def test_a_step_over_twenty_words_fails():
    """Each step in the next-step section is 20 words or fewer."""
    long_step = "- " + " ".join(["evaluate"] * 21) + ".\n"
    body = GOOD.replace(
        "- Evaluate the three exits on a live ticket before adopting them.\n", long_step
    )
    score = gate(body, enforce_structure=True)
    assert "cta_language" in score.signature(), score.report()


def test_the_recorded_fixture_paper_passes_the_next_step_rows(run_dir, stub_renderer):
    """After the fixture repair, `task paper` assembles a paper whose last
    prose section is the next step, and `next_step`/`cta_language` both pass
    under `assemble_gate`'s own `enforce_structure=True`."""
    import stages  # noqa: PLC0415
    from conftest import build_run  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    assert body.index("## Next step") < body.index("## References")
    assert "Evaluate the three exits on a live ticket" in body, "the recorded CTA steps"
    score = stages.assemble_gate(
        body, run.ledger, allowed_domains=run.allowed_domains, loop_doctrine=run.loop_doctrine
    )
    names = {c.name for c in score.checks}
    assert "next_step" in names
    assert "cta_language" in names
    assert score.passed, score.report()


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
        "# Title\n\n"
        "## One\n\n"
        "### What stops the loop from running forever?\n\n"
        "A rubric computed in code, not left to the model, stops it. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"], outline=outline)
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
        "# Title\n\n"
        "## One\n\n"
        "### What stops the loop from running forever.\n\n"
        "A rubric computed in code, not left to the model, stops it. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    colon = (
        "# Title\n\n"
        "## One\n\n"
        "### What stops the loop from running forever:\n\n"
        "A rubric computed in code, not left to the model, stops it. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "question_heading" in gate(period, urls=["https://a"], outline=outline).signature()
    assert "question_heading" in gate(colon, urls=["https://a"], outline=outline).signature()


def test_a_heading_ending_in_a_question_mark_fails():
    """The row is unconditional: a heading ending in `?` fails with no
    outline handed to `check` at all."""
    body = (
        "# Title\n\n"
        "## Is the harness safe to run unattended?\n\n"
        "A rubric computed in code stops it, not a model's own judgment. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"])
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
        "# Title\n\n"
        "## One\n\n"
        "### A rubric in code stops the loop\n\n"
        "The rubric decides when the loop stops, never a model's own "
        "judgment. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"], outline=outline)
    assert "question_heading" not in score.signature(), score.report()


def test_a_clean_paper_passes_question_heading():
    """`GOOD` has no interrogative heading and no outline is handed to it,
    so the row passes by construction."""
    assert "question_heading" not in gate(GOOD, URLS).signature()


def test_a_heading_inside_a_fence_is_not_a_heading():
    """#509. A `##` line inside a fenced code block is not paper structure,
    in every row that scans headings: `question_headings`,
    `last_prose_heading`, `has_body` (`sections_without_prose`), and
    `top_level_sections`, the boundary helper others build on. The same
    line outside the fence still fails `question_heading`.
    """
    fenced = (
        "## Real heading\n\n"
        "Real prose describes a heading question with a rubric here today [1].\n\n"
        "## Another heading\n\n"
        "More real prose closes the section out today [1].\n\n"
        "```markdown\n"
        "## Is this a heading?\n"
        "more fence text\n"
        "```\n"
    )
    outline = {"sections": [{"heading": "Real heading", "key_questions": ["Is this a heading?"]}]}

    assert paper_check.question_headings(fenced, outline) == []
    assert set(paper_check.top_level_sections(fenced)) == {"real heading", "another heading"}
    # The fence sits after "Another heading", so a heading scan that reads
    # it unmasked would report the fenced line as the paper's last section,
    # not "Another heading".
    assert paper_check.last_prose_heading(fenced) == "Another heading"
    assert paper_check.sections_without_prose(fenced, 5) == []

    unfenced = (
        "## Real heading\n\n"
        "Real prose describes a heading question with a rubric here today [1].\n\n"
        "## Is this a heading?\n\n"
        "more fence text\n\n"
        "## Another heading\n\n"
        "More real prose closes the section out today [1].\n"
    )
    assert "Is this a heading?" in paper_check.question_headings(unfenced, outline)


def test_a_fenced_heading_does_not_satisfy_the_sections_row():
    """#509. A fenced markdown example naming a required heading must not
    let `sections` (`missing_sections`) believe that section is present.
    """
    body = (
        "# Title\n\n"
        "## Abstract\n\nSummary text here today. [1]\n\n"
        "```markdown\n"
        "## Introduction\n"
        "example only\n"
        "```\n\n"
        "## References\n\n1. https://a\n"
    )
    assert paper_check.missing_sections(body, ("abstract", "introduction", "references")) == ["introduction"]


def test_the_recorded_fixture_paper_passes_question_heading(run_dir, stub_renderer):
    """`task paper` assembles a paper with no heading that pastes a
    question, under `assemble_gate`'s own production call."""
    from conftest import build_run  # noqa: PLC0415
    import stages  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    score = stages.assemble_gate(
        body, run.ledger, allowed_domains=run.allowed_domains, loop_doctrine=run.loop_doctrine
    )
    names = {c.name for c in score.checks}
    assert "question_heading" in names
    assert score.passed, score.report()


# -- P6, the paper does not narrate the harness --------------------------------


def test_the_creatine_sentence_fails_policy_leak():
    """The exact sentence from #412. The finished creatine paper spent whole
    paragraphs reporting that no preprint was found, and this is the one the
    ticket quotes. `arxiv.org` was the host admitted for that run, the same
    way a biomedical librarian would admit it today."""
    body = (
        "# Title\n\n"
        "## Introduction\n\nA point about creatine. [1]\n\n"
        "No study identified for this mechanism was hosted on arxiv.org.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"], allowed_domains=("arxiv.org",))
    assert "policy_leak" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "policy_leak")
    assert "arxiv.org" in row.detail


def test_an_allowlist_host_in_body_prose_fails():
    """A host from the run's allowlist in a body section fails. The same
    host in Methods or References passes: #478 fills Methods with the
    admitted-host list by design, and References is the citation list."""
    host = "example-journal.org"
    body_hit = f"# Title\n\n## Introduction\n\nThe team searched {host} for evidence. [1]\n\n## References\n\n1. https://a\n"
    assert "policy_leak" in gate(body_hit, urls=["https://a"], allowed_domains=(host,)).signature()

    methods_ok = (
        "# Title\n\n"
        "## Introduction\n\nA point. [1]\n\n"
        f"## Methods\n\nThe run searched {host} for evidence.\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "policy_leak" not in gate(methods_ok, urls=["https://a"], allowed_domains=(host,)).signature()

    references_ok = f"# Title\n\n## Introduction\n\nA point. [1]\n\n## References\n\n1. https://{host}/x\n"
    assert (
        "policy_leak"
        not in gate(references_ok, urls=[f"https://{host}/x"], allowed_domains=(host,)).signature()
    )


def test_methods_may_name_admitted_hosts():
    """The Methods exemption, on its own: #478 writes Methods from the run
    record, and it names the admitted hosts by design."""
    host = "example-journal.org"
    body = (
        "# Title\n\n"
        "## Introduction\n\nA point. [1]\n\n"
        f"## Methods\n\nSources were retrieved from {host} and {host}/archive.\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"], allowed_domains=(host,))
    assert "policy_leak" not in score.signature(), score.report()


def test_the_references_section_may_name_hosts():
    """The References exemption, on its own: the reference list is where a
    host name belongs."""
    host = "example-journal.org"
    body = f"# Title\n\n## Introduction\n\nA point. [1]\n\n## References\n\n1. https://{host}/paper\n"
    score = gate(body, urls=[f"https://{host}/paper"], allowed_domains=(host,))
    assert "policy_leak" not in score.signature(), score.report()


def test_the_three_phrases_fail():
    """The three retrieval phrases #412 names, each in an otherwise
    ordinary sentence."""
    sentences = {
        "preprint search": "The preprint search turned up nothing usable here. [1]",
        "search scope": "The search scope excluded several relevant databases. [1]",
        "no study was hosted on": "No study was hosted on a site this run could reach. [1]",
    }
    for phrase, sentence in sentences.items():
        body = f"# Title\n\n## Introduction\n\n{sentence}\n\n## References\n\n1. https://a\n"
        score = gate(body, urls=["https://a"])
        assert "policy_leak" in score.signature(), (phrase, score.report())


def test_a_paper_that_never_names_a_host_passes():
    """A clean paper, with no search host and no retrieval language, passes
    by construction."""
    body = (
        "# Title\n\n"
        "## Introduction\n\nCreatine reduces lean mass loss during immobilization. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    assert "policy_leak" not in gate(body, urls=["https://a"]).signature()


def test_the_writer_message_names_no_allowlist_host_belt():
    """`policy_leak` is the belt behind the stripped delegation message
    (`tests/test_paper.py`). This is the Python-side row that still catches
    a leak if the strip is ever bypassed."""
    body = "# Title\n\n## Introduction\n\nThe result came from arxiv.org, which this run searched. [1]\n\n## References\n\n1. https://a\n"
    assert "policy_leak" in gate(body, urls=["https://a"], allowed_domains=("arxiv.org",)).signature()


def test_the_recorded_fixture_paper_passes_policy_leak(run_dir, stub_renderer):
    """`task paper` assembles a paper that names no search host and
    narrates no retrieval boundary, under `assemble_gate`'s own production
    call. #452 #465 #412."""
    from conftest import build_run  # noqa: PLC0415
    import stages  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    score = stages.assemble_gate(
        body, run.ledger, allowed_domains=run.allowed_domains, loop_doctrine=run.loop_doctrine
    )
    names = {c.name for c in score.checks}
    assert "policy_leak" in names


# -- P7, the abstract is written last ---------------------------------------


def _single_source_ledger(text: str, url: str = "https://a") -> evidence.Ledger:
    ledger = evidence.Ledger("/nonexistent")
    source = ledger.add_source(evidence.SourceDocument(title="One", url=url, subject="exits"))
    claim = ledger.add_claim(evidence.Claim(text=text, subject="exits", source_ids=[source.id]))
    evidence.corroborate(claim)
    return ledger


def test_an_unhedged_single_source_abstract_fails():
    """A hedge-free sentence in the abstract, beside a `[n]` whose claim is
    single-source, fails and names the sentence."""
    ledger = _single_source_ledger("The loop halts before a person notices")
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices. [1]\n\n"
        "## Introduction\n\nThe loop halts before a person notices, one trial supporting it. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"], ledger=ledger)
    assert "abstract_matches_body" in score.signature(), score.report()
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert "halts before a person notices" in row.detail


def test_a_number_shared_by_a_corroborated_claim_is_not_forced_to_hedge():
    """Two claims can share one reference number. A single-source claim on
    it must not force a hedge onto a sentence citing the other, corroborated
    claim on the same number."""
    ledger = evidence.Ledger("/nonexistent")
    src = ledger.add_source(evidence.SourceDocument(title="One", url="https://a", subject="exits"))
    src2 = ledger.add_source(evidence.SourceDocument(title="Two", url="https://b", subject="exits"))
    single_claim = ledger.add_claim(
        evidence.Claim(text="The loop halts before a person notices", subject="exits", source_ids=[src.id])
    )
    evidence.corroborate(single_claim)
    corroborated_claim = ledger.add_claim(
        evidence.Claim(
            text="A checker catches errors the maker cannot",
            subject="exits",
            source_ids=[src.id, src2.id],
            # #471: `corroborate()` counts attributed bindings, not raw
            # source ids. Both must pass attribution before the claim
            # counts as corroborated.
            attributed_source_ids=[src.id, src2.id],
        )
    )
    evidence.corroborate(corroborated_claim)
    assert corroborated_claim.truth_state == evidence.CORROBORATED
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices. [1]\n\n"
        "## Introduction\n\nThe loop halts before a person notices. [1]\n\n"
        "## References\n\n1. https://a\n2. https://b\n"
    )
    score = gate(body, urls=["https://a", "https://b"], ledger=ledger)
    assert "abstract_matches_body" not in score.signature(), score.report()


def test_an_abstract_number_absent_from_the_body_fails():
    """A citation the abstract uses, and no other section does, fails."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nThe loop halts before a person notices [1]. It also cites [2].\n\n"
        "## Introduction\n\nThe loop halts before a person notices [1].\n\n"
        "## References\n\n1. https://a\n2. https://b\n"
    )
    score = gate(body, urls=["https://a", "https://b"])
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
    score = gate(body, urls=["https://a"])
    assert "abstract_matches_body" in score.signature(), score.report()


def test_improves_is_not_an_overclaim():
    """`ABSTRACT_OVERCLAIM` matches whole words: `improves` is not `proves`."""
    body = (
        "# Title\n\n"
        "## Abstract\n\nCreatine improves lean mass. [1]\n\n"
        "## Introduction\n\nCreatine improves lean mass, on a single source. [1]\n\n"
        "## References\n\n1. https://a\n"
    )
    score = gate(body, urls=["https://a"])
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
    score = gate(body, urls=["https://a"])
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
    score = gate(body, urls=["https://a"])
    row = next(c for c in score.checks if c.name == "abstract_matches_body")
    assert row.passed, row.detail


def test_the_reviewer_card_carries_the_abstract_row():
    """Both the model and Python grade the abstract against the body."""
    from pathlib import Path  # noqa: PLC0415

    folder = Path(__file__).resolve().parents[1]
    card = (folder / "skills" / "reviewer" / "SKILL.md").read_text(encoding="utf-8")
    assert "abstract_matches_body" in card


def test_the_recorded_fixture_paper_passes_abstract_matches_body(run_dir, stub_renderer):
    """`task paper` still assembles with the abstract last, and it matches
    the body it summarizes."""
    from conftest import build_run  # noqa: PLC0415
    import stages  # noqa: PLC0415

    run = build_run(run_dir)
    assert run.run() == 0, "the recorded fixture must still assemble and pass its gate"
    body = run.paper_path.read_text(encoding="utf-8")
    score = stages.assemble_gate(
        body, run.ledger, allowed_domains=run.allowed_domains, loop_doctrine=run.loop_doctrine
    )
    names = {c.name for c in score.checks}
    assert "abstract_matches_body" in names
    assert score.passed, score.report()
