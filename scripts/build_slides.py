#!/usr/bin/env python3
"""Render the mermaid blocks in each deck, then write a deck Marp can use.

Marp does not draw mermaid. Left alone, a diagram slide shows the room the words
`flowchart TB` instead of a diagram. This renders each block to an SVG once and
writes `slides.build.md` next to the source, with the block replaced by an image.

    python scripts/build_slides.py

Edit `slides.md`. Never edit `slides.build.md`. It is generated.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "slides"
BLOCK = re.compile(r"^```mermaid\n(.*?)^```\n", re.M | re.S)
MMDC = ["npx", "-y", "@mermaid-js/mermaid-cli"]
# Mermaid's default type is too small once a wide diagram is scaled to fit.
CONFIG = SLIDES / "mermaid.json"
VIEWBOX = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')

# A 1280x720 slide, less the heading and the caption that share it.
MAX_W = 1060
MAX_H = 460
SLIDE_RATIO = MAX_W / MAX_H


def slide_ids(text: str) -> list[tuple[int, str]]:
    """Where each slide id sits in the file, so a block can be named after it."""
    return [(m.start(), m.group(1)) for m in re.finditer(r"^id:\s*(\S+)\s*$", text, re.M)]


def id_before(offset: int, ids: list[tuple[int, str]]) -> str:
    found = "diagram"
    for pos, name in ids:
        if pos > offset:
            break
        found = name
    return found


def viewbox(svg: Path) -> tuple[float, float]:
    """The drawing's real size. mermaid-cli puts it in the viewBox and then
    sets width to 100 percent, which is what makes it overflow."""
    match = VIEWBOX.search(svg.read_text(encoding="utf-8")[:600])
    if not match:
        return float(MAX_W), float(MAX_H)
    return float(match.group(1)), float(match.group(2))


def render(source: str, out: Path) -> None:
    """Draw one block. The hash in the file name means an unchanged block is a
    cache hit, which keeps a rebuild from costing 30 seconds of node startup."""
    if out.exists():
        return
    mmd = out.with_suffix(".mmd")
    mmd.write_text(source, encoding="utf-8")
    subprocess.run(
        [*MMDC, "-i", str(mmd), "-o", str(out), "-b", "transparent", "-c", str(CONFIG)],
        check=True,
        capture_output=True,
    )
    mmd.unlink()


def build(deck: Path) -> int:
    text = deck.read_text(encoding="utf-8")
    ids = slide_ids(text)
    images = deck.parent / "images"
    images.mkdir(exist_ok=True)
    count = 0

    def swap(match: re.Match) -> str:
        nonlocal count
        body = match.group(1)
        digest = hashlib.sha256(body.encode()).hexdigest()[:8]
        name = f"diagram-{id_before(match.start(), ids)}-{digest}.svg"
        render(body, images / name)
        # mermaid-cli writes width="100%", so the SVG fills whatever box it
        # lands in and a tall flowchart runs off the slide. Pick the dimension
        # that actually binds, and let Marp keep the aspect ratio.
        width, height = viewbox(images / name)
        fit = f"h:{MAX_H}" if width / height < SLIDE_RATIO else f"w:{MAX_W}"
        count += 1
        return f"![{fit}]({images.name}/{name})\n"

    built = BLOCK.sub(swap, text)
    (deck.parent / "slides.build.md").write_text(built, encoding="utf-8")
    return count


def main() -> int:
    total = 0
    for deck in sorted(SLIDES.glob("session-*/slides.md")):
        n = build(deck)
        total += n
        print(f"{deck.parent.name}: {n} diagrams")
    print(f"{total} diagrams, {len(list(SLIDES.glob('session-*')))} decks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
