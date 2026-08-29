"""The publication figure boundary: source in, judged *_imagen.png out."""

from __future__ import annotations

import json
from pathlib import Path

import diagrams
import pytest

SIMPLE = 'flowchart LR\n  A["Plan"] --> B["Search"]\n  B --> C{"Grounded?"}\n'
PUML = '@startuml\nparticipant "Maker" as M\nparticipant "Checker" as C\nM -> C: draft\n@enduml\n'


def result(code=0, *, stdout="", stderr=""):
    return type("Result", (), {"returncode": code, "stdout": stdout, "stderr": stderr})()


def big(nodes: int) -> str:
    rows = [f'  N{i}["Node {i}"] --> N{i + 1}["Node {i + 1}"]' for i in range(nodes)]
    return "flowchart TB\n" + "\n".join(rows)


def test_demo_assertions_hold():
    diagrams.demo()


def test_setup_pins_both_image_plugins_and_keeps_their_jobs_separate():
    taskfile = (diagrams.HERE / "Taskfile.yml").read_text(encoding="utf-8")
    assert "RENDERER_TAG: 'v0.2.0'" in taskfile
    assert "IMAGE_GEN_TAG: 'v2.1.0'" in taskfile
    assert ".cache/imagen-diagrams" in taskfile
    assert ".cache/image-gen" in taskfile

    module = (diagrams.HERE / "diagrams.py").read_text(encoding="utf-8")
    assert "run_image_gen" not in module
    assert "mmdc" not in module
    assert "-tsvg" not in module and "-tpng" not in module


def test_inventory_reads_labels_and_edges_without_rendering():
    inv = diagrams.inventory(SIMPLE, "mermaid")
    assert inv.labels == ["Plan", "Search", "Grounded?"]
    assert inv.edges == 2


def test_inventory_falls_back_to_a_bare_node_id():
    inv = diagrams.inventory('flowchart LR\n  A[] --> B["Search"]\n', "mermaid")
    assert inv.labels == ["A", "Search"]


def test_plantuml_inventory_is_local_too():
    inv = diagrams.inventory(PUML, "plantuml")
    assert inv.labels == ["Maker", "Checker"]
    assert inv.edges == 1


def test_complexity_gate_fires_before_the_plugin(monkeypatch, tmp_path):
    source = tmp_path / "wide.mmd"
    source.write_text(big(diagrams.MAX_NODES + 2))
    called = []
    monkeypatch.setattr(diagrams, "render_png", lambda *_args: called.append(True))
    with pytest.raises(diagrams.DiagramTooComplex) as exc:
        diagrams.render(source, tmp_path / "out")
    assert "Combine related nodes" in str(exc.value)
    assert not called


def test_alt_text_names_labels_but_not_source_syntax():
    inv = diagrams.Inventory(labels=["[Start]", "Maker\\nwrite scope"], edges=1)
    text = diagrams.alt_text(inv, "the loop")
    assert "Start" in text and "Maker write scope" in text
    assert "[" not in text and "\\n" not in text


