"""The figure loop. Bounded, and honest about what it lost."""

from __future__ import annotations

import pathlib

import diagrams
import pytest


class Drawer:
    def __init__(self, source=None):
        self.calls = []
        self.claims_seen = []
        self.source = source

    def diagram(self, name, concept, feedback="", claims=None):
        self.calls.append(feedback)
        self.claims_seen.append(list(claims or []))
        return {
            "language": "mermaid",
            "source": self.source or f"flowchart LR\n  A[{name}]",
            "caption": "Cap.",
        }


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


# -- #476: a label must agree with the section's claims -----------------------


def test_label_direction_reads_the_three_outcome_buckets():
    assert diagrams.label_direction("Reported lean mass gain") == "gain"
    assert diagrams.label_direction("True fat-free loss") == "loss"
    assert diagrams.label_direction("Lean mass preservation") == "preservation"
    assert diagrams.label_direction("Corrected comparison") is None
    assert diagrams.label_direction("A reported strength increase") == "gain"


def test_label_direction_inverts_on_negation():
    """#476 F1. "Did not prevent lean mass loss" is a loss claim, not a
    preservation claim; the bare word list reads `prevent` the wrong way.

    #476 N1: a negated gain or a negated loss is a preservation claim (a
    neutral "nothing changed" reading), not each other's opposite. The
    first cut of `_INVERT_DIRECTION` sent a negated loss to gain, so "no
    loss of lean mass" read as a gain claim.
    """
    assert diagrams.label_direction("Creatine did not prevent lean mass loss") == "loss"
    assert diagrams.label_direction("The trial found no strength gain") == "preservation"
    assert diagrams.label_direction("Fails to increase strength") == "preservation"
    assert diagrams.label_direction("Without a fat-free mass gain") == "preservation"
    assert diagrams.label_direction("There was no loss of lean mass") == "preservation"
    # A negation after the outcome word belongs to a different clause.
    assert diagrams.label_direction("Strength gain, not measured directly") == "gain"


def test_node_labels_matches_the_deep_agents_ports_inventory_on_arrows_and_ids():
    """A label after an arrow (`Start --> Gain[Fat-free mass]`) must not glue
    to the preceding `-->` or read as the node id `Gain`. Same fixture as the
    Deep Agents port's `inventory()` test; the two parsers must agree. #476 B1
    """
    source = "flowchart LR\n  Start --> Gain[Fat-free mass]\n  Gain --> End[End]\n"
    assert diagrams.node_labels(source) == ["Fat-free mass", "End"]


def test_a_hedged_loss_does_not_back_a_gain_label():
    """#476 N1: a negated loss is a preservation claim, not a gain claim.
    `_INVERT_DIRECTION` used to send it the other way, so "there was no
    loss of lean mass" backed a bare "Lean mass gain" label, the overclaim
    this ticket exists to stop. Two claims, so a reverted map (which counts
    both as "gain") clears the single-source "reported" hedge and the
    mismatch would go unnoticed with only one.
    """
    labels = ["Lean mass gain"]
    claims = [
        "There was no loss of lean mass in the treatment arm.",
        "There was no loss of lean mass in the control arm either.",
    ]
    assert diagrams.figure_claims(labels, claims) == ["Lean mass gain"]


def test_a_label_that_contradicts_the_section_claims_fails():
    labels = ["Lean mass preservation", "Search"]
    claims = ["The trial could not distinguish water retention from tissue."]
    assert diagrams.figure_claims(labels, claims) == ["Lean mass preservation"]


def test_a_single_source_label_needs_the_word_reported():
    labels = ["True fat-free gain", "Reported fat-free gain"]
    claims = ["One small trial reported a fat-free mass gain."]
    assert diagrams.figure_claims(labels, claims) == ["True fat-free gain"]


def test_two_claims_backing_a_direction_need_no_hedge():
    labels = ["Lean mass gain"]
    claims = ["One trial found a lean mass gain.", "A second trial also found a gain."]
    assert diagrams.figure_claims(labels, claims) == []


def test_a_third_mismatch_drops_the_figure_and_the_image(renderer, tmp_path):
    """Three attempts, a mismatch every time: no image, no dangling reference."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer(source='flowchart LR\n  A["Lean mass preservation"]')
    out_dir = tmp_path / "diagrams"
    figure = diagrams.draw(
        drawer,
        name="f",
        concept="c",
        section="s",
        topic="t",
        out_dir=out_dir,
        claims=["The trial could not distinguish water retention from tissue."],
    )
    assert figure.attempts == diagrams.MAX_ATTEMPTS
    assert not figure.rendered, "a claims mismatch is dropped, not kept imperfect"
    assert figure.path == ""
    assert not (out_dir / "f_imagen.png").exists(), "no orphan image file is left behind"


def test_a_changed_claim_recommissions_a_previously_dropped_label(renderer, tmp_path):
    """The same label passes once two independent claims back its direction."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer(source='flowchart LR\n  A["Lean mass preservation"]')
    figure = diagrams.draw(
        drawer,
        name="f",
        concept="c",
        section="s",
        topic="t",
        out_dir=tmp_path / "diagrams",
        claims=[
            "One trial found a lean mass preservation across both arms.",
            "A second trial also found a lean mass preservation.",
        ],
    )
    assert figure.rendered
    assert figure.path == "diagrams/f_imagen.png"


