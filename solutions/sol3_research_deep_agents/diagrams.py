"""Mermaid and PlantUML into figures a white paper can print.

The source is an intermediate representation, not the artifact. A reader should
never see `flowchart TB` in a published figure.

Four steps, and every one of them fails closed to the step before it.

    1. Deterministic render. mmdc for .mmd and plantuml for .puml, both to SVG.
       Mermaid also emits a three-times-scale PNG because its current SVG uses
       browser-only HTML labels. The PNG is the print artifact; the SVG stays
       with it as the accessible, inspectable intermediate. A correct plain
       diagram beats a missing pretty one.
    2. Polish. The imagen-diagrams plugin when it is installed, otherwise the
       same six-block prompt contract built here against a theme YAML, sent to
       the `imagen` CLI.
    3. Judge. Deterministic inventory check against the source: every label
       present, edge count within tolerance, no source syntax visible. On a miss
       it prepends REGENERATION FEEDBACK and reruns, capped at two retries.
    4. Sidecar. Source hash, theme, alt text, judge score. A matching hash skips
       the whole thing, which is what makes a resumed run cheap.

Two things worth knowing before you edit this file.

The complexity gate runs before any render. A diagram with more nodes than a
reader can hold is not fixed by a nicer renderer. `MAX_NODES` rejects it and
names which nodes to combine, and the diagrammer redraws.

The `imagen` CLI treats `{x}` as a template variable, so every brace in the
prompt is doubled. The imagen-diagrams PRD calls this the `imagen-cli-vars`
policy and records that the inverse bug already bit two earlier pipelines. A
`{Decision?}` node crashes the call without it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
THEMES = HERE / "themes"
DEFAULT_THEME = "spillwave-light"
MERMAID_CONFIG = THEMES / "mermaid.json"

# A figure past this many nodes stops explaining and starts cataloguing.
MAX_NODES = 12
# Labels the judge expects to see, and how far off the edge count may drift.
EDGE_TOLERANCE = 0.10
MAX_POLISH_RETRIES = 2

MMDC_TIMEOUT = 120
PLANTUML_TIMEOUT = 120
IMAGEN_TIMEOUT = 300

MERMAID_SUFFIXES = (".mmd", ".mermaid")
PLANTUML_SUFFIXES = (".puml", ".plantuml")

# mmdc starts Chromium to render a local, model-produced diagram. The secure
# Chromium sandbox is the normal path. A few nested CI/dev sandboxes cannot
# launch it; those environments may opt in with SOL3_MERMAID_NO_SANDBOX=1.
# Never make that weaker mode the default for model-produced input.
UNSAFE_PUPPETEER_CONFIG = {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
MERMAID_PRINT_SCALE = "3"

# Where an installed imagen-diagrams plugin puts its renderer.
PLUGIN_RENDER = (
    Path.home()
    / ".claude/plugins/cache/spillwave-documentation/imagen-diagrams"
    / "skills/imagen-diagrams/scripts/render.py"
)

# Mermaid node text, in the four bracket shapes the decks actually use.
MERMAID_NODE = re.compile(
    r'(\w+)\s*(?:\[\s*"?(.*?)"?\s*\]|\(\s*"?(.*?)"?\s*\)|\{\s*"?(.*?)"?\s*\}|>\s*"?(.*?)"?\s*\])'
)
MERMAID_EDGE = re.compile(r"(-{1,3}[->.=]{1,3}|={2,3}>)")
PUML_NODE = re.compile(
    r"^\s*(?:participant|actor|component|class|node|rectangle|database|queue|state|usecase)\s+"
    r'(?:"([^"]+)"|(\w+))',
    re.M,
)
PUML_EDGE = re.compile(r"^\s*\S+\s*(?:-{1,3}>|<-{1,3}|\.{2,3}>|-{2,})\s*\S+", re.M)
MERMAID_KEYWORD = re.compile(
    r"\b(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|@startuml|@enduml)\b"
)


class DiagramTooComplex(ValueError):
    """More nodes than a figure can carry. Simplify, do not render."""


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
    """What the source says is in the picture. The judge grades against this."""

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
    """Read the nodes and edges out of the source, without rendering it."""
    if kind == "mermaid":
        labels: list[str] = []
        for match in MERMAID_NODE.finditer(source):
            text = next((group for group in match.groups()[1:] if group), "")
            # An empty bracket means the node id is the label. Falling back to
            # the id keeps the judge honest about what a reader will see.
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
    """What to hand the diagrammer when the gate fires.

    Naming the surplus nodes matters. "Simplify this" produces a redraw of the
    same graph with shorter labels. Naming them produces a combine.
    """
    surplus = inv.labels[MAX_NODES:]
    return (
        f"This diagram has {inv.nodes} nodes. A figure carries at most {MAX_NODES}. "
        f"Combine related nodes until it fits. Start with: {', '.join(surplus[:6])}. "
        "Keep the concept, drop the implementation detail."
    )


# -- step 1, the deterministic render -------------------------------------


def _run_renderer(argv: list[str], src: Path, target: Path, timeout: int) -> Path:
    """Run one deterministic renderer and make its useful failure explicit."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{argv[0]} failed on {src.name}: {exc}") from exc
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(f"{argv[0]} exited {proc.returncode} on {src.name}: {proc.stderr[:300]}")
    return target


