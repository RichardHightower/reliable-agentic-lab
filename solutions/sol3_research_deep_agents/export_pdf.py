"""Render a finished Sol3 whitepaper as a print-ready PDF.

This file is deliberately local to the Deep Agents solution.  It turns the
pipeline's deterministic Markdown artifact and audited local diagrams into a
reader-friendly PDF; it neither calls a model nor changes the research record.

    python3 export_pdf.py work/paper/topic/whitepaper.md --out output/pdf/topic.pdf
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

# ReportLab is an optional artifact dependency, not part of the standalone
# Deep Agents runtime.  Keep imports inside the export path so the workshop's
# "every module imports with no SDK" smoke test remains a true bare-Python
# test.  These names are assigned by `_load_reportlab()` immediately before a
# PDF is built.
colors = None
TA_CENTER = TA_LEFT = None
letter = inch = None
ParagraphStyle = getSampleStyleSheet = None
BaseDocTemplate = Frame = Image = KeepTogether = None
NextPageTemplate = PageBreak = PageTemplate = Paragraph = Spacer = ImageReader = None

PAGE_WIDTH, PAGE_HEIGHT = 612, 792  # Letter, in PostScript points.
MARGIN = 0.72 * 72
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
NAVY = INK = MUTED = ICE = ORANGE = TEAL = None
DATE = date.today().strftime("%d %B %Y").lstrip("0")

HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)
IMAGE = re.compile(r"^!\[([^\]]+)\]\(([^)]+)\)\s*$")
CITATION = re.compile(r"\[(\d+)\]")
REFERENCE = re.compile(r"^(\d+)\.\s+(.*)$")


def _load_reportlab() -> None:
    """Load the optional PDF stack only when the export command is invoked."""
    global colors, TA_CENTER, TA_LEFT, letter, inch, ParagraphStyle, getSampleStyleSheet
    global BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak
    global PageTemplate, Paragraph, Spacer, ImageReader, NAVY, INK, MUTED, ICE, ORANGE, TEAL
    if colors is not None:
        return
    try:
        from reportlab.lib import colors as reportlab_colors
        from reportlab.lib.enums import TA_CENTER as center, TA_LEFT as left
        from reportlab.lib.pagesizes import letter as letter_page
        from reportlab.lib.units import inch as inch_unit
        from reportlab.lib.styles import ParagraphStyle as paragraph_style, getSampleStyleSheet as samples
        from reportlab.platypus import (
            BaseDocTemplate as doc_template,
            Frame as frame,
            Image as image,
            KeepTogether as keep_together,
            NextPageTemplate as next_page_template,
            PageBreak as page_break,
            PageTemplate as page_template,
            Paragraph as paragraph,
            Spacer as spacer,
        )
        from reportlab.lib.utils import ImageReader as image_reader
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF export needs ReportLab. Use the bundled workspace Python or install reportlab."
        ) from exc
    colors, TA_CENTER, TA_LEFT, letter, inch = reportlab_colors, center, left, letter_page, inch_unit
    ParagraphStyle, getSampleStyleSheet = paragraph_style, samples
    BaseDocTemplate, Frame, Image, KeepTogether = doc_template, frame, image, keep_together
    NextPageTemplate, PageBreak, PageTemplate = next_page_template, page_break, page_template
    Paragraph, Spacer, ImageReader = paragraph, spacer, image_reader
    NAVY = colors.HexColor("#1A365D")
    INK = colors.HexColor("#1B2437")
    MUTED = colors.HexColor("#4A5B70")
    ICE = colors.HexColor("#EEF2F7")
    ORANGE = colors.HexColor("#D9772A")
    TEAL = colors.HexColor("#2AA8BB")


def inline(text: str) -> str:
    """Escape model prose while retaining compact, readable citation markers."""
    # Helvetica covers the Latin publication text but not arbitrary CJK source
    # titles. Dropping unsupported title glyphs is better than printing black
    # squares; the English title fragment and source URL remain intact.
    text = text.translate(
        str.maketrans({"\u2011": "-", "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'"})
    )
    text = "".join(char for char in text if ord(char) < 128).strip()
    safe = html.escape(text, quote=False)
    safe = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#1A365D">\1</font>', safe)
    safe = safe.replace("**", "")
    return CITATION.sub(r'<super><font color="#1A365D">[\1]</font></super>', safe)


def parsed_sections(markdown: str) -> list[tuple[str, list[str | tuple[str, str]]]]:
    """Keep the pipeline's section order and image placement intact."""
    matches = list(HEADING.finditer(markdown))
    sections: list[tuple[str, list[str | tuple[str, str]]]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        raw = markdown[match.end() : end].strip()
        blocks: list[str | tuple[str, str]] = []
        if match.group(1).strip().lower() == "references":
            blocks.extend(line.strip() for line in raw.splitlines() if line.strip())
            sections.append((match.group(1), blocks))
            continue
        for block in re.split(r"\n\s*\n", raw):
            text = block.strip()
            if not text:
                continue
            image = IMAGE.match(text)
            if image:
                blocks.append((image.group(1), image.group(2)))
            else:
                blocks.append(text.replace("\n", " "))
        sections.append((match.group(1), blocks))
    return sections


def publication_figure_target(target: str) -> bool:
    """PDF diagram assets come only from the imagen-diagrams output contract."""
    return Path(target).name.endswith("_imagen.png")


def publication_stats(sections: list[tuple[str, list[str | tuple[str, str]]]]) -> str:
    """Describe this paper on its cover using counts derived from its body."""
    sources = sum(
        1
        for heading, blocks in sections
        if heading.strip().lower() == "references"
        for block in blocks
        if isinstance(block, str) and REFERENCE.match(block)
    )
    figures = sum(
        1 for _heading, blocks in sections for block in blocks if isinstance(block, tuple)
    )
    body_sections = sum(
        1 for heading, _blocks in sections if heading.strip().lower() != "references"
    )
    return (
        f"{sources} cited sources  •  {figures} technical figures  •  "
        f"{body_sections} evidence-backed sections"
    )


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.3,
            leading=10,
            textColor=ORANGE,
            alignment=TA_CENTER,
            spaceAfter=14,
            tracking=1.1,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=30,
            leading=35,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=19,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=25,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=13,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=23,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.2,
            leading=15.2,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=9,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.3,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=5,
            spaceAfter=11,
        ),
        "reference": ParagraphStyle(
            "reference",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=10.5,
            textColor=INK,
            leftIndent=14,
            firstLineIndent=-14,
            spaceAfter=4,
            wordWrap="CJK",
        ),
    }


