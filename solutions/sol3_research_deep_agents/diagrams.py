"""Turn Mermaid or PlantUML source into one publication figure.

The source is an intermediate representation. It is useful to the diagrammer,
the inventory gate, and the fidelity judge; it is never the published figure.
Only ``imagen-diagrams`` v0.2.0+ may create a diagram PNG for the paper.

    source -> local inventory gate -> imagen-diagrams -> plugin judge -> PNG

``image-gen`` is deliberately absent from this module. That plugin owns cover
and non-diagram artwork. It must not become an alternate diagram renderer.

If the renderer or its image backend is unavailable, the run fails closed with
``<stem>_imagen.prompt.txt`` retained. There is no SVG or deterministic PNG
fallback that can accidentally leak into the PDF.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDERER = HERE / ".cache" / "imagen-diagrams"
SCRIPTS = RENDERER / "skills" / "imagen-diagrams" / "scripts"
RENDERER_THEMES = RENDERER / "skills" / "imagen-diagrams" / "themes"
THEMES = HERE / "themes"

DEFAULT_THEME = "spillwave-light"
MAX_NODES = 12
TIMEOUT = 300
NO_BACKEND = 2
SALT = 3
PIPELINE_VERSION = "imagen-diagrams-v0.2.0"

MERMAID_SUFFIXES = (".mmd", ".mermaid")
PLANTUML_SUFFIXES = (".puml", ".plantuml")

MERMAID_NODE = re.compile(
    r'(\w+)\s*(?:\[\s*"?(.*?)"?\s*\]|\(\s*"?(.*?)"?\s*\)|\{\s*"?(.*?)"?\s*\}|>\s*"?(.*?)"?\s*\])'
)
MERMAID_EDGE = re.compile(r"(-{1,3}[->.=]{1,3}|={2,3}>)")
PUML_NODE = re.compile(
    r"^\s*(?:participant|actor|component|class|node|rectangle|database|queue|state|usecase)\s+"
    r'(?:(?:"([^"]+)")|(\w+))',
    re.M,
)
PUML_EDGE = re.compile(r"^\s*\S+\s*(?:-{1,3}>|<-{1,3}|\.{2,3}>|-{2,})\s*\S+", re.M)


class DiagramTooComplex(ValueError):
    """The diagrammer must combine nodes before an image call is allowed."""


class ImageBackendUnavailable(RuntimeError):
    """No publication PNG can be produced; the caller exits with status 2."""

    exit_code = 2

    def __init__(self, prompt_file: Path, detail: str = "no image backend is available"):
        self.prompt_file = Path(prompt_file)
        super().__init__(f"{detail}; saved prompt at {self.prompt_file}")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def kind_of(path: Path) -> str:
    if path.suffix.lower() in MERMAID_SUFFIXES:
        return "mermaid"
    if path.suffix.lower() in PLANTUML_SUFFIXES:
        return "plantuml"
    raise ValueError(f"not a diagram source: {path.name}")


@dataclass
class Inventory:
    """The labels and relationships the plugin judge must preserve."""

    kind: str = ""
    diagram_type: str = "flowchart"
    labels: list[str] = field(default_factory=list)
    edges: int = 0

    @property
    def nodes(self) -> int:
        return len(self.labels)

    @property
    def too_complex(self) -> bool:
        return self.nodes > MAX_NODES


def inventory(source: str, kind: str) -> Inventory:
    """Read the source locally before spending an image call."""
    if kind == "mermaid":
        labels: list[str] = []
        for match in MERMAID_NODE.finditer(source):
            text = next((group for group in match.groups()[1:] if group), "")
            label = (text or match.group(1)).strip().strip("[]").replace("\\n", " ")
            if label and label not in labels:
                labels.append(label)
        first = source.strip().split("\n", 1)[0]
        diagram_type = first.split()[0] if first else "flowchart"
        edges = len(MERMAID_EDGE.findall(source))
    else:
        labels = []
        for match in PUML_NODE.finditer(source):
            label = (match.group(1) or match.group(2) or "").strip()
            if label and label not in labels:
                labels.append(label)
        diagram_type = "sequence" if "->" in source and "participant" in source else "component"
        edges = len(PUML_EDGE.findall(source))
    return Inventory(kind=kind, diagram_type=diagram_type, labels=labels, edges=edges)


def simplify_instruction(inv: Inventory) -> str:
    surplus = inv.labels[MAX_NODES:]
    return (
        f"This diagram has {inv.nodes} nodes. A figure carries at most {MAX_NODES}. "
        f"Combine related nodes until it fits. Start with: {', '.join(surplus[:6])}. "
        "Keep the concept, drop the implementation detail."
    )


def alt_text(inv: Inventory, topic: str) -> str:
    head = ", ".join(label.strip("[]").replace("\\n", " ") for label in inv.labels[:6])
    more = f", and {inv.nodes - 6} more" if inv.nodes > 6 else ""
    return (
        f"A {inv.diagram_type} diagram of {topic}, showing {head}{more}, "
        f"connected by {inv.edges} relationships."
    )


def available() -> bool:
    """Whether the pinned renderer and its fidelity judge are installed."""
    return (SCRIPTS / "render.py").is_file() and (SCRIPTS / "judge.py").is_file()


def ensure_theme() -> None:
    """Copy this standalone folder's themes into the disposable plugin clone."""
    if not RENDERER_THEMES.is_dir() or not THEMES.is_dir():
        return
    for theme in THEMES.glob("*.yaml"):
        target = RENDERER_THEMES / theme.name
        if not target.exists() or target.read_bytes() != theme.read_bytes():
            shutil.copy2(theme, target)


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    if not environment.get("GOOGLE_API_KEY") and environment.get("GEMINI_API_KEY"):
        environment["GOOGLE_API_KEY"] = environment["GEMINI_API_KEY"]
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=str(HERE),
        text=True,
        capture_output=True,
        check=False,
        timeout=TIMEOUT,
        env=environment,
    )