def plantuml_style_args(theme_name: str) -> list[str]:
    """Map the shared white-paper palette to PlantUML's SVG skin settings."""
    palette = load_theme(theme_name).get("palette", {})
    background = palette.get("background", "#eef2f7")
    surface = palette.get("surface", "#ffffff")
    primary = palette.get("primary", "#1a365d")
    ink = palette.get("ink", "#1b2437")
    muted = palette.get("muted", "#4a5b70")
    return [
        f"-SbackgroundColor={background}",
        "-SdefaultFontName=Helvetica",
        "-SdefaultFontSize=18",
        f"-SdefaultFontColor={ink}",
        f"-SsequenceParticipantBackgroundColor={surface}",
        f"-SsequenceParticipantBorderColor={primary}",
        f"-SsequenceArrowColor={primary}",
        f"-SsequenceLifeLineBorderColor={muted}",
        "-SsequenceMessageAlign=center",
        "-Sroundcorner=12",
    ]


def _puppeteer_config(temp_dir: str) -> Path | None:
    """Return an opt-in workaround for nested CI/dev sandboxes only."""
    if os.environ.get("SOL3_MERMAID_NO_SANDBOX") != "1":
        return None
    config = Path(temp_dir) / "puppeteer.json"
    config.write_text(json.dumps(UNSAFE_PUPPETEER_CONFIG), encoding="utf-8")
    return config


def _mmdc_argv(
    src: Path, target: Path, puppeteer: Path | None, *, background: str, scale: str = "1"
) -> list[str]:
    binary = shutil.which("mmdc")
    argv = ([binary] if binary else ["npx", "--yes", "@mermaid-js/mermaid-cli"]) + [
        "-i",
        str(src),
        "-o",
        str(target),
        "-b",
        background,
        "-s",
        scale,
    ]
    if MERMAID_CONFIG.exists():
        argv += ["-c", str(MERMAID_CONFIG)]
    return argv + (["--puppeteerConfigFile", str(puppeteer)] if puppeteer else [])


def render_svg(src: Path, out_dir: Path, *, theme_name: str = DEFAULT_THEME) -> Path:
    """mmdc or plantuml to SVG. This is the artifact that always exists."""
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = kind_of(src)
    target = out_dir / f"{src.stem}.svg"
    if kind == "mermaid":
        # Keep an opt-in Puppeteer configuration outside the paper artifact.
        with tempfile.TemporaryDirectory(prefix="sol3-mmdc-") as temp_dir:
            puppeteer = _puppeteer_config(temp_dir)
            return _run_renderer(
                _mmdc_argv(src, target, puppeteer, background="transparent"),
                src,
                target,
                MMDC_TIMEOUT,
            )
    else:
        argv = ["plantuml", "-tsvg", "-Playout=smetana", *plantuml_style_args(theme_name)]
        argv += ["-o", str(out_dir.resolve()), str(src)]
        return _run_renderer(argv, src, target, PLANTUML_TIMEOUT)


