"""The PDF export keeps Markdown as source and Arctic Fox as the visual contract."""

from __future__ import annotations

import json

import pdf_report
import pytest


def test_markdown_parser_keeps_headings_figures_lists_and_tables():
    blocks = pdf_report.markdown_blocks(
        "# Paper\n\n## Finding\n\n- one\n\n![Control](diagrams/control.png)\n\n"
        "| Exit | Meaning |\n| --- | --- |\n| done | accepted |\n"
    )
    assert [(block.kind, block.text) for block in blocks[:4]] == [
        ("heading", "Paper"),
        ("heading", "Finding"),
        ("bullet", "one"),
        ("image", "Control"),
    ]
    assert blocks[-1].rows == [["Exit", "Meaning"], ["done", "accepted"]]


def test_pdf_palette_is_loaded_from_the_plugin_theme(tmp_path):
    theme = tmp_path / "arctic-fox.yaml"
    theme.write_text("palette:\n  primary: \"#010203\"\n  accent: \"#AABBCC\"\n")

    palette = pdf_report.theme_palette(theme)

    assert palette["primary"] == "#010203"
    assert palette["accent"] == "#AABBCC"
    assert palette["background"] == "#FFFFFF"


def test_pdf_export_records_the_arctic_fox_theme(tmp_path):
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    paper = tmp_path / "paper.md"
    paper.write_text(
        "# Loop Engineering\n\n## Abstract\n\nA bounded control loop.\n\n"
        "## References\n\n1. https://example.com\n",
        encoding="utf-8",
    )

    output = tmp_path / "paper.pdf"
    record = pdf_report.build_pdf(paper, output)

    assert output.read_bytes().startswith(b"%PDF")
    assert record["theme"] == "arctic-fox"
    assert record["pages"] >= 2
    assert json.loads((tmp_path / "paper.pdf.json").read_text())["theme"] == "arctic-fox"


def test_e2e_pdf_refuses_a_report_without_its_required_figures(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text("# Loop Engineering\n\n## Abstract\n\nNo figure was rendered.\n")

    with pytest.raises(ValueError, match="requires at least 2"):
        pdf_report.build_pdf(paper, tmp_path / "paper.pdf", min_figures=2)