def prompt_path(source: Path, out_dir: Path) -> Path:
    return Path(out_dir) / f"{source.stem}_imagen.prompt.txt"


def _missing_renderer_prompt(source: Path, topic: str, out_dir: Path, theme: str) -> Path:
    """Leave a recoverable request even when setup has not cloned the plugin."""
    prompt = prompt_path(source, out_dir)
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(
        "\n\n".join(
            [
                "imagen-diagrams v0.2.0 is not installed. Run `task setup`, then retry.",
                f"Topic: {topic}",
                f"Theme: {theme}",
                "Diagram source:",
                source.read_text(encoding="utf-8"),
            ]
        ),
        encoding="utf-8",
    )
    return prompt


def render_png(source: Path, topic: str, out_dir: Path, theme: str = DEFAULT_THEME) -> Path:
    """Ask imagen-diagrams for the only filename publication accepts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not available():
        prompt = _missing_renderer_prompt(source, topic, out_dir, theme)
        raise ImageBackendUnavailable(prompt, "imagen-diagrams v0.2.0 is not installed")

    ensure_theme()
    png = out_dir / f"{source.stem}_imagen.png"
    png.unlink(missing_ok=True)
    proc = _run(
        "render.py",
        [
            "--source",
            str(source),
            "--topic",
            topic,
            "--theme",
            theme,
            "--density",
            "article",
            "--output-dir",
            str(out_dir),
        ],
    )
    prompt = prompt_path(source, out_dir)
    if proc.returncode == NO_BACKEND and prompt.is_file():
        raise ImageBackendUnavailable(prompt)
    if proc.returncode == SALT:
        raise RuntimeError("imagen-diagrams refused a Salt wireframe")
    if proc.returncode != 0 and prompt.is_file():
        detail = (proc.stderr or proc.stdout or "image backend failed").strip()
        raise ImageBackendUnavailable(prompt, detail[:300])
    if proc.returncode != 0 or not png.is_file() or png.stat().st_size < 4096:
        detail = (proc.stderr or proc.stdout or "renderer produced no publication PNG").strip()
        raise RuntimeError(f"imagen-diagrams exited {proc.returncode}: {detail[:400]}")
    return png


def judge(source: Path, png: Path) -> dict:
    """Run the plugin's source-to-image fidelity judge and keep its sidecar."""
    sidecar = png.with_suffix(".judge.json")
    proc = _run(
        "judge.py",
        ["--source", str(source), "--png", str(png), "--sidecar", str(sidecar)],
    )
    try:
        verdict = json.loads(proc.stdout)
    except json.JSONDecodeError:
        try:
            verdict = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            verdict = {"pass": False, "misses": ["the plugin judge returned no JSON"]}
    if proc.returncode != 0:
        verdict["pass"] = False
        verdict.setdefault("misses", []).append(f"the plugin judge exited {proc.returncode}")
    return verdict