def image_flowable(path: Path, caption: str, style: ParagraphStyle) -> KeepTogether:
    image = ImageReader(str(path))
    width, height = image.getSize()
    max_height = 3.35 * inch
    scale = min(CONTENT_WIDTH / width, max_height / height)
    figure = Image(str(path), width=width * scale, height=height * scale)
    return KeepTogether([figure, Paragraph(inline(caption), style)])


def cover(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(ICE)
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    canvas.setFillColor(ORANGE)
    canvas.rect(MARGIN, PAGE_HEIGHT - 0.58 * inch, CONTENT_WIDTH, 4, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.rect(MARGIN, 0.58 * inch, CONTENT_WIDTH * 0.38, 3, fill=1, stroke=0)
    canvas.restoreState()


def body_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7DFEA"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_HEIGHT - 0.48 * inch, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 0.48 * inch)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 0.36 * inch, "LOOP ENGINEERING BEST PRACTICES")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 0.36 * inch, f"RESEARCH WHITE PAPER  |  {DATE}")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, 0.38 * inch, "Evidence-backed design patterns for production agent loops")
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 0.38 * inch, str(doc.page))
    canvas.restoreState()


def build(markdown: Path, output: Path) -> dict:
    _load_reportlab()
    raw = markdown.read_text(encoding="utf-8")
    title_line, _, remainder = raw.partition("\n")
    title = title_line.lstrip("# ").strip()
    sections = parsed_sections(remainder)
    style = styles()

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(output),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.72 * inch,
        bottomMargin=0.62 * inch,
        title=title,
        author="Sol3 Research Deep Agents",
    )
    frame = doc.leftMargin, doc.bottomMargin, doc.width, doc.height
    doc.addPageTemplates(
        [
            PageTemplate("cover", [Frame(*frame)], onPage=cover),
            PageTemplate("body", [Frame(*frame)], onPage=body_page),
        ]
    )

    story = [
        Spacer(1, 1.45 * inch),
        Paragraph("RESEARCH WHITE PAPER", style["eyebrow"]),
        Paragraph(inline(title), style["title"]),
        Paragraph(
            "Evidence-backed design patterns for bounded, debuggable, and resilient production agent loops.",
            style["subtitle"],
        ),
        Spacer(1, 0.35 * inch),
        Paragraph(publication_stats(sections), style["cover_meta"]),
        Spacer(1, 0.11 * inch),
        Paragraph(f"Research completed {DATE}", style["cover_meta"]),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    for heading, blocks in sections:
        if heading.lower() == "references":
            # Let references use the space left after the conclusion. Forcing
            # a new page can strand one short concluding paragraph on an
            # otherwise blank page. The section style keeps the heading with
            # the first reference when the remaining space is genuinely tight.
            story.append(Paragraph(heading, style["section"]))
            for block in blocks:
                if not isinstance(block, str):
                    continue
                match = REFERENCE.match(block)
                if match:
                    number, rest = match.groups()
                    story.append(Paragraph(f"<b>{number}.</b> {inline(rest)}", style["reference"]))
                else:
                    story.append(Paragraph(inline(block), style["reference"]))
            continue

        story.append(Paragraph(inline(heading), style["section"]))
        for block in blocks:
            if isinstance(block, tuple):
                caption, target = block
                if not publication_figure_target(target):
                    raise RuntimeError(
                        f"PDF rejected non-publication figure {target!r}; "
                        "diagram assets must be judged *_imagen.png files"
                    )
                figure = markdown.parent / target
                if figure.exists():
                    story.append(image_flowable(figure, caption, style["caption"]))
                else:
                    story.append(Paragraph(f"Figure unavailable: {inline(caption)}", style["caption"]))
            else:
                story.append(Paragraph(inline(block), style["body"]))

    doc.build(story)
    figure_inventory = [
        Path(target).name
        for _heading, blocks in sections
        for block in blocks
        if isinstance(block, tuple)
        for _caption, target in [block]
    ]
    return {
        "source": str(markdown),
        "pdf": str(output),
        "pages": doc.page,
        "figures": figure_inventory,
        "bytes": output.stat().st_size,
    }


def sidecar_path(output: Path) -> Path:
    return Path(f"{output}.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--theme", default="arctic-fox")
    args = parser.parse_args(argv)
    metadata = build(args.markdown, args.out)
    metadata["theme"] = args.theme
    sidecar = sidecar_path(args.out)
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    print(sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