def test_an_outcome_label_with_no_supporting_claims_fails(renderer, tmp_path):
    """#476 F3: absence of claims is not support. A caller with nothing
    bound yet does not get a pass, it gets the same drop a real mismatch
    does."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer(source='flowchart LR\n  A["Lean mass preservation"]')
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert not figure.rendered
    assert figure.dropped
    assert figure.attempts == diagrams.MAX_ATTEMPTS


def test_a_structural_label_with_no_outcome_word_needs_no_claims(renderer, tmp_path):
    """Absence of claims only sinks a label that asserts an outcome. A plain
    process label (`Plan`, `Search`, ...) has no direction to grade."""
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer(source='flowchart LR\n  A["Plan"] --> B["Search"]')
    figure = diagrams.draw(
        drawer, name="f", concept="c", section="s", topic="t", out_dir=tmp_path / "diagrams"
    )
    assert figure.rendered


def test_the_diagrammer_receives_the_sections_claims(renderer, tmp_path):
    renderer.setattr(diagrams, "judge", lambda source, png: {"pass": True, "misses": []})
    drawer = Drawer()
    diagrams.draw(
        drawer,
        name="f",
        concept="c",
        section="s",
        topic="t",
        out_dir=tmp_path / "diagrams",
        claims=["Creatine increased fat-free mass."],
    )
    assert drawer.claims_seen == [["Creatine increased fat-free mass."]]


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


def test_renderer_child_receives_the_imagen_06_key_alias(monkeypatch):
    seen = {}
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    def run(*_args, **kwargs):
        seen.update(kwargs["env"])
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(diagrams.subprocess, "run", run)
    diagrams._run("render.py", [])
    assert seen["GOOGLE_API_KEY"] == "secret-value"


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


def test_backend_auth_failure_also_fails_closed_with_the_prompt(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text("flowchart LR\n  A[Plan]")
    out = tmp_path / "out"
    prompt = out / "figure_imagen.prompt.txt"
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(_script, _args):
        out.mkdir(exist_ok=True)
        prompt.write_text("the plugin-built themed prompt")
        return type("Result", (), {"returncode": 1})()

    monkeypatch.setattr(diagrams, "_run", run)
    with pytest.raises(diagrams.ImageBackendUnavailable) as exc:
        diagrams.render(source, "loop safety", out)
    assert exc.value.exit_code == 2
    assert exc.value.prompt_file == prompt


def test_runtime_failure_falls_through_in_order_and_keeps_attempts(monkeypatch, tmp_path):
    source = tmp_path / "figure.mmd"
    source.write_text("flowchart LR\n  A[Plan] --> B[Check]")
    out = tmp_path / "out"
    calls = []
    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)

    def run(script, args):
        backend = args[args.index("--backend") + 1] if "--backend" in args else "imagen"
        calls.append(backend)
        out.mkdir(parents=True, exist_ok=True)
        (out / "figure_imagen.prompt.txt").write_text(f"prompt for {backend}")
        (out / "figure_imagen.json").write_text(json.dumps({"backend": backend}))
        if backend == "grok":
            (out / "figure_imagen.png").write_bytes(b"x" * 64)
            return type("Result", (), {"returncode": 0})()
        return type("Result", (), {"returncode": 1})()

    import json  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "_run", run)

    assert diagrams.render(source, "loop safety", out) == out / "figure_imagen.png"
    assert calls == ["imagen", "grok"]
    assert (out / "figure_imagen.imagen.prompt.txt").read_text() == "prompt for imagen"
    assert (out / "figure_imagen.imagen.json").is_file()


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


# -- the image backend never sees a single-brace node (#367) -------------------


def test_a_decision_node_is_rewritten_for_the_image_backend(tmp_path):
    """`GATE{Gate}` became `{Gate}` in the prompt and the imagen CLI read it as
    an unfilled template variable. The first live run to reach the diagram
    phase died on it, every backend the same way.
    """
    import diagrams  # noqa: PLC0415

    src = tmp_path / "flow.mmd"
    src.write_text(
        "flowchart TD\n    A[Start] --> GATE{Gate}\n    GATE --> B((Done))\n"
        "    B --> C{{Hex}}\n",
        encoding="utf-8",
    )
    staged = diagrams.for_image_backend(src)
    assert staged != src
    assert staged.name == src.name, "the stem must not change"
    text = staged.read_text()
    assert "GATE[Gate]" in text
    assert "{Gate}" not in text
    assert "C{{Hex}}" in text, "a hexagon is not a decision node"
    assert "B((Done))" in text
    assert src.read_text().count("{Gate}") == 1, "the original is not touched"


def test_a_source_with_no_decision_node_is_handed_over_as_is(tmp_path):
    import diagrams  # noqa: PLC0415

    src = tmp_path / "flow.mmd"
    src.write_text("flowchart TD\n    A[Start] --> B[End]\n", encoding="utf-8")
    assert diagrams.for_image_backend(src) == src


def test_render_hands_the_backend_the_sanitized_source(tmp_path, monkeypatch):
    """The call site, not the helper. A helper test stays green if `render`
    keeps passing the raw path.
    """
    import subprocess  # noqa: PLC0415

    import diagrams  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "ensure_theme", lambda: None)
    seen = []

    def fake_run(script, args):
        seen.append(list(args))
        return subprocess.CompletedProcess(args, returncode=diagrams.NO_BACKEND)

    monkeypatch.setattr(diagrams, "_run", fake_run)
    src = tmp_path / "flow.mmd"
    src.write_text("flowchart TD\n    A --> GATE{Gate}\n", encoding="utf-8")
    diagrams.render(src, "a topic", tmp_path / "out")
    assert seen, "render never called the renderer"
    handed = pathlib.Path(seen[0][seen[0].index("--source") + 1])
    assert "{Gate}" not in handed.read_text(), handed
    assert handed.name == src.name
