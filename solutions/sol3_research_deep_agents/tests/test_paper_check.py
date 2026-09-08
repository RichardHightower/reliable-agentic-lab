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
    "## References\n\n1. https://docs.langchain.com/one\n2. https://docs.claude.com/two\n"
)


def gate(body, urls=URLS, **kwargs):
    """Structural checks keep the old short-paper floor."""
    kwargs.setdefault("min_words", 0)
    kwargs.setdefault("min_section_words", 5)
    return paper_check.check(body, urls, **kwargs)


def test_demo_assertions_hold():
    paper_check.demo()


def test_a_clean_paper_passes():
    assert gate(GOOD, URLS).passed


def test_cli_uses_the_evidence_bibliography_when_sources_are_not_separate(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(paper_check, "MIN_WORDS", 0)
    monkeypatch.setattr(paper_check, "MIN_SECTION_WORDS", 5)
    ledger = evidence.Ledger(tmp_path / "evidence")
    for url in URLS:
        source = ledger.add_source(evidence.SourceDocument(title=url, url=url, subject="exits"))
        claim = ledger.add_claim(
            evidence.Claim(text=f"Claim from {url}", subject="exits", source_ids=[source.id])
        )
        evidence.corroborate(claim)
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
    "# Exit conditions\n\n## Abstract\n\ndone, then cost, then max turns. [1]\n\n## Introduction\n\n## Limitations\n\n"
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
