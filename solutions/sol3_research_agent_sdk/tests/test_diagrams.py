"""The figure loop. Bounded, and honest about what it lost."""

from __future__ import annotations

import diagrams
import pytest


class Drawer:
    def __init__(self):
        self.calls = []

    def diagram(self, name, concept, feedback=""):
        self.calls.append(feedback)
        return {"language": "mermaid", "source": f"flowchart LR\n  A[{name}]", "caption": "Cap."}


@pytest.fixture
def renderer(monkeypatch, tmp_path):
    """A renderer that always draws. The judge is what the test varies."""
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def render(source, topic, out_dir, theme=diagrams.DEFAULT_THEME):
        png = out_dir / f"{source.stem}_imagen.png"
        png.write_bytes(b"x" * 64)
        return png

    monkeypatch.setattr(diagrams, "render", render)
    return monkeypatch


def test_a_clean_render_stops_after_one_attempt(renderer, tmp_path):
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer()
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert figure.attempts == 1
    assert figure.rendered and figure.misses == []
    assert figure.path == "diagrams/f_imagen.png"


def test_a_miss_is_handed_back_as_feedback(renderer, tmp_path):
    verdicts = iter([{"pass": False, "misses": ["lost Verify"]}, {"pass": True, "misses": []}])
    renderer.setattr(diagrams, "judge", lambda source, png: next(verdicts))
    drawer = Drawer()
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert figure.attempts == 2
    assert drawer.calls == ["", "lost Verify"], "the second attempt is told what was lost"
    assert figure.misses == []


def test_it_stops_after_three_attempts_and_records_the_miss(renderer, tmp_path):
    """A render loop with no ceiling redraws the same overcrowded graph forever."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": False, "misses": ["crowded"]})
    drawer = Drawer()
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert figure.attempts == diagrams.MAX_ATTEMPTS
    assert figure.misses == ["crowded"]
    assert figure.rendered, "the last image is kept, imperfect and labelled"


def test_no_image_backend_stops_immediately(renderer, tmp_path):
    """Redrawing does not add a backend, so it does not ask again."""
    renderer.setattr(diagrams, "render", lambda *a, **k: None)
    drawer = Drawer()
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert figure.attempts == 1
    assert not figure.rendered
    assert figure.misses == ["the renderer produced no image"]


def test_a_missing_renderer_never_calls_the_model(monkeypatch, tmp_path):
    monkeypatch.setattr(diagrams, "available", lambda: False)
    drawer = Drawer()
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert drawer.calls == []
    assert not figure.rendered
    assert "task setup" in figure.misses[0]


def test_render_invokes_the_plugin_with_article_density(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text("flowchart LR\n  A[{Decision?}]")
    out = tmp_path / "out"
    calls = []
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(script, args):
        calls.append((script, args))
        (out / "figure_imagen.png").parent.mkdir(parents=True, exist_ok=True)
        (out / "figure_imagen.png").write_bytes(b"x" * 64)
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(diagrams, "_run", run)

    assert diagrams.render(source, "loop safety", out) == out / "figure_imagen.png"
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


def test_plugin_no_backend_keeps_its_prompt_and_fails_closed(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text("flowchart LR\n  A[{Decision?}]")
    out = tmp_path / "out"
    prompt = out / "figure_imagen.prompt.txt"
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(script, args):
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text("the plugin-built themed prompt")
        return type("Result", (), {"returncode": diagrams.NO_BACKEND})()

    monkeypatch.setattr(diagrams, "_run", run)

    with pytest.raises(diagrams.ImageBackendUnavailable) as exc:
        diagrams.render(source, "loop safety", out)

    assert prompt.name == "figure_imagen.prompt.txt"
    assert exc.value.exit_code == 2
    assert exc.value.prompt_file == prompt
    assert prompt.read_text() == "the plugin-built themed prompt"


def test_judge_persists_the_plugin_fidelity_sidecar(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    png = tmp_path / "figure_imagen.png"
    calls = []

    def run(script, args):
        calls.append((script, args))
        return type("Result", (), {"stdout": '{"pass": true, "misses": []}'})()

    monkeypatch.setattr(diagrams, "_run", run)
    assert diagrams.judge(source, png) == {"pass": True, "misses": []}
    assert calls == [
        (
            "judge.py",
            ["--source", str(source), "--png", str(png), "--sidecar", str(tmp_path / "figure_imagen.judge.json")],
        )
    ]


def test_the_source_is_written_next_to_the_image(renderer, tmp_path):
    """The source is an intermediate form, kept for a reader, not for the paper."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    out = tmp_path / "diagrams"
    diagrams.draw(Drawer(), name="f", concept="c", section="s", topic="t", out_dir=out)
    assert (out / "f.mmd").read_text().startswith("flowchart LR")
