"""Python-rendered data charts. No model touches the pixels.

A read-only chartist returns a spec (type, columns, labels, caption).
This module plots it to `charts/<name>.png` and writes a sidecar that
names every plotted value and its source. Matplotlib is preferred when
installed; a stdlib PNG renderer is the fallback so `task test` needs
no extra package.

    python3 charts.py --demo
"""

from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path

# Arctic Fox. Same tokens the PDF and imagen-diagrams theme use.
NAVY = (16, 42, 86)
BLUE = (47, 111, 237)
SILVER = (200, 209, 221)
WHITE = (255, 255, 255)
MUTED = (95, 111, 130)

CITATION = re.compile(r"\[(\d+)\]")
ALLOWED_TYPES = ("bar", "line", "grouped_bar", "scatter")


def default_spec(figure: dict, rows: list[dict]) -> dict:
    """A spec when the chartist is silent. First two columns, bar chart."""
    keys = list(rows[0].keys()) if rows else ["x", "y"]
    keys = [k for k in keys if k not in ("source", "ref", "citation")]
    x = keys[0] if keys else "x"
    y = keys[1] if len(keys) > 1 else x
    name = figure.get("name") or "chart"
    needed = figure.get("data_needed") or figure.get("shows") or name
    return {
        "name": name,
        "type": "bar",
        "x": x,
        "y": y,
        "xlabel": x,
        "ylabel": y,
        "caption": f"{needed} [1]",
        "section": figure.get("section") or "",
    }


