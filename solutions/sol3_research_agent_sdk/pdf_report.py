#!/usr/bin/env python3
"""Render a research paper and its figures as an Arctic Fox PDF.

The Markdown remains the source of truth.  This module is intentionally local
to the Agent SDK solution so an attendee can copy the folder and keep the PDF
export without learning a repository-wide publishing framework.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

THEME = "arctic-fox"
FOLDER = Path(__file__).resolve().parent
THEME_FILE = (
    FOLDER
    / ".cache"
    / "imagen-diagrams"
    / "skills"
    / "imagen-diagrams"
    / "themes"
    / f"{THEME}.yaml"
)
DEFAULT_PALETTE = {
    "background": "#FFFFFF",
    "surface": "#F2F5F9",
    "primary": "#102A56",
    "accent": "#2F6FED",
    "accent_2": "#C8D1DD",
    "muted": "#5F6F82",
}

IMAGE = re.compile(r"^!\[([^]]*)\]\(([^)\s]+)\)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET = re.compile(r"^\s*[-*+]\s+(.+)$")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+)$")
TABLE_DIVIDER = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    level: int = 0
    target: str = ""
    rows: list[list[str]] = field(default_factory=list)


def _table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_blocks(markdown: str) -> list[Block]:
    """Parse the paper subset needed by the report without an HTML engine."""
    lines = markdown.replace("\r\n", "\n").splitlines()
    blocks: list[Block] = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(Block("paragraph", " ".join(part.strip() for part in paragraph)))
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code:
                blocks.append(Block("code", "\n".join(code)))
                code.clear()
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        heading = HEADING.match(line)
        image = IMAGE.match(line)
        bullet = BULLET.match(line)
        numbered = NUMBERED.match(line)
        if heading:
            flush_paragraph()
            blocks.append(Block("heading", heading.group(2), len(heading.group(1))))
        elif image:
            flush_paragraph()
            blocks.append(Block("image", image.group(1), target=image.group(2)))
        elif bullet:
            flush_paragraph()
            blocks.append(Block("bullet", bullet.group(1)))
        elif numbered:
            flush_paragraph()
            blocks.append(Block("numbered", numbered.group(1)))
        elif (
            "|" in line
            and index + 1 < len(lines)
            and TABLE_DIVIDER.match(lines[index + 1])
        ):
            flush_paragraph()
            rows = [_table_row(line)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_table_row(lines[index]))
                index += 1
            blocks.append(Block("table", rows=rows))
            continue
        elif line.strip() in ("---", "***"):
            flush_paragraph()
            blocks.append(Block("rule"))
        elif line.lstrip().startswith(">"):
            flush_paragraph()
            blocks.append(Block("quote", line.lstrip()[1:].strip()))
        else:
            paragraph.append(line)
        index += 1

    flush_paragraph()
    if code:
        blocks.append(Block("code", "\n".join(code)))
    return blocks


def _inline(text: str) -> str:
    """Translate conservative inline Markdown into ReportLab paragraph XML."""
    value = html.escape(text, quote=True)
    value = re.sub(
        r"\[([^]]+)\]\((https?://[^)]+)\)",
        r'<link href="\2" color="#2F6FED">\1</link>',
        value,
    )
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    return value


def theme_palette(path: Path = THEME_FILE) -> dict[str, str]:
    """Load the PDF palette from imagen-diagrams' built-in Arctic Fox theme."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Arctic Fox theme not installed: {path}. Run `task setup`.")
    palette = dict(DEFAULT_PALETTE)
    in_palette = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "palette:":
            in_palette = True
            continue
        if in_palette and raw and not raw.startswith(" "):
            break
        if not in_palette:
            continue
        match = re.match(r'^\s{2}([a-z0-9_]+):\s*["\']?(#[0-9A-Fa-f]{6})', raw)
        if match and match.group(1) in palette:
            palette[match.group(1)] = match.group(2).upper()
    return palette


