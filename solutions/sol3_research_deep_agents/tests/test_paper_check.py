"""The hard gates. Everything here is settled without asking anyone."""

from __future__ import annotations

import evidence
import paper_check
import pytest

URLS = ["https://a.example/one", "https://b.example/two"]
GOOD = (
    "# Exit conditions\n\n"
    "## Abstract\n\nA loop without an exit spends until someone notices. [1]\n\n"
    "## Introduction\n\nThree exits cover the observed cases. [1][2]\n\n"
    "![A flowchart of the three exits](figures/exits.svg)\n\n"
    "## Limitations\n\nThis paper measures two runtimes only. [2]\n\n"
    "## References\n\n1. https://a.example/one\n2. https://b.example/two\n"
)


def test_demo_assertions_hold():
    paper_check.demo()


def test_a_clean_paper_passes():
    assert paper_check.check(GOOD, URLS).passed


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
    score = paper_check.check(body, URLS)
    assert not score.passed
    assert row in score.signature()


def test_an_em_dash_is_replaced_not_argued_about():
    score = paper_check.check(GOOD.replace("spends until", "spends — until"), URLS)
    assert "style" in score.signature()


def test_diagram_source_in_the_body_blocks():
    """The figure is the artifact. A reader never sees `flowchart TB`."""
    leaked = GOOD.replace("![A", "```mermaid\nflowchart TB\n  A --> B\n```\n\n![A")
    assert "no_diagram_source" in paper_check.check(leaked, URLS).signature()


def test_a_figure_is_not_an_uncited_claim():
    """An image paragraph asserts nothing, so demanding a citation on it would
    fail every paper that has a figure."""
    assert "cited" not in paper_check.check(GOOD, URLS).signature()


def test_a_numbered_procedure_is_not_a_reference_list():
    assert paper_check.reference_rows("## Steps\n\n1. do this\n2. do that\n") == []
    assert len(paper_check.reference_rows(GOOD)) == 2


def test_missing_limitations_warns_but_ships():
    trimmed = GOOD.replace("## Limitations\n\nThis paper measures two runtimes only. [2]\n\n", "")
    score = paper_check.check(trimmed, URLS)
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
    assert "single_source_caveat" in paper_check.check(GOOD, URLS, ledger=ledger).signature()

    caveated = GOOD.replace(
        "Three exits cover the observed cases. [1][2]",
        "Three exits cover the observed cases, on a single source. [1][2]",
    )
    assert (
        "single_source_caveat" not in paper_check.check(caveated, URLS, ledger=ledger).signature()
    )


def test_the_caveat_must_be_local_to_the_claim():
    """A caveat in the abstract does not cover a claim four sections later."""
    ledger, _ = ledger_with_single_source()
    elsewhere = GOOD.replace(
        "A loop without an exit spends until someone notices. [1]",
        "A loop without an exit spends until someone notices, on a single source. [1]",
    )
    assert "single_source_caveat" in paper_check.check(elsewhere, URLS, ledger=ledger).signature()


def test_the_reference_list_is_not_searched_for_a_caveat():
    """Every URL appears there, so scanning it would test the bibliography."""
    sections = paper_check.body_sections(GOOD)
    assert not any("References" in section for section in sections)


def test_a_contradicted_claim_never_reaches_the_paper():
    ledger, claim = ledger_with_single_source()
    evidence.corroborate(claim, contradicted=True)
    body = GOOD.replace("Three exits cover", f"{claim.id} Three exits cover")
    assert "no_contradicted" in paper_check.check(body, URLS, ledger=ledger).signature()


def test_the_signature_is_what_failed_not_how_it_was_worded():
    """`gates.decide` compares two signatures to spot a loop that is not
    converging, so the signature must be stable across retries."""
    first = paper_check.check(GOOD.replace("[2]", "[9]"), URLS).signature()
    second = paper_check.check(GOOD.replace("[2]", "[8]"), URLS).signature()
    assert first == second == ("grounded",)


# -- the body --------------------------------------------------------------

HOLLOW = (
    "# Exit conditions\n\n## Abstract\n\n## Introduction\n\n## Limitations\n\n"
    "## References\n\n1. https://a.example/one\n2. https://b.example/two\n"
)


def test_a_paper_with_no_body_is_blocked():
    """Every other gate checks content that is not there. Grounding passes with
    no citations to dangle, `cited` passes with no claim paragraphs, and style
    passes with no text to hold an em dash. Only the soft word count noticed."""
    score = paper_check.check(HOLLOW, URLS)
    assert not score.passed
    assert score.signature() == ("has_body",)


def test_every_other_hard_gate_passes_on_the_hollow_paper():
    """This is why `has_body` had to be added rather than tightened."""
    score = paper_check.check(HOLLOW, URLS)
    green = {c.name for c in score.checks if c.passed}
    assert {"grounded", "cited", "style", "sections", "references"} <= green


def test_a_stub_section_is_blocked():
    thin = GOOD.replace("Three exits cover the observed cases. [1][2]", "Yes. [1]")
    assert "has_body" in paper_check.check(thin, URLS).signature()


def test_a_section_of_only_a_figure_is_blocked():
    """A figure still owes the reader an explanation."""
    figure_only = GOOD.replace(
        "Three exits cover the observed cases. [1][2]\n\n"
        "![A flowchart of the three exits](figures/exits.svg)",
        "![A flowchart of the three exits](figures/exits.svg)",
    )
    assert "has_body" in paper_check.check(figure_only, URLS).signature()


def test_references_and_figures_owe_no_prose():
    appendix = GOOD.replace(
        "## References",
        "## Figures\n\n![A sequence of the roles](figures/roles.svg)\n\n## References",
    )
    assert "has_body" not in paper_check.check(appendix, URLS).signature()


def test_a_real_paper_still_passes():
    assert paper_check.check(GOOD, URLS).passed
