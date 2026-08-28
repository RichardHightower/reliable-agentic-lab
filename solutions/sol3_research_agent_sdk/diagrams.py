"""Turn a figure concept into a publication image.

The Mermaid or PlantUML source is an intermediate form. It never reaches the
reader. `imagen-diagrams` renders it into a themed PNG, and the PNG is the
figure. A white paper that prints diagram syntax has published its notes.

    draw()   diagrammer writes source -> render -> judge -> simplify -> repeat

Three attempts, then stop. A render loop with no ceiling is a render loop that
spends a budget redrawing the same overcrowded graph, because the fix is always
"simplify" and a model asked to simplify its own work tends to rename things.

The renderer is a clone, not a dependency. `task setup` puts it in `.cache/`.
When it is not there, or when no image backend is on PATH, `draw` records the
miss and the run continues without that figure. A missing figure is a weaker
paper. A failed run over a missing figure is no paper.
"""

from __future__ import annotations

import json
import shutil
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

SUFFIX = {"mermaid": ".mmd", "plantuml": ".puml"}


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

    v0.1.0 resolves a theme against its own `themes/` directory only, whatever
    the README says about `.imagen-diagrams/themes/`. The clone lives in
    `.cache/`, which is disposable, so the copy runs before every render rather
    than once at setup.
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


def _generate(prompt_file: Path, png: Path) -> bool:
    """Draw the image with the `imagen` CLI, using the flags it actually has.

    imagen-diagrams builds the themed prompt, and that is the part worth having.
    Its own backend then calls `imagen generate --prompt-file X --aspect Y
    --output Z`, and the published gemini-imagen CLI has none of those three
    options: the prompt is an argument or stdin, output is `-o`, and aspect is
    `--aspect-ratio`. Both v0.1.0 and main have this mismatch.

    So the renderer builds the prompt and judges the result, and this function
    is the one call in between. Fix it upstream and this collapses back into
    `render.py` doing the whole job.
    """
    if not shutil.which("imagen"):
        return False
    proc = subprocess.run(
        ["imagen", "generate", "-o", str(png), "--aspect-ratio", ASPECT],
        input=prompt_file.read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        check=False,
        timeout=TIMEOUT,
    )
    return proc.returncode == 0 and png.exists() and png.stat().st_size >= 32


def render(source: Path, topic: str, out_dir: Path, theme: str = DEFAULT_THEME) -> Path | None:
    """Render one source file. Returns the PNG, or None when nothing was drawn."""
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
    if png.exists() and png.stat().st_size >= 32:
        return png
    if proc.returncode == SALT:
        # A Salt wireframe needs the PlantUML JAR, not an image model. Handing
        # the prompt to `imagen` anyway produces a picture of a form, which is
        # worse than no figure because it looks like a rendering.
        return None
    prompt_file = png.with_suffix(".prompt.txt")
    if prompt_file.exists() and _generate(prompt_file, png):
        return png
    return None


def judge(source: Path, png: Path) -> dict:
    """Ask the renderer's own fidelity judge what the image lost."""
    proc = _run("judge.py", ["--source", str(source), "--png", str(png)])
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
