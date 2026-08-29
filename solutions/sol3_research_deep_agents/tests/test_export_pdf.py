"""PDF assembly cannot reopen the removed SVG/plain-PNG publication path."""

from pathlib import Path

import export_pdf


def test_pdf_accepts_only_imagen_diagrams_publication_assets():
    assert export_pdf.publication_figure_target("figures/loop_imagen.png")
    assert not export_pdf.publication_figure_target("figures/loop.svg")
    assert not export_pdf.publication_figure_target("figures/loop.png")
    assert not export_pdf.publication_figure_target("figures/loop_imagen.svg")


def test_cover_stats_are_derived_from_the_paper():
    sections = export_pdf.parsed_sections(
        "## Abstract\n\nGrounded prose. [1]\n\n"
        "## Findings\n\n![A useful figure](figures/loop_imagen.png)\n\n"
        "## References\n\n1. https://example.com/one\n2. https://example.com/two\n"
    )
    assert export_pdf.publication_stats(sections) == (
        "2 cited sources  •  1 technical figures  •  2 evidence-backed sections"
    )


def test_pdf_sidecar_sits_beside_the_pdf():
    assert export_pdf.sidecar_path(Path("paper.pdf")) == Path("paper.pdf.json")


def test_inline_text_drops_glyphs_helvetica_cannot_render():
    rendered = export_pdf.inline("可靠性 SRE - Training")
    assert rendered == "SRE - Training"
    assert "■" not in rendered
