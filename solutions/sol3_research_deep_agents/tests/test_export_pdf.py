"""PDF assembly cannot reopen the removed SVG/plain-PNG publication path."""

import export_pdf


def test_pdf_accepts_only_imagen_diagrams_publication_assets():
    assert export_pdf.publication_figure_target("figures/loop_imagen.png")
    assert not export_pdf.publication_figure_target("figures/loop.svg")
    assert not export_pdf.publication_figure_target("figures/loop.png")
    assert not export_pdf.publication_figure_target("figures/loop_imagen.svg")
