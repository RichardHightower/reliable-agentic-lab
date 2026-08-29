"""The figure pipeline. Every step fails closed to the step before it."""

from __future__ import annotations

import json
from pathlib import Path

import diagrams
import pytest

SIMPLE = 'flowchart LR\n  A["Plan"] --> B["Search"]\n  B --> C{"Grounded?"}\n'
PUML = '@startuml\nparticipant "Maker" as M\nparticipant "Checker" as C\nM -> C: draft\n@enduml\n'


def big(nodes: int) -> str:
    rows = [f'  N{i}["Node {i}"] --> N{i + 1}["Node {i + 1}"]' for i in range(nodes)]
    return "flowchart TB\n" + "\n".join(rows)


def test_demo_assertions_hold():
    diagrams.demo()


def test_inventory_reads_labels_not_ids():
    inv = diagrams.inventory(SIMPLE, "mermaid")
    assert inv.labels == ["Plan", "Search", "Grounded?"]
    assert inv.edges == 2


def test_inventory_falls_back_to_the_id_when_a_node_has_no_label():
    """A bare id is what a reader would see, so the judge must check for it."""
    inv = diagrams.inventory('flowchart LR\n  A[] --> B["Search"]\n', "mermaid")
    assert "A" in inv.labels


def test_plantuml_inventory():
    inv = diagrams.inventory(PUML, "plantuml")
    assert inv.labels == ["Maker", "Checker"]
    assert inv.edges == 1


def test_complexity_gate_fires_over_the_limit():
    inv = diagrams.inventory(big(diagrams.MAX_NODES + 2), "mermaid")
    assert inv.too_complex
    assert not diagrams.inventory(SIMPLE, "mermaid").too_complex


def test_the_simplify_instruction_names_the_surplus_nodes():
    """ "Simplify this" produces shorter labels. Naming them produces a combine."""
    instruction = diagrams.simplify_instruction(diagrams.inventory(big(20), "mermaid"))
    assert "Combine related nodes" in instruction
    assert "Node 12" in instruction


def test_render_refuses_a_too_complex_source(tmp_path):
    src = tmp_path / "wide.mmd"
    src.write_text(big(30))
    with pytest.raises(diagrams.DiagramTooComplex):
        diagrams.render(src, tmp_path / "out", polish=False)


def test_braces_are_doubled_for_the_imagen_cli():
    """The CLI reads {x} as a template variable. A {Decision?} node crashes it."""
    assert diagrams.escape_braces("a {x} b") == "a {{x}} b"
    prompt = diagrams.build_prompt(
        SIMPLE, diagrams.inventory(SIMPLE, "mermaid"), diagrams.load_theme(), "loops"
    )
    assert "{{" in prompt and "}}" in prompt
    assert "{Decision?}" not in prompt


def test_imagen_argv_matches_the_installed_cli_help(monkeypatch, tmp_path):
    """Imagen accepts a prompt argument, -o, and --aspect-ratio.

    Do not cargo-cult the imagen-diagrams v0.1.0 adapter here. Its
    --prompt-file, --aspect, and --output flags are not accepted by the CLI
    installed for this course.
    """
    target = tmp_path / "figure.png"
    seen = []

    def run(argv, **_kwargs):
        seen.append(argv)
        target.write_bytes(b"png")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(diagrams.subprocess, "run", run)

    assert diagrams.run_imagen("draw {{Decision?}}", target, "4:3") == target
    assert seen == [
        ["imagen", "generate", "draw {{Decision?}}", "-o", str(target), "--aspect-ratio", "4:3"]
    ]


def test_the_closer_is_the_last_thing_in_the_prompt():
    """Final tokens weigh most, and the failure this guards is a picture of code."""
    prompt = diagrams.build_prompt(
        SIMPLE, diagrams.inventory(SIMPLE, "mermaid"), diagrams.load_theme(), "loops"
    )
    assert prompt.rstrip().endswith("not Mermaid or PlantUML code.")


def test_the_prompt_carries_the_theme_palette():
    theme = diagrams.load_theme("spillwave-light")
    assert theme["palette"]["background"].startswith("#")
    prompt = diagrams.build_prompt(SIMPLE, diagrams.inventory(SIMPLE, "mermaid"), theme, "loops")
    assert theme["palette"]["background"] in prompt
    assert "mermaid or plantuml source syntax" in prompt


def test_mermaid_theme_keeps_html_labels_for_the_browser_rendered_print_png():
    config = json.loads(diagrams.MERMAID_CONFIG.read_text())
    assert config["flowchart"]["htmlLabels"] is True


def test_mermaid_keeps_chromium_sandboxed_unless_the_environment_opted_out(tmp_path, monkeypatch):
    monkeypatch.delenv("SOL3_MERMAID_NO_SANDBOX", raising=False)
    assert diagrams._puppeteer_config(str(tmp_path)) is None

    monkeypatch.setenv("SOL3_MERMAID_NO_SANDBOX", "1")
    config = diagrams._puppeteer_config(str(tmp_path))
    assert config is not None
    assert json.loads(config.read_text())["args"] == ["--no-sandbox", "--disable-setuid-sandbox"]