@dataclass
class Figure:
    """A source plus an accepted imagen-diagrams publication PNG."""

    name: str
    source: Path
    png: Path | None = None
    alt: str = ""
    theme: str = DEFAULT_THEME
    polished: bool = False
    score: float = 0.0
    hash: str = ""
    note: str = ""
    misses: list[str] = field(default_factory=list)

    @property
    def best(self) -> Path | None:
        if self.polished and self.png and self.png.name.endswith("_imagen.png"):
            return self.png
        return None

    def sidecar(self) -> dict:
        return {
            "name": self.name,
            "source": self.source.name,
            "source_hash": self.hash,
            "theme": self.theme,
            "png": self.png.name if self.png else None,
            "alt": self.alt,
            "polished": self.polished,
            "score": self.score,
            "note": self.note,
            "misses": self.misses,
            "renderer": PIPELINE_VERSION,
        }


def audit_path(source: Path, out_dir: Path) -> Path:
    return Path(out_dir) / f"{source.stem}.imagen.json"


def render(  # noqa: PLR0913
    src: Path | str,
    out_dir: Path | str,
    *,
    topic: str = "the system",
    theme_name: str = DEFAULT_THEME,
    polish: bool = True,
    force: bool = False,
    describe=None,
) -> Figure:
    """Render and judge one source; ``polish`` is retained but cannot bypass PNG."""
    del polish, describe
    source_path = Path(src)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = source_path.read_text(encoding="utf-8")
    inv = inventory(source, kind_of(source_path))
    if inv.too_complex:
        raise DiagramTooComplex(simplify_instruction(inv))

    stamp = digest(source + theme_name + PIPELINE_VERSION)
    audit = audit_path(source_path, output)
    if not force and audit.is_file():
        cached = json.loads(audit.read_text(encoding="utf-8"))
        png = output / cached["png"] if cached.get("png") else None
        if (
            cached.get("source_hash") == stamp
            and cached.get("polished") is True
            and png is not None
            and png.is_file()
            and png.name.endswith("_imagen.png")
        ):
            return Figure(
                name=source_path.stem,
                source=source_path,
                png=png,
                alt=cached.get("alt", ""),
                theme=cached.get("theme", theme_name),
                polished=True,
                score=float(cached.get("score", 1.0)),
                hash=stamp,
                note="unchanged, reused",
                misses=[],
            )

    png = render_png(source_path, topic, output, theme_name)
    verdict = judge(source_path, png)
    passed = verdict.get("pass") is True
    misses = [str(item) for item in verdict.get("misses", [])]
    figure = Figure(
        name=source_path.stem,
        source=source_path,
        png=png,
        alt=alt_text(inv, topic),
        theme=theme_name,
        polished=passed,
        score=1.0 if passed else 0.0,
        hash=stamp,
        note="accepted by the imagen-diagrams judge" if passed else "plugin judge rejected the PNG",
        misses=misses,
    )
    audit.write_text(json.dumps(figure.sidecar(), indent=2) + "\n", encoding="utf-8")
    return figure


def render_all(src_dir: Path | str, out_dir: Path | str, **kwargs) -> list[Figure]:
    source_dir = Path(src_dir)
    return [
        render(path, out_dir, **kwargs)
        for path in sorted(source_dir.iterdir())
        if path.suffix.lower() in MERMAID_SUFFIXES + PLANTUML_SUFFIXES
    ]


def demo() -> None:
    mermaid = 'flowchart LR\n  A["Plan"] --> B["Search"]\n  B --> C{"Grounded?"}\n'
    inv = inventory(mermaid, "mermaid")
    assert inv.labels == ["Plan", "Search", "Grounded?"]
    assert inv.edges == 2
    assert not inv.too_complex
    figure = Figure(
        name="loop",
        source=Path("loop.mmd"),
        png=Path("loop_imagen.png"),
        polished=True,
    )
    assert figure.best == Path("loop_imagen.png")
    figure.png = Path("loop.png")
    assert figure.best is None, "a non-plugin PNG must never become the published figure"


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src")
    parser.add_argument("--out", default=None)
    parser.add_argument("--topic", default="the system")
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    if args.demo:
        demo()
        print("diagrams: all demo assertions passed")
        return 0
    if not args.src:
        parser.error("--src is required unless --demo is used")

    source = Path(args.src)
    output = Path(args.out) if args.out else (source if source.is_dir() else source.parent)
    try:
        figures = (
            [render(source, output, topic=args.topic, theme_name=args.theme, force=args.force)]
            if source.is_file()
            else render_all(
                source,
                output,
                topic=args.topic,
                theme_name=args.theme,
                force=args.force,
            )
        )
    except ImageBackendUnavailable as exc:
        print(f"image backend unavailable: {exc}", file=sys.stderr)
        return exc.exit_code
    for figure in figures:
        status = "accepted" if figure.best else "rejected"
        print(f"{figure.name:<32} {status:<9} {figure.note}")
    return 0 if all(figure.best for figure in figures) else 1


if __name__ == "__main__":
    raise SystemExit(main())