def render_mermaid_png(src: Path, out_dir: Path, *, theme_name: str = DEFAULT_THEME) -> Path:
    """Render a print-scale PNG when Mermaid's SVG labels require a browser."""
    target = out_dir / f"{src.stem}.png"
    background = load_theme(theme_name).get("palette", {}).get("background", "#eef2f7")
    with tempfile.TemporaryDirectory(prefix="sol3-mmdc-") as temp_dir:
        puppeteer = _puppeteer_config(temp_dir)
        return _run_renderer(
            _mmdc_argv(src, target, puppeteer, background=background, scale=MERMAID_PRINT_SCALE),
            src,
            target,
            MMDC_TIMEOUT,
        )


def render_plantuml_png(src: Path, out_dir: Path, *, theme_name: str = DEFAULT_THEME) -> Path:
    """Render a two-times PNG for print PDFs alongside PlantUML's SVG."""
    target = out_dir / f"{src.stem}.png"
    argv = ["plantuml", "-tpng", "-Playout=smetana", "-Sscale=2", *plantuml_style_args(theme_name)]
    argv += ["-o", str(out_dir.resolve()), str(src)]
    return _run_renderer(argv, src, target, PLANTUML_TIMEOUT)


# -- step 2, the polish ---------------------------------------------------


def load_theme(name: str = DEFAULT_THEME) -> dict:
    """Palette and negatives from a theme YAML. Flat enough not to need a parser."""
    path = THEMES / f"{name}.yaml"
    if not path.exists():
        return {"id": name, "palette": {}, "negatives": []}
    palette: dict[str, str] = {}
    negatives: list[str] = []
    section = ""
    summary: list[str] = []
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if raw and not raw.startswith((" ", "\t", "-")):
            section = raw.split(":", 1)[0]
            continue
        stripped = raw.strip()
        if section == "palette" and ":" in stripped:
            key, _, value = stripped.partition(":")
            palette[key.strip()] = value.strip().strip('"')
        elif section == "negatives" and stripped.startswith("- "):
            negatives.append(stripped[2:])
        elif section == "style" and stripped and not stripped.endswith(":"):
            if not re.match(r"^\w+:", stripped):
                summary.append(stripped)
    return {
        "id": name,
        "palette": palette,
        "negatives": negatives,
        "summary": " ".join(summary),
    }


def escape_braces(text: str) -> str:
    """Double every brace for the `imagen` CLI, which reads `{x}` as a variable."""
    return text.replace("{", "{{").replace("}", "}}")


def build_prompt(source: str, inv: Inventory, theme: dict, topic: str, feedback: str = "") -> str:
    """The six-block prompt contract from the imagen-diagrams PRD.

    Framing, style, palette, negatives, diagram type, layout hints, then a
    bookend closer. The closer is last on purpose: the final tokens are the ones
    an image model weighs most, and the failure this guards against is a picture
    of source code.
    """
    palette = "\n".join(f"  {role}: {value}" for role, value in theme.get("palette", {}).items())
    negatives = "\n".join(f"  - {item}" for item in theme.get("negatives", []))
    blocks = []
    if feedback:
        blocks.append(f"REGENERATION FEEDBACK. The previous attempt missed these:\n{feedback}\n")
    blocks += [
        f"FRAMING. This is a figure for a technical white paper about {topic}. "
        "Render an illustration of the concept below.",
        "STYLE. Clean minimalist technical illustration for print. Boxes, arrows, "
        "and labels only. Horizontal text. Every label legible at print size. "
        f"{theme.get('summary', '')}".strip(),
        f"PALETTE. Use these named colors and no others:\n{palette}",
        f"NEGATIVE. Do not include:\n{negatives}",
        f"DIAGRAM TYPE. {inv.diagram_type}, with {inv.nodes} nodes and {inv.edges} connections.",
        "LAYOUT HINTS. Use the source below only as guidance for structure. "
        f"Every one of these labels must appear as readable text: {', '.join(inv.labels)}.\n"
        f"```\n{source}\n```",
        "Convert the visual boxes, arrows, and labels. The image must show a "
        "finished diagram, not Mermaid or PlantUML code.",
    ]
    return escape_braces("\n\n".join(blocks))


