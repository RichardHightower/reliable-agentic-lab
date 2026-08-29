"""Turn a figure concept into a publication image.

The Mermaid or PlantUML source is an intermediate form. It never reaches the
reader. `imagen-diagrams` renders it into a themed PNG, and the PNG is the
figure. A white paper that prints diagram syntax has published its notes.

    draw()   diagrammer writes source -> render -> judge -> simplify -> repeat

Three attempts, then stop. A render loop with no ceiling is a render loop that
spends a budget redrawing the same overcrowded graph, because the fix is always
"simplify" and a model asked to simplify its own work tends to rename things.

The renderer is the installed `imagen-diagrams` plugin, cloned by `task setup`
into `.cache/`. Its auto policy is authoritative: `imagen`, then `grok`, then
`codex`. When none is on PATH, it writes the themed prompt beside the intended
PNG and exits 2. A paper cannot claim a publication-quality figure it did not
render.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
RENDERER = FOLDER / ".cache" / "imagen-diagrams"
SCRIPTS = RENDERER / "skills" / "imagen-diagrams" / "scripts"
RENDERER_THEMES = RENDERER / "skills" / "imagen-diagrams" / "themes"
THEMES = FOLDER / "themes"

DEFAULT_THEME = "spillwave-navy"
ASPECT = "16:9"
MAX_ATTEMPTS = 3
TIMEOUT = 300

# render.py's exit code for a Salt wireframe, which it refuses on purpose.
SALT = 3
# imagen-diagrams's documented fail-closed status. Its render script leaves
# <stem>_imagen.prompt.txt and a JSON sidecar before returning this status.
NO_BACKEND = 2

SUFFIX = {"mermaid": ".mmd", "plantuml": ".puml"}


class ImageBackendUnavailable(RuntimeError):
    """No approved image backend is available; the caller must exit 2."""

    exit_code = 2

    def __init__(self, prompt_file: Path):
        self.prompt_file = Path(prompt_file)
        super().__init__(f"no image backend is on PATH; saved prompt at {self.prompt_file}")


@dataclass
class Figure:
    name: str
    section: str = ""
    caption: str = ""
    path: str = ""
    source: str = ""
    attempts: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def rendered(self) -> bool:
        return bool(self.path)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "section": self.section,
            "caption": self.caption,
            "path": self.path,
            "attempts": self.attempts,
            "misses": self.misses,
        }


def available() -> bool:
    """Whether the renderer clone is present and runnable."""
    return (SCRIPTS / "render.py").exists() and (SCRIPTS / "judge.py").exists()


def ensure_theme() -> None:
    """Copy this folder's themes into the renderer clone.

    v0.2.0 ships built-in themes and the fixed Imagen 0.6 CLI adapter. This
    solution still owns `spillwave-navy`, so copy that local theme into the
    disposable plugin clone before each render.
    """
    if not RENDERER_THEMES.is_dir() or not THEMES.is_dir():
        return
    for theme in THEMES.glob("*.yaml"):
        target = RENDERER_THEMES / theme.name
        if not target.exists() or target.read_bytes() != theme.read_bytes():
            target.write_bytes(theme.read_bytes())


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    # Running the script by path puts its own directory on sys.path, which is
    # how its sibling imports resolve.
    return subprocess.run(
        ["python3", str(SCRIPTS / script), *args],
        cwd=str(FOLDER),
        text=True,
        capture_output=True,
        check=False,
        timeout=TIMEOUT,
    )


def render(source: Path, topic: str, out_dir: Path, theme: str = DEFAULT_THEME) -> Path | None:
    """Render with imagen-diagrams. The plugin owns backend selection and prompts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_theme()
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
    png = out_dir / f"{Path(source).stem}_imagen.png"
    prompt_file = png.with_suffix(".prompt.txt")
    if png.exists() and png.stat().st_size >= 32:
        return png
    if proc.returncode == NO_BACKEND and prompt_file.is_file():
        raise ImageBackendUnavailable(prompt_file)
    if proc.returncode == SALT:
        # A Salt wireframe needs the PlantUML JAR, not an image model. Handing
        # the prompt to `imagen` anyway produces a picture of a form, which is
        # worse than no figure because it looks like a rendering.
        return None
    return None


def judge(source: Path, png: Path) -> dict:
    """Ask the renderer's own fidelity judge what the image lost."""
    sidecar = png.with_suffix(".judge.json")
    proc = _run(
        "judge.py",
        ["--source", str(source), "--png", str(png), "--sidecar", str(sidecar)],
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"pass": False, "misses": ["the judge returned no JSON"], "nodes": [], "edges": 0}


def draw(  # noqa: PLR0913  (every one of these is a distinct render input)
    turns,
    *,
    name: str,
    concept: str,
    section: str,
    topic: str,
    out_dir: Path,
    theme: str = DEFAULT_THEME,
    max_attempts: int = MAX_ATTEMPTS,
) -> Figure:
    """Draw one figure, simplifying on every judged miss."""
    figure = Figure(name=name, section=section)
    out_dir = Path(out_dir)

    if not available():
        figure.misses = ["the renderer is not installed. Run `task setup`."]
        return figure

    feedback = ""
    for attempt in range(1, max_attempts + 1):
        figure.attempts = attempt
        drawn = turns.diagram(name, concept, feedback)
        figure.caption = drawn.get("caption", "")
        figure.source = drawn.get("source", "")
        suffix = SUFFIX.get(drawn.get("language", "mermaid"), ".mmd")

        out_dir.mkdir(parents=True, exist_ok=True)
        source_path = out_dir / f"{name}{suffix}"
        source_path.write_text(figure.source, encoding="utf-8")

        png = render(source_path, topic, out_dir, theme)
        if png is None:
            # No image backend on PATH, or the renderer refused this source.
            # Redrawing does not add a backend, so stop asking.
            figure.misses = ["the renderer produced no image"]
            return figure

        verdict = judge(source_path, png)
        if verdict.get("pass"):
            figure.path = str(png.relative_to(out_dir.parent))
            figure.misses = []
            return figure

        figure.misses = list(verdict.get("misses", []))
        feedback = "; ".join(figure.misses)

    # Out of attempts. Keep the last image and record what it lost, so the
    # check report says the figure is imperfect instead of pretending it is not.
    figure.path = str(
        (out_dir / f"{name}{suffix}").with_name(f"{name}_imagen.png").relative_to(out_dir.parent)
    )
    return figure