def test_a_missing_theme_does_not_raise():
    assert diagrams.load_theme("no-such-theme")["palette"] == {}


def test_plantuml_uses_the_selected_white_paper_palette():
    args = diagrams.plantuml_style_args("spillwave-light")
    assert "-SbackgroundColor=#eef2f7" in args
    assert "-SsequenceArrowColor=#1a365d" in args
    assert "-SdefaultFontSize=18" in args


class FakePng:
    def __init__(self, size=100_000, there=True):
        self._size = size
        self._there = there

    def exists(self):
        return self._there

    def stat(self):
        return type("S", (), {"st_size": self._size})()


def test_the_judge_catches_a_missing_label():
    inv = diagrams.inventory(SIMPLE, "mermaid")
    verdict = diagrams.judge_png(FakePng(), inv, "boxes labelled Plan and Search")
    assert not verdict.passed
    assert any("Grounded?" in miss for miss in verdict.misses)


def test_the_judge_catches_visible_source_syntax():
    inv = diagrams.inventory(SIMPLE, "mermaid")
    verdict = diagrams.judge_png(FakePng(), inv, "flowchart LR Plan Search Grounded?")
    assert any("source syntax" in miss for miss in verdict.misses)


def test_the_judge_reports_a_missing_image():
    verdict = diagrams.judge_png(FakePng(there=False), diagrams.inventory(SIMPLE, "mermaid"))
    assert not verdict.passed


def test_alt_text_names_the_labels():
    alt = diagrams.alt_text(diagrams.inventory(SIMPLE, "mermaid"), "the loop")
    assert "Plan" in alt and "2 relationships" in alt


def test_a_figure_ships_its_svg_until_a_png_is_judged_good():
    figure = diagrams.Figure(name="x", source=Path("x.mmd"), svg=Path("x.svg"))
    assert figure.best == Path("x.svg")
    figure.png = Path("x.png")
    assert figure.best == Path("x.svg"), "an unjudged png does not ship"
    figure.rasterized = True
    assert figure.best == Path("x.png"), "the deterministic print PNG is safe to ship"
    figure.rasterized = False
    figure.polished = True
    assert figure.best == Path("x.png")


def test_missing_imagen_keeps_the_deterministic_figure(tmp_path, monkeypatch):
    """No CLI and no key is a fact about the laptop, not a failed run."""
    monkeypatch.setattr(diagrams, "imagen_available", lambda: False)
    monkeypatch.setattr(diagrams, "PLUGIN_RENDER", tmp_path / "absent.py")
    src = tmp_path / "d.mmd"
    src.write_text(SIMPLE)
    monkeypatch.setattr(diagrams, "render_svg", lambda s, o, **_: _stub_svg(o, s))
    monkeypatch.setattr(diagrams, "render_mermaid_png", lambda s, o, **_: _stub_png(o, s))

    figure = diagrams.render(src, tmp_path / "out", polish=True)
    assert figure.polished is False
    assert figure.svg.exists()
    assert figure.rasterized is True
    assert figure.best == figure.png
    assert "embedded print PNG" in figure.note


def _stub_svg(out_dir: Path, src: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{src.stem}.svg"
    target.write_text("<svg/>")
    return target


def _stub_png(out_dir: Path, src: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{src.stem}.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n")
    return target


def test_a_matching_hash_skips_the_render(tmp_path, monkeypatch):
    """This is what makes a resumed run cheap. A rerender costs an image call."""
    calls = []
    monkeypatch.setattr(diagrams, "imagen_available", lambda: False)
    monkeypatch.setattr(diagrams, "PLUGIN_RENDER", tmp_path / "absent.py")
    monkeypatch.setattr(
        diagrams, "render_svg", lambda s, o, **_: (calls.append(s), _stub_svg(o, s))[1]
    )
    monkeypatch.setattr(diagrams, "render_mermaid_png", lambda s, o, **_: _stub_png(o, s))

    src = tmp_path / "d.mmd"
    src.write_text(SIMPLE)
    out = tmp_path / "out"
    diagrams.render(src, out, polish=True)
    assert len(calls) == 1

    figure = diagrams.render(src, out, polish=True)
    assert len(calls) == 1, "the second run must not rerender"
    assert figure.note == "unchanged, reused"

    src.write_text(SIMPLE + '  C --> D["Write"]\n')
    diagrams.render(src, out, polish=True)
    assert len(calls) == 2, "a changed source must rerender"


def test_the_sidecar_records_what_happened(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "imagen_available", lambda: False)
    monkeypatch.setattr(diagrams, "PLUGIN_RENDER", tmp_path / "absent.py")
    monkeypatch.setattr(diagrams, "render_svg", lambda s, o, **_: _stub_svg(o, s))
    monkeypatch.setattr(diagrams, "render_mermaid_png", lambda s, o, **_: _stub_png(o, s))
    src = tmp_path / "d.mmd"
    src.write_text(SIMPLE)
    diagrams.render(src, tmp_path / "out", polish=True, topic="loops")

    sidecar = json.loads((tmp_path / "out" / "d.imagen.json").read_text())
    assert sidecar["polished"] is False
    assert sidecar["rasterized"] is True
    assert sidecar["source_hash"]
    assert "Plan" in sidecar["alt"]