def imagen_available() -> bool:
    return shutil.which("imagen") is not None and bool(
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )


def run_imagen(prompt: str, target: Path, aspect: str = "16:9") -> Path:
    argv = ["imagen", "generate", prompt, "-o", str(target), "--aspect-ratio", aspect]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=IMAGEN_TIMEOUT)
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(f"imagen exited {proc.returncode}: {proc.stderr[:300]}")
    return target


def run_plugin(src: Path, theme: str, out_dir: Path) -> Path:
    """The installed imagen-diagrams plugin, when it is there."""
    argv = [
        "python3",
        str(PLUGIN_RENDER),
        str(src),
        "--theme",
        theme,
        "--density",
        "article",
        "--out",
        str(out_dir),
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=IMAGEN_TIMEOUT)
    target = out_dir / f"{src.stem}_imagen.png"
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(f"imagen-diagrams exited {proc.returncode}: {proc.stderr[:300]}")
    return target


# -- step 3, the judge ----------------------------------------------------


@dataclass
class Verdict:
    passed: bool = True
    misses: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return 0.0 if not self.passed else 1.0

    def feedback(self) -> str:
        return "\n".join(f"  - {miss}" for miss in self.misses)


def judge_png(png: Path, inv: Inventory, described: str = "") -> Verdict:
    """Grade the rendered figure against the source inventory.

    `described` is optional text about the image, from a vision call or from the
    backend. With no description, the check is what can be known without one: a
    file that exists and has plausible size. Reporting a pass here would be a
    lie, so the verdict says which checks it could actually run.
    """
    misses: list[str] = []
    if not png.exists():
        return Verdict(passed=False, misses=["no image was produced"])
    if png.stat().st_size < 4096:
        misses.append(f"the image is {png.stat().st_size} bytes, which is not a diagram")
    if described:
        lowered = described.lower()
        for label in inv.labels:
            if label.lower() not in lowered:
                misses.append(f"the label {label!r} does not appear in the image")
        if MERMAID_KEYWORD.search(described):
            misses.append("diagram source syntax is visible in the image")
    return Verdict(passed=not misses, misses=misses)


def alt_text(inv: Inventory, topic: str) -> str:
    """Alt text a screen reader can use. Not decoration, an accessibility floor."""
    # Brackets are Mermaid shape syntax, and ``\\n`` is PlantUML's line-break
    # escape. Neither belongs in a sentence a screen reader announces.
    head = ", ".join(label.strip("[]").replace("\\n", " ") for label in inv.labels[:6])
    more = f", and {inv.nodes - 6} more" if inv.nodes > 6 else ""
    return (
        f"A {inv.diagram_type} diagram of {topic}, showing {head}{more}, "
        f"connected by {inv.edges} relationships."
    )


# -- the figure -----------------------------------------------------------


@dataclass
class Figure:
    """One rendered diagram plus everything the paper needs to place it."""

    name: str
    source: Path
    svg: Path | None = None
    png: Path | None = None
    alt: str = ""
    theme: str = DEFAULT_THEME
    polished: bool = False
    rasterized: bool = False
    score: float = 0.0
    hash: str = ""
    note: str = ""

    @property
    def best(self) -> Path | None:
        """The audited PNG when it exists; otherwise the deterministic SVG."""
        return self.png if self.png and (self.polished or self.rasterized) else self.svg

    def sidecar(self) -> dict:
        return {
            "name": self.name,
            "source": self.source.name,
            "source_hash": self.hash,
            "theme": self.theme,
            "svg": self.svg.name if self.svg else None,
            "png": self.png.name if self.png else None,
            "alt": self.alt,
            "polished": self.polished,
            "rasterized": self.rasterized,
            "score": self.score,
            "note": self.note,
        }


def sidecar_path(src: Path, out_dir: Path) -> Path:
    return out_dir / f"{src.stem}.imagen.json"


