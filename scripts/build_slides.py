#!/usr/bin/env python3
"""Render the mermaid blocks in each deck, then write a deck Marp can use.

Marp does not draw mermaid. Left alone, a diagram slide shows the room the words
`flowchart TB` instead of a diagram. This renders each block to an SVG once and
writes `slides.build.md` next to the source, with the block replaced by an image.

    python scripts/build_slides.py

Edit `slides.md`. Never edit `slides.build.md`. It is generated.

Optional: set MERMAID_PUPPETEER_CONFIG to a puppeteer JSON if Chromium is not
where mermaid-cli expects it. In CI-like sandboxes this script will also look
for Playwright's chrome-headless-shell under /opt/pw-browsers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "slides"
BLOCK = re.compile(r"^```mermaid\n(.*?)^```\n", re.M | re.S)
MMDC = ["npx", "-y", "@mermaid-js/mermaid-cli"]
CONFIG = SLIDES / "mermaid.json"
VIEWBOX = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')

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


def find_chrome() -> Path | None:
    env = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env and Path(env).is_file():
        return Path(env)
    bundled = Path(
        "/opt/pw-browsers/chromium_headless_shell-1234/"
        "chrome-headless-shell-linux64/chrome-headless-shell"
    )
    if bundled.is_file():
        return bundled
    matches = sorted(Path("/opt/pw-browsers").glob("**/chrome-headless-shell"))
    return matches[0] if matches else None


def puppeteer_config() -> Path | None:
    env = os.environ.get("MERMAID_PUPPETEER_CONFIG")
    if env and Path(env).is_file():
        return Path(env)
    bundled = SLIDES / "puppeteer.json"
    if bundled.is_file():
        return bundled
    chrome = find_chrome()
    if chrome is None:
        return None
    path = Path(tempfile.gettempdir()) / "mermaid-puppeteer.json"
    path.write_text(
        json.dumps(
            {
                "executablePath": str(chrome),
                "args": ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            }
        ),
        encoding="utf-8",
    )
    return path


def render(source: str, out: Path) -> None:
    """Draw one block. The hash in the file name means an unchanged block is a
    cache hit, which keeps a rebuild from costing 30 seconds of node startup."""
    if out.exists():
        return
    mmd = out.with_suffix(".mmd")
    mmd.write_text(source, encoding="utf-8")
    cmd = [*MMDC, "-i", str(mmd), "-o", str(out), "-b", "transparent", "-c", str(CONFIG)]
    puppeteer = puppeteer_config()
    if puppeteer is not None:
        cmd.extend(["-p", str(puppeteer)])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"mermaid-cli failed for {out.name}\n")
        sys.stderr.write(exc.stderr or exc.stdout or "")
        raise
    finally:
        if mmd.exists():
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