def build_pdf(
    paper: Path,
    output: Path,
    *,
    theme: str = THEME,
    min_figures: int = 0,
) -> dict:
    """Build and reopen the PDF, returning its durable sidecar record."""
    if theme != THEME:
        raise ValueError(f"unsupported report theme {theme!r}; expected {THEME!r}")
    paper = Path(paper).resolve()
    output = Path(output).resolve()
    if not paper.is_file():
        raise FileNotFoundError(f"paper not found: {paper}")

    markdown = paper.read_text(encoding="utf-8")
    blocks = markdown_blocks(markdown)
    figures = [block for block in blocks if block.kind == "image"]
    if len(figures) < min_figures:
        raise ValueError(
            f"paper has {len(figures)} figures; this export requires at least {min_figures}"
        )
    missing = [block.target for block in figures if not (paper.parent / block.target).is_file()]
    if missing:
        raise FileNotFoundError(f"paper references missing figures: {', '.join(missing)}")

    from pypdf import PdfReader  # noqa: PLC0415 - optional until `task setup`
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.enums import TA_CENTER, TA_LEFT  # noqa: PLC0415
    from reportlab.lib.pagesizes import letter  # noqa: PLC0415
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: PLC0415
    from reportlab.lib.units import inch  # noqa: PLC0415
    from reportlab.platypus import (  # noqa: PLC0415
        HRFlowable,
        Image,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    title = next(
        (block.text for block in blocks if block.kind == "heading" and block.level == 1),
        paper.stem.replace("-", " ").title(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    palette = theme_palette()
    navy = colors.HexColor(palette["primary"])
    blue = colors.HexColor(palette["accent"])
    silver = colors.HexColor(palette["accent_2"])
    surface = colors.HexColor(palette["surface"])
    muted = colors.HexColor(palette["muted"])

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ArcticTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=33,
            textColor=navy,
            alignment=TA_LEFT,
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "ArcticSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=muted,
        ),
        "h1": ParagraphStyle(
            "ArcticH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=navy,
            spaceBefore=16,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "ArcticH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=blue,
            spaceBefore=13,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "ArcticH3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=navy,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ArcticBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=navy,
            spaceAfter=7,
            allowWidows=0,
            allowOrphans=0,
            splitLongWords=True,
        ),
        "list": ParagraphStyle(
            "ArcticList",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            leftIndent=18,
            firstLineIndent=-9,
            textColor=navy,
            spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "ArcticCaption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=muted,
            spaceAfter=10,
        ),
        "quote": ParagraphStyle(
            "ArcticQuote",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=14,
            leftIndent=18,
            borderColor=silver,
            borderWidth=0,
            borderPadding=8,
            backColor=surface,
            textColor=navy,
            spaceAfter=8,
        ),
        "code": ParagraphStyle(
            "ArcticCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.5,
            leading=10,
            textColor=navy,
        ),
    }

    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title=title,
        author="Reliable Agentic Lab",
        subject="Research white paper",
        creator="sol3_research_agent_sdk Arctic Fox PDF exporter",
    )
    story = [
        Spacer(1, 1.2 * inch),
        Paragraph(_inline(title), styles["title"]),
        HRFlowable(width="38%", thickness=4, color=blue, hAlign="LEFT", spaceAfter=20),
        Paragraph("RESEARCH WHITE PAPER", styles["subtitle"]),
        Spacer(1, 0.12 * inch),
        Paragraph("Arctic Fox publication edition", styles["subtitle"]),
        PageBreak(),
    ]

    numbered = 0
    for block in blocks:
        if block.kind == "heading" and block.level == 1:
            continue
        if block.kind == "heading":
            style = styles["h1"] if block.level == 2 else styles["h2"] if block.level == 3 else styles["h3"]
            story.append(Paragraph(_inline(block.text), style))
        elif block.kind == "paragraph":
            story.append(Paragraph(_inline(block.text), styles["body"]))
        elif block.kind == "bullet":
            story.append(Paragraph(f"&#8226;&nbsp; {_inline(block.text)}", styles["list"]))
        elif block.kind == "numbered":
            numbered += 1
            story.append(Paragraph(f"{numbered}.&nbsp; {_inline(block.text)}", styles["list"]))
        elif block.kind == "quote":
            story.append(Paragraph(_inline(block.text), styles["quote"]))
        elif block.kind == "rule":
            story.append(HRFlowable(width="100%", thickness=0.7, color=silver, spaceBefore=5, spaceAfter=8))
        elif block.kind == "code":
            code = Preformatted(block.text, styles["code"], maxLineLength=95)
            wrapper = Table([[code]], colWidths=[doc.width], style=[
                ("BACKGROUND", (0, 0), (-1, -1), surface),
                ("BOX", (0, 0), (-1, -1), 0.5, silver),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])
            story.extend([wrapper, Spacer(1, 8)])
        elif block.kind == "image":
            image_path = (paper.parent / block.target).resolve()
            if image_path.is_file():
                figure = Image(str(image_path))
                figure._restrictSize(doc.width, 4.6 * inch)
                figure.hAlign = "CENTER"
                story.extend([Spacer(1, 5), figure, Paragraph(_inline(block.text), styles["caption"])])
            else:
                story.append(Paragraph(f"Figure unavailable: {_inline(block.text)}", styles["quote"]))
        elif block.kind == "table" and block.rows:
            cells = [[Paragraph(_inline(cell), styles["body"]) for cell in row] for row in block.rows]
            columns = max(len(row) for row in cells)
            table = Table(cells, colWidths=[doc.width / columns] * columns, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), surface),
                ("GRID", (0, 0), (-1, -1), 0.5, silver),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.extend([table, Spacer(1, 8)])

    def cover(canvas, document) -> None:
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, letter[1] - 0.28 * inch, letter[0], 0.28 * inch, fill=1, stroke=0)
        canvas.setFillColor(blue)
        canvas.rect(0, 0, letter[0], 0.12 * inch, fill=1, stroke=0)
        canvas.restoreState()

    def page(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(silver)
        canvas.line(doc.leftMargin, letter[1] - 0.43 * inch, letter[0] - doc.rightMargin, letter[1] - 0.43 * inch)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(doc.leftMargin, letter[1] - 0.32 * inch, title[:78])
        canvas.drawRightString(letter[0] - doc.rightMargin, 0.36 * inch, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=cover, onLaterPages=page)

    reader = PdfReader(str(output))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(reader.pages) < 2 or title not in extracted:
        raise RuntimeError("PDF verification failed: missing pages or title")
    record = {
        "pdf": str(output),
        "source": str(paper),
        "theme": theme,
        "theme_source": str(THEME_FILE),
        "pages": len(reader.pages),
        "figures": [block.target for block in figures],
        "bytes": output.stat().st_size,
    }
    Path(f"{output}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--theme", default=THEME)
    parser.add_argument("--min-figures", type=int, default=0)
    args = parser.parse_args(argv)
    output = args.output or args.paper.with_suffix(".pdf")
    record = build_pdf(args.paper, output, theme=args.theme, min_figures=args.min_figures)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