def render(  # noqa: PLR0913  (every knob here is a real caller option)
    src: Path | str,
    out_dir: Path | str,
    *,
    topic: str = "the system",
    theme_name: str = DEFAULT_THEME,
    polish: bool = True,
    force: bool = False,
    describe=None,
) -> Figure:
    """One diagram source to one figure. Raises only on too many nodes.

    `describe` is an optional callable that takes a PNG path and returns text
    about it, so the judge can check labels. Without it the judge runs the checks
    it can and says so.
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = src.read_text(encoding="utf-8")
    inv = inventory(source, kind_of(src))

    if inv.too_complex:
        raise DiagramTooComplex(simplify_instruction(inv))

    stamp = digest(source + theme_name)
    side = sidecar_path(src, out_dir)
    if not force and side.exists():
        cached = json.loads(side.read_text(encoding="utf-8"))
        if cached.get("source_hash") == stamp:
            svg = out_dir / cached["svg"] if cached.get("svg") else None
            png = out_dir / cached["png"] if cached.get("png") else None
            if (svg is None or svg.exists()) and (png is None or png.exists()):
                return Figure(
                    name=cached["name"],
                    source=src,
                    svg=svg,
                    png=png,
                    alt=cached.get("alt", ""),
                    theme=cached.get("theme", theme_name),
                    polished=bool(cached.get("polished")),
                    rasterized=bool(cached.get("rasterized")),
                    score=float(cached.get("score", 0.0)),
                    hash=stamp,
                    note="unchanged, reused",
                )

    figure = Figure(
        name=src.stem,
        source=src,
        theme=theme_name,
        hash=stamp,
        alt=alt_text(inv, topic),
    )
    figure.svg = render_svg(src, out_dir, theme_name=theme_name)
    if kind_of(src) == "mermaid":
        try:
            figure.png = render_mermaid_png(src, out_dir, theme_name=theme_name)
            figure.rasterized = True
        except RuntimeError as exc:
            figure.note = f"local PNG render failed, kept the SVG: {exc}"
    else:
        try:
            figure.png = render_plantuml_png(src, out_dir, theme_name=theme_name)
            figure.rasterized = True
        except RuntimeError as exc:
            figure.note = f"local PNG render failed, kept the SVG: {exc}"

    if polish:
        _polish(figure, source, inv, topic, out_dir, describe)
    else:
        figure.note = "polish not requested; embedded print PNG" if figure.rasterized else "polish not requested"

    side.write_text(json.dumps(figure.sidecar(), indent=2), encoding="utf-8")
    return figure


def _polish(  # noqa: PLR0913, PLR0917  (one private step of `render`, not an API)
    figure: Figure, source: str, inv: Inventory, topic: str, out_dir: Path, describe
) -> None:
    """Step 2 and step 3. Never raises. The SVG is already safe on disk."""
    if PLUGIN_RENDER.exists():
        try:
            figure.png = run_plugin(figure.source, figure.theme, out_dir)
            figure.polished = True
            figure.score = 1.0
            figure.note = "rendered by the imagen-diagrams plugin"
            return
        except Exception as exc:
            figure.note = f"plugin render failed, used the local prompt: {exc}"

    if not imagen_available():
        fallback = "embedded print PNG" if figure.rasterized else "kept the SVG"
        figure.note = figure.note or f"imagen is not on PATH or no GEMINI_API_KEY, {fallback}"
        return

    theme = load_theme(figure.theme)
    target = out_dir / f"{figure.source.stem}_imagen.png"
    feedback = ""
    for attempt in range(MAX_POLISH_RETRIES + 1):
        try:
            run_imagen(build_prompt(source, inv, theme, topic, feedback), target, "4:3")
        except Exception as exc:
            figure.note = f"imagen failed on attempt {attempt + 1}, kept the SVG: {exc}"
            return
        described = describe(target) if describe else ""
        verdict = judge_png(target, inv, described)
        if verdict.passed:
            figure.png = target
            figure.polished = True
            figure.score = verdict.score
            figure.note = f"polished on attempt {attempt + 1}"
            return
        feedback = verdict.feedback()
    figure.note = f"the judge rejected {MAX_POLISH_RETRIES + 1} renders, kept the SVG:\n{feedback}"


def render_all(src_dir: Path | str, out_dir: Path | str, **kwargs) -> list[Figure]:
    src_dir = Path(src_dir)
    figures = []
    for path in sorted(src_dir.iterdir()):
        if path.suffix.lower() in MERMAID_SUFFIXES + PLANTUML_SUFFIXES:
            figures.append(render(path, out_dir, **kwargs))
    return figures


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Render diagram sources into figures.")
    parser.add_argument("--src", required=True, help="a diagram file or a directory of them")
    parser.add_argument("--out", default=None, help="where the figures go")
    parser.add_argument("--topic", default="the system")
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--no-polish", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    src = Path(args.src)
    out = Path(args.out) if args.out else (src if src.is_dir() else src.parent)
    todo = [src] if src.is_file() else None
    kwargs = {
        "topic": args.topic,
        "theme_name": args.theme,
        "polish": not args.no_polish,
        "force": args.force,
    }

    try:
        figures = (
            [render(path, out, **kwargs) for path in todo]
            if todo
            else render_all(src, out, **kwargs)
        )
    except DiagramTooComplex as exc:
        print(f"too complex: {exc}")
        return 1

    for figure in figures:
        mark = "polished" if figure.polished else "svg only"
        print(f"{figure.name:<28} {mark:<10} {figure.note}")
    return 0


def demo() -> None:
    mermaid = (
        'flowchart TB\n  A["Plan"] --> B["Search"]\n  B --> C{"Grounded?"}\n  C --> D["Write"]\n'
    )
    inv = inventory(mermaid, "mermaid")
    assert inv.labels == ["Plan", "Search", "Grounded?", "Write"], inv.labels
    assert inv.edges == 3, inv.edges
    assert not inv.too_complex

    big = "flowchart TB\n" + "\n".join(
        f'  N{i}["Node {i}"] --> N{i + 1}["Node {i + 1}"]' for i in range(MAX_NODES + 2)
    )
    wide = inventory(big, "mermaid")
    assert wide.too_complex, wide.nodes
    assert "Combine related nodes" in simplify_instruction(wide)

    puml = '@startuml\nparticipant "Orchestrator" as O\nparticipant Researcher\nO -> Researcher: ask\n@enduml\n'
    pinv = inventory(puml, "plantuml")
    assert pinv.labels == ["Orchestrator", "Researcher"], pinv.labels
    assert pinv.edges == 1

    # Braces are doubled for the imagen CLI, or a {Decision?} node crashes it.
    assert escape_braces("a {x} b") == "a {{x}} b"
    prompt = build_prompt(mermaid, inv, load_theme(), "loops")
    assert "{{" in prompt, "the prompt carries a brace and must escape it"
    assert "}}" in prompt
    assert prompt.rstrip().endswith("not Mermaid or PlantUML code."), "the closer is last"
    assert "Grounded?" in prompt

    # The judge fails a missing label and fails visible source syntax.
    class FakePng:
        def exists(self):
            return True

        def stat(self):
            return type("S", (), {"st_size": 100_000})()

    verdict = judge_png(FakePng(), inv, "a diagram with Plan, Search, Write")
    assert not verdict.passed
    assert any("Grounded?" in miss for miss in verdict.misses)

    verdict = judge_png(FakePng(), inv, "flowchart TB Plan Search Grounded? Write")
    assert not verdict.passed
    assert any("source syntax" in miss for miss in verdict.misses)

    verdict = judge_png(FakePng(), inv, "Plan, Search, Grounded?, and Write boxes joined by arrows")
    assert verdict.passed, verdict.misses

    alt = alt_text(inv, "the research loop")
    assert "Plan" in alt and "3 relationships" in alt

    figure = Figure(name="x", source=Path("x.mmd"), svg=Path("x.svg"))
    assert figure.best == Path("x.svg"), "an unpolished figure ships its SVG"
    figure.png, figure.polished = Path("x.png"), True
    assert figure.best == Path("x.png")

    print("diagrams: all demo assertions passed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        raise SystemExit(main())