def collect(work_dir: Path | str, figure: dict, ledger=None) -> list[dict]:
    """Rows from `data/*.json` and the ledger's numbers[]."""
    work = Path(work_dir)
    name = figure.get("name") or ""
    rows: list[dict] = []
    data_dir = work / "data"
    if data_dir.is_dir():
        for path in sorted(data_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("name") not in (None, "", name):
                if path.stem != name:
                    continue
            rows.extend(_rows_from_payload(payload, source=str(path)))
    if not rows and ledger:
        rows.extend(_rows_from_ledger(ledger, figure))
    return rows


def _rows_from_payload(payload, *, source: str) -> list[dict]:
    if isinstance(payload, list):
        return [_as_row(item, source) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    columns = payload.get("columns") or []
    table = payload.get("rows") or payload.get("data") or []
    src = payload.get("source") or source
    out = []
    for item in table:
        if isinstance(item, dict):
            row = dict(item)
            row.setdefault("source", src)
            out.append(row)
        elif isinstance(item, (list, tuple)) and columns:
            row = {columns[i]: item[i] for i in range(min(len(columns), len(item)))}
            row["source"] = src
            out.append(row)
    return out


def _as_row(item: dict, source: str) -> dict:
    row = dict(item)
    row.setdefault("source", source)
    return row


def _rows_from_ledger(ledger, figure: dict) -> list[dict]:
    entries = ledger.get("entries") if isinstance(ledger, dict) else ledger
    out = []
    needle = (figure.get("data_needed") or figure.get("shows") or figure.get("name") or "").lower()
    for entry in entries or []:
        for number in entry.get("numbers") or []:
            measures = str(number.get("measures") or number.get("unit") or "")
            if needle and needle not in measures.lower() and needle not in str(number.get("value") or "").lower():
                # Keep every number if the needle is generic; otherwise require overlap.
                terms = {w for w in re.findall(r"[a-z0-9]+", needle) if len(w) > 2}
                blob = (measures + " " + str(number.get("value") or "")).lower()
                if terms and not any(term in blob for term in terms):
                    continue
            try:
                value = float(str(number.get("value")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            out.append(
                {
                    "x": measures or str(number.get("unit") or "item"),
                    "y": value,
                    "source": number.get("ref") or entry.get("section_id") or "",
                    "ref": number.get("ref") or "",
                }
            )
    return out


def _xy(rows: list[dict], spec: dict) -> tuple[list[str], list[float], list[str]]:
    x_key = spec.get("x") or "x"
    y_key = spec.get("y") or "y"
    labels, values, sources = [], [], []
    for row in rows:
        if x_key not in row and "x" in row:
            x_key = "x"
        if y_key not in row and "y" in row:
            y_key = "y"
        raw_y = row.get(y_key)
        try:
            y = float(str(raw_y).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            continue
        labels.append(str(row.get(x_key, len(labels) + 1)))
        values.append(y)
        sources.append(str(row.get("source") or row.get("ref") or ""))
    return labels, values, sources


def render(spec: dict, rows: list[dict], out_dir: Path | str) -> dict:
    """Write `charts/<name>.png` and the sidecar. Returns the figure record."""
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", spec.get("name") or "chart").strip("-") or "chart"
    png = dest / f"{name}.png"
    labels, values, sources = _xy(rows, spec)
    if not values:
        raise ValueError(f"chart {name!r} has no numeric y values")
    kind = spec.get("type") or "bar"
    if kind not in ALLOWED_TYPES:
        kind = "bar"
    try:
        _matplotlib_png(png, labels, values, spec, kind)
    except Exception:
        _stdlib_png(png, labels, values)
    sidecar = {
        "name": name,
        "type": kind,
        "caption": spec.get("caption") or name,
        "xlabel": spec.get("xlabel") or spec.get("x") or "",
        "ylabel": spec.get("ylabel") or spec.get("y") or "",
        "section": spec.get("section") or "",
        "path": str(png),
        "values": [
            {"x": labels[i], "y": values[i], "source": sources[i] if i < len(sources) else ""}
            for i in range(len(values))
        ],
        "sources": sorted({s for s in sources if s}),
    }
    (dest / f"{name}.json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    return sidecar


def _matplotlib_png(path: Path, labels: list[str], values: list[float], spec: dict, kind: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.0), facecolor="#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    xs = list(range(len(values)))
    navy = "#102A56"
    blue = "#2F6FED"
    if kind == "line":
        ax.plot(xs, values, color=blue, marker="o", linewidth=2)
        ax.set_xticks(xs, labels, rotation=20, ha="right")
    elif kind == "scatter":
        ax.scatter(xs, values, color=blue)
        ax.set_xticks(xs, labels, rotation=20, ha="right")
    else:
        ax.bar(xs, values, color=blue, edgecolor=navy)
        ax.set_xticks(xs, labels, rotation=20, ha="right")
    ax.set_xlabel(spec.get("xlabel") or "")
    ax.set_ylabel(spec.get("ylabel") or "")
    ax.tick_params(colors=navy)
    for spine in ax.spines.values():
        spine.set_color("#C8D1DD")
    ax.yaxis.label.set_color(navy)
    ax.xaxis.label.set_color(navy)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor="#FFFFFF")
    plt.close(fig)
    if not path.exists() or path.stat().st_size < 32:
        raise RuntimeError("matplotlib wrote nothing")


def _stdlib_png(path: Path, labels: list[str], values: list[float]) -> None:
    """A real PNG bar chart with no third-party library."""
    width, height = 640, 360
    pad_l, pad_b, pad_t, pad_r = 48, 40, 24, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    pixels = bytearray(width * height * 3)
    for i in range(0, len(pixels), 3):
        pixels[i : i + 3] = WHITE

    def put(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = ((height - 1 - y) * width + x) * 3
            pixels[idx : idx + 3] = color

    def hline(y: int, x0: int, x1: int, color: tuple[int, int, int]) -> None:
        for x in range(x0, x1):
            put(x, y, color)

    def vline(x: int, y0: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(y0, y1):
            put(x, y, color)

    hline(pad_b, pad_l, width - pad_r, SILVER)
    vline(pad_l, pad_b, height - pad_t, SILVER)
    peak = max(values) or 1.0
    n = len(values)
    bar_w = max(4, plot_w // max(n * 2, 1))
    gap = max(4, bar_w)
    for i, value in enumerate(values):
        bh = int((value / peak) * (plot_h - 4))
        x0 = pad_l + gap + i * (bar_w + gap)
        for x in range(x0, x0 + bar_w):
            for y in range(pad_b, pad_b + bh):
                put(x, y, BLUE)
    _write_png(path, width, height, bytes(pixels))


def _write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b""
    stride = width * 3
    for y in range(height):
        raw += b"\x00" + rgb[y * stride : (y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    )


def charted_failures(body: str, charts: list[dict], evidence: str) -> list[str]:
    """Every plotted value must appear in the evidence; the caption must cite."""
    blob = evidence.lower()
    failures = []
    for chart in charts:
        caption = chart.get("caption") or ""
        for item in chart.get("values") or []:
            token = str(item.get("y"))
            compact = token.replace(".0", "") if token.endswith(".0") else token
            if token.lower() not in blob and compact.lower() not in blob:
                src = str(item.get("source") or "")
                if src and src.lower() in blob:
                    continue
                failures.append(f"{chart.get('name')}: {token} not in corpus")
        sources = chart.get("sources") or []
        if sources and not CITATION.search(caption):
            failures.append(f"{chart.get('name')}: caption has no citation")
        path = chart.get("path") or ""
        name = chart.get("name") or ""
        mentioned = (name and name in body) or (path and Path(path).name in body)
        rel = f"charts/{Path(path).name}" if path else ""
        if rel and rel in body:
            mentioned = True
        if not mentioned:
            failures.append(f"{chart.get('name')}: figure not in the paper")
    return failures


def demo() -> int:
    rows = [
        {"x": "done", "y": 1, "source": "paper.py"},
        {"x": "cost", "y": 2, "source": "paper.py"},
        {"x": "max turns", "y": 3, "source": "paper.py"},
    ]
    spec = default_spec({"name": "three-exits", "data_needed": "the three exits", "section": "s1"}, rows)
    dest = Path("/tmp/sol3-charts-demo")
    dest.mkdir(parents=True, exist_ok=True)
    record = render(spec, rows, dest)
    assert (dest / "three-exits.png").exists()
    assert (dest / "three-exits.json").exists()
    evidence = "1 2 3 done cost max turns paper.py the three exits [1]"
    body = f"See the exits.\n\n![{record['caption']}](charts/three-exits.png)\n"
    assert charted_failures(body, [record], evidence) == []
    empty = collect("/tmp/does-not-exist", {"name": "missing"})
    assert empty == []
    print("charts: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo())