def test_available_requires_both_plugin_scripts(monkeypatch, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(diagrams, "SCRIPTS", scripts)
    (scripts / "render.py").write_text("")
    assert not diagrams.available()
    (scripts / "judge.py").write_text("")
    assert diagrams.available()


def test_renderer_child_receives_the_imagen_06_key_alias(monkeypatch):
    seen = {}
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    def run(*_args, **kwargs):
        seen.update(kwargs["env"])
        return result()

    monkeypatch.setattr(diagrams.subprocess, "run", run)
    diagrams._run("render.py", [])
    assert seen["GOOGLE_API_KEY"] == "secret-value"


def test_local_themes_are_copied_into_the_disposable_clone(monkeypatch, tmp_path):
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    local.mkdir()
    remote.mkdir()
    (local / "paper.yaml").write_text("id: paper\n")
    monkeypatch.setattr(diagrams, "THEMES", local)
    monkeypatch.setattr(diagrams, "RENDERER_THEMES", remote)

    diagrams.ensure_theme()

    assert (remote / "paper.yaml").read_text() == "id: paper\n"


def test_render_invokes_only_imagen_diagrams_v020(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    calls = []
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(script, args):
        calls.append((script, args))
        out.mkdir(exist_ok=True)
        (out / "figure_imagen.png").write_bytes(b"x" * 5000)
        return result()

    monkeypatch.setattr(diagrams, "_run", run)
    png = diagrams.render_png(source, "loop safety", out)

    assert png == out / "figure_imagen.png"
    assert calls == [
        (
            "render.py",
            [
                "--source",
                str(source),
                "--topic",
                "loop safety",
                "--theme",
                diagrams.DEFAULT_THEME,
                "--density",
                "article",
                "--output-dir",
                str(out),
            ],
        )
    ]


def test_missing_plugin_fails_closed_and_leaves_a_prompt(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    monkeypatch.setattr(diagrams, "available", lambda: False)

    with pytest.raises(diagrams.ImageBackendUnavailable) as exc:
        diagrams.render_png(source, "loop safety", out)

    assert exc.value.exit_code == 2
    assert exc.value.prompt_file == out / "figure_imagen.prompt.txt"
    assert "Run `task setup`" in exc.value.prompt_file.read_text()
    assert not list(out.glob("*.svg"))
    assert not list(out.glob("figure.png"))


def test_plugin_no_backend_keeps_its_themed_prompt_and_exits_two(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    prompt = out / "figure_imagen.prompt.txt"
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(_script, _args):
        out.mkdir(exist_ok=True)
        prompt.write_text("plugin-built themed prompt")
        return result(diagrams.NO_BACKEND)

    monkeypatch.setattr(diagrams, "_run", run)
    with pytest.raises(diagrams.ImageBackendUnavailable) as exc:
        diagrams.render_png(source, "loop safety", out)
    assert exc.value.prompt_file == prompt
    assert prompt.read_text() == "plugin-built themed prompt"


def test_backend_auth_failure_also_fails_closed_with_the_prompt(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    prompt = out / "figure_imagen.prompt.txt"
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(_script, _args):
        out.mkdir(exist_ok=True)
        prompt.write_text("plugin-built themed prompt")
        return result(1, stderr="Google API key not configured")

    monkeypatch.setattr(diagrams, "_run", run)
    with pytest.raises(diagrams.ImageBackendUnavailable) as exc:
        diagrams.render_png(source, "loop safety", out)
    assert exc.value.exit_code == 2
    assert exc.value.prompt_file == prompt


def test_a_plain_png_cannot_masquerade_as_the_publication_figure():
    figure = diagrams.Figure(
        name="loop", source=Path("loop.mmd"), png=Path("loop.png"), polished=True
    )
    assert figure.best is None
    figure.png = Path("loop_imagen.png")
    assert figure.best == Path("loop_imagen.png")
    figure.polished = False
    assert figure.best is None


def test_judge_uses_the_plugin_and_names_its_sidecar(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    png = tmp_path / "figure_imagen.png"
    calls = []

    def run(script, args):
        calls.append((script, args))
        return result(stdout='{"pass": true, "misses": []}')

    monkeypatch.setattr(diagrams, "_run", run)
    assert diagrams.judge(source, png) == {"pass": True, "misses": []}
    assert calls == [
        (
            "judge.py",
            [
                "--source",
                str(source),
                "--png",
                str(png),
                "--sidecar",
                str(tmp_path / "figure_imagen.judge.json"),
            ],
        )
    ]


def test_judge_fails_when_it_returns_no_json(monkeypatch, tmp_path):
    monkeypatch.setattr(diagrams, "_run", lambda *_args: result(stdout="not json"))
    verdict = diagrams.judge(tmp_path / "f.mmd", tmp_path / "f_imagen.png")
    assert verdict["pass"] is False
    assert "no JSON" in verdict["misses"][0]


def test_render_accepts_only_a_plugin_judged_png(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"

    def render_png(_source, _topic, output, _theme):
        png = output / "figure_imagen.png"
        png.write_bytes(b"x" * 5000)
        return png

    monkeypatch.setattr(diagrams, "render_png", render_png)
    monkeypatch.setattr(diagrams, "judge", lambda *_args: {"pass": True, "misses": []})
    figure = diagrams.render(source, out, topic="loops")

    assert figure.best == out / "figure_imagen.png"
    assert figure.polished
    audit = json.loads((out / "figure.imagen.json").read_text())
    assert audit["renderer"] == diagrams.PIPELINE_VERSION
    assert audit["png"] == "figure_imagen.png"


def test_plugin_judge_rejection_never_publishes_the_png(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"

    def render_png(_source, _topic, output, _theme):
        png = output / "figure_imagen.png"
        png.write_bytes(b"x" * 5000)
        return png

    monkeypatch.setattr(diagrams, "render_png", render_png)
    monkeypatch.setattr(
        diagrams, "judge", lambda *_args: {"pass": False, "misses": ["lost Done"]}
    )
    figure = diagrams.render(source, out)
    assert figure.best is None
    assert figure.misses == ["lost Done"]


def test_no_polish_flag_cannot_restore_the_old_svg_path(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    calls = []

    def render_png(_source, _topic, output, _theme):
        calls.append(True)
        png = output / "figure_imagen.png"
        png.write_bytes(b"x" * 5000)
        return png

    monkeypatch.setattr(diagrams, "render_png", render_png)
    monkeypatch.setattr(diagrams, "judge", lambda *_args: {"pass": True, "misses": []})
    assert diagrams.render(source, out, polish=False).best.name == "figure_imagen.png"
    assert calls == [True]


def test_matching_accepted_hash_reuses_the_plugin_png(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    out = tmp_path / "out"
    calls = []

    def render_png(_source, _topic, output, _theme):
        calls.append(True)
        png = output / "figure_imagen.png"
        png.write_bytes(b"x" * 5000)
        return png

    monkeypatch.setattr(diagrams, "render_png", render_png)
    monkeypatch.setattr(diagrams, "judge", lambda *_args: {"pass": True, "misses": []})
    diagrams.render(source, out)
    reused = diagrams.render(source, out)
    assert calls == [True]
    assert reused.note == "unchanged, reused"


def test_main_returns_two_for_a_missing_backend(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text(SIMPLE)
    prompt = tmp_path / "out" / "figure_imagen.prompt.txt"

    def unavailable(*_args, **_kwargs):
        prompt.parent.mkdir()
        prompt.write_text("retry me")
        raise diagrams.ImageBackendUnavailable(prompt)

    monkeypatch.setattr(diagrams, "render", unavailable)
    assert diagrams.main(["--src", str(source), "--out", str(prompt.parent)]) == 2
