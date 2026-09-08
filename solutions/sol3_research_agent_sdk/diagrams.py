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
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
RENDERER = FOLDER / ".cache" / "imagen-diagrams"
SCRIPTS = RENDERER / "skills" / "imagen-diagrams" / "scripts"
RENDERER_THEMES = RENDERER / "skills" / "imagen-diagrams" / "themes"
THEMES = FOLDER / "themes"

DEFAULT_THEME = "arctic-fox"
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
        super().__init__(
            f"every approved image backend failed; saved prompt at {self.prompt_file}"
        )


@dataclass
class Figure:
    name: str
    section: str = ""
    caption: str = ""
    path: str = ""
    source: str = ""
    attempts: int = 0
    misses: list[str] = field(default_factory=list)
    # #476 B2: durable. `attempts` here is this call's count; `diagram()`
    # adds whatever budget an earlier commissioning already spent, so the
    # record on disk carries the figure's lifetime total. `dropped` is set
    # only by a `figure_claims` exhaustion, never by a render failure, so
    # `diagram()` can tell "gave up on the claims" from "no image backend".
    dropped: bool = False

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
            "dropped": self.dropped,
        }


def available() -> bool:
    """Whether the renderer clone is present and runnable."""
    return (SCRIPTS / "render.py").exists() and (SCRIPTS / "judge.py").exists()


def ensure_theme() -> None:
    """Copy this folder's themes into the renderer clone.

    v0.2.0 ships Arctic Fox and the fixed Imagen 0.6 CLI adapter. Copy any
    solution-local themes into the disposable clone too, but the publication
    default stays the plugin's built-in `arctic-fox` theme.
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
    env = os.environ.copy()
    # gemini-imagen 0.6.x names this credential GOOGLE_API_KEY even when the
    # operator uses the provider-neutral GEMINI_API_KEY name in the shell.
    if env.get("GEMINI_API_KEY") and not env.get("GOOGLE_API_KEY"):
        env["GOOGLE_API_KEY"] = env["GEMINI_API_KEY"]
    return subprocess.run(
        ["python3", str(SCRIPTS / script), *args],
        cwd=str(FOLDER),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=TIMEOUT,
    )


def _sidecar_backend(sidecar: Path) -> str | None:
    try:
        return json.loads(sidecar.read_text(encoding="utf-8")).get("backend")
    except (OSError, json.JSONDecodeError):
        return None


def _snapshot_failed_attempt(png: Path, backend: str) -> None:
    """Keep each failed backend's prompt and metadata for diagnosis."""
    prompt = png.with_suffix(".prompt.txt")
    sidecar = png.with_suffix(".json")
    for source, suffix in ((prompt, "prompt.txt"), (sidecar, "json")):
        if source.is_file():
            target = png.with_name(f"{png.stem}.{backend}.{suffix}")
            target.write_bytes(source.read_bytes())


DECISION_NODE = re.compile(r"(\b\w+)\{([^{}\n]+)\}")


def for_image_backend(source: Path) -> Path:
    """The source the image backend may see. Same stem, no single-brace nodes.

    Mermaid writes a decision node as `GATE{Gate}`. The renderer copies the
    source into its prompt line for line, and the `imagen` CLI reads `{Gate}`
    as an unfilled template variable and refuses:

        Missing 1 required variable(s): {'Gate'}

    Every backend then fails the same way and the run exits 2. The first live
    run to reach the diagram phase died on it.

    The renderer is a cached clone that `task setup` re-fetches, so the fix
    lives here, before the handoff. `[Gate]` is a rectangle, `{Gate}` is a
    diamond, and the image model draws from a description either way. The
    stem is unchanged so the PNG lands where the caller expects. The original
    file is not touched.
    """
    source = Path(source)
    text = source.read_text(encoding="utf-8")
    safe = DECISION_NODE.sub(r"\1[\2]", text)
    if safe == text:
        return source
    staged = source.parent / ".imagen" / source.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(safe, encoding="utf-8")
    return staged


def render(source: Path, topic: str, out_dir: Path, theme: str = DEFAULT_THEME) -> Path | None:
    """Render with imagen-diagrams. The plugin owns backend selection and prompts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_theme()
    args = [
        "--source",
        str(for_image_backend(source)),
        "--topic",
        topic,
        "--theme",
        theme,
        "--density",
        "article",
        "--output-dir",
        str(out_dir),
    ]
    png = out_dir / f"{Path(source).stem}_imagen.png"
    prompt_file = png.with_suffix(".prompt.txt")
    sidecar = png.with_suffix(".json")

    proc = _run("render.py", args)
    if png.exists() and png.stat().st_size >= 32:
        return png
    if proc.returncode == SALT:
        # A Salt wireframe needs the PlantUML JAR, not an image model. Handing
        # the prompt to an image backend produces a picture of a form.
        return None

    first = _sidecar_backend(sidecar)
    if first:
        _snapshot_failed_attempt(png, first)
    order = ("imagen", "grok", "codex")
    remaining = order[order.index(first) + 1 :] if first in order else ()
    for backend in remaining:
        proc = _run("render.py", [*args, "--backend", backend])
        if png.exists() and png.stat().st_size >= 32:
            return png
        _snapshot_failed_attempt(png, backend)

    if prompt_file.is_file():
        raise ImageBackendUnavailable(prompt_file)
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


# -- #476: a label must agree with the section's claims -----------------------

# Copied from the Deep Agents port's `diagrams.inventory()` label extraction,
# never imported: two standalone folders. The node id must sit immediately
# (mod whitespace) before the bracket; a bare `>` inside an edge arrow
# (`-->`) has no preceding `\w+` there, so it cannot start a match. An
# earlier cut of this parser dropped that leading group, and the bare `>`
# alternative then matched the `>` inside `-->` and won the leftmost-match
# race, gluing a label after an arrow to the node id before it
# (`Gain[Fat-free mass` on `Start --> Gain[Fat-free mass]`).
MERMAID_NODE = re.compile(
    r'(\w+)\s*(?:\[\s*"?(.*?)"?\s*\]|\(\s*"?(.*?)"?\s*\)|\{\s*"?(.*?)"?\s*\}|>\s*"?(.*?)"?\s*\])'
)
MERMAID_PARTICIPANT = re.compile(r"^\s*participant\s+(\w+)(?:\s+as\s+([^\n]+))?", re.M | re.I)
MERMAID_STATE_EDGE = re.compile(r"^\s*(\w+|\[\*\])\s*-->\s*(\w+|\[\*\])", re.M)
PUML_NODE = re.compile(
    r'^\s*(?:participant|actor|component|class|node|rectangle|database|queue|state|usecase)\s+'
    r'(?:"([^"]+)"|(\w+))',
    re.M,
)

# Word-bounded so "alone" does not fire on "alone time" and "increase" does not
# fire on "increases" (also listed) reading only its stem. Three buckets, the
# real defect this ticket names: two arms both labeled a gain, an ending
# labeled a preservation the body refuses to claim.
OUTCOME_WORD = re.compile(
    r"\b(gain|loss|preservation|preserve|increase|decrease|improve|improves|"
    r"prevent|prevents|reduce|reduces)\b",
    re.I,
)
_DIRECTION_OF = {
    "gain": "gain",
    "increase": "gain",
    "improve": "gain",
    "improves": "gain",
    "loss": "loss",
    "decrease": "loss",
    "reduce": "loss",
    "reduces": "loss",
    "preservation": "preservation",
    "preserve": "preservation",
    "prevent": "preservation",
    "prevents": "preservation",
}

# #476 F1. "Creatine did not prevent lean mass loss" reads `prevent` as
# preservation-direction on the bare word list, and the sentence actually
# says loss happened. Checked only in the text before the outcome word: a
# negation after it belongs to a different clause.
NEGATION_WORD = re.compile(r"\b(no|not|without|fails to)\b", re.I)
# #476 N1. A negated loss is "no loss", a preservation claim, not a gain
# claim; the first cut of this table sent it to gain, which let "there was
# no loss of lean mass" back a bare "Lean mass gain" label, the overclaim
# this ticket exists to stop, in this ticket's own domain. A negated gain
# is "no gain", the same neutral preservation claim, not a loss. Negating
# preservation still means the bad outcome happened, loss, which the F1
# fixture ("did not prevent lean mass loss") already confirmed correct.
_INVERT_DIRECTION = {"gain": "preservation", "loss": "preservation", "preservation": "loss"}


def label_direction(label: str) -> str | None:
    """Which outcome direction a label or a claim's text asserts, or `None`.

    First outcome word wins. A label naming two directions in one clause is
    rare, and untangling it is the caption's job, not this gate's.
    """
    text = label or ""
    match = OUTCOME_WORD.search(text)
    if not match:
        return None
    direction = _DIRECTION_OF[match.group(1).lower()]
    if NEGATION_WORD.search(text[: match.start()]):
        return _INVERT_DIRECTION.get(direction, direction)
    return direction


def node_labels(source: str, language: str = "mermaid") -> list[str]:
    """The node labels a diagram source names, for `figure_claims` to grade.

    Mirrors the Deep Agents port's `diagrams.inventory()` label extraction
    exactly, so the two ports read the same source the same way. Copied, not
    imported: two standalone folders. #476
    """
    source = source or ""
    if language == "plantuml":
        labels: list[str] = []
        for match in PUML_NODE.finditer(source):
            label = (match.group(1) or match.group(2) or "").strip()
            if label and label not in labels:
                labels.append(label)
        return labels
    first = source.strip().split("\n", 1)[0]
    diagram_type = first.split()[0] if first else "flowchart"
    labels = []
    if diagram_type.lower() == "sequencediagram":
        for match in MERMAID_PARTICIPANT.finditer(source):
            label = (match.group(2) or match.group(1)).strip()
            if label and label not in labels:
                labels.append(label)
    elif diagram_type.lower().startswith("statediagram"):
        for match in MERMAID_STATE_EDGE.finditer(source):
            for label in match.groups():
                if label != "[*]" and label not in labels:
                    labels.append(label)
    else:
        for match in MERMAID_NODE.finditer(source):
            text = next((group for group in match.groups()[1:] if group), "")
            label = (text or match.group(1)).strip().strip("[]").replace("\\n", " ")
            if label and label not in labels:
                labels.append(label)
    return labels


def figure_claims(labels: list[str], claims: list[str]) -> list[str]:
    """Node labels no claim in `claims` backs, direction by direction.

    A label whose direction (gain, loss, or preservation) no claim in this
    section asserts fails outright: the GitHub issue this ticket answers is
    a figure ending on "Lean mass preservation" for a section that refuses
    to make that claim. When exactly one claim backs a direction -- this
    section's sole support for it -- the label must say "reported"; stated
    plainly, it reads as a settled fact only one source made.
    """
    supports: dict[str, int] = {}
    for text in claims:
        direction = label_direction(text)
        if direction:
            supports[direction] = supports.get(direction, 0) + 1
    mismatches = []
    for label in labels:
        direction = label_direction(label)
        if direction is None:
            continue
        count = supports.get(direction, 0)
        if count == 0:
            mismatches.append(label)
        elif count == 1 and "reported" not in label.lower():
            mismatches.append(label)
    return mismatches


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
    claims: list[str] | None = None,
) -> Figure:
    """Draw one figure, simplifying on every judged miss.

    `claims` grounds the diagrammer in what this section's ledger entries
    actually assert, and every rendered attempt is graded against it by
    `figure_claims`, `claims` empty included: a section with no claims
    supports no outcome, so an outcome-shaped label still fails. #476 F3.

    `max_attempts` is the budget this call may spend, not a fresh three
    every time: `diagram()` passes what remains of a figure's lifetime cap
    after an earlier commissioning already spent some. #476 B2.
    """
    figure = Figure(name=name, section=section)
    out_dir = Path(out_dir)
    claims = list(claims or [])

    if not available():
        figure.misses = ["the renderer is not installed. Run `task setup`."]
        return figure

    feedback = ""
    claim_mismatch = False
    for attempt in range(1, max_attempts + 1):
        figure.attempts = attempt
        drawn = turns.diagram(name, concept, feedback, claims=claims)
        figure.caption = drawn.get("caption", "")
        figure.source = drawn.get("source", "")
        language = drawn.get("language", "mermaid")
        suffix = SUFFIX.get(language, ".mmd")

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
            mismatches = figure_claims(node_labels(figure.source, language), claims)
            if not mismatches:
                figure.path = str(png.relative_to(out_dir.parent))
                figure.misses = []
                return figure
            claim_mismatch = True
            figure.misses = [f"{label!r} does not match this section's claims" for label in mismatches]
            feedback = "; ".join(figure.misses)
            continue

        claim_mismatch = False
        figure.misses = list(verdict.get("misses", []))
        feedback = "; ".join(figure.misses)

    if claim_mismatch:
        # The budget for this call is spent on a claims mismatch every time.
        # No orphan image file, and an empty `path` keeps assembly from
        # placing a dangling reference. `dropped` tells `diagram()` this was
        # a claims exhaustion, not a render failure, so its durable count
        # stays spent even once the record's `path` is empty for another
        # reason too (no image backend, for one).
        png.unlink(missing_ok=True)
        figure.path = ""
        figure.dropped = True
        return figure

    # Out of attempts on rendering alone. Keep the last image and record what
    # it lost, so the check report says the figure is imperfect instead of
    # pretending it is not.
    figure.path = str(
        (out_dir / f"{name}{suffix}").with_name(f"{name}_imagen.png").relative_to(out_dir.parent)
    )
    return figure
