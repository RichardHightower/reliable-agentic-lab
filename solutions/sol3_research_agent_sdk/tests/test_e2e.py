"""The illustrated white-paper acceptance contract, without a live provider."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import e2e


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_png(path: Path, width: int = 1600, height: int = 900) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The validator reads PNG signature and IHDR dimensions, then requires a
    # nontrivial file. Image fidelity itself belongs to the real renderer's
    # judge, not this isolated validation test.
    header = e2e.PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    path.write_bytes(header + b"x" * 4096)


def complete_artifact(work: Path) -> None:
    figures = []
    embedded = []
    for name in e2e.REQUIRED_FIGURES:
        relative = f"diagrams/{name}_imagen.png"
        caption = f"The {name} figure explains the E2E scenario."
        figures.append({"name": name, "path": relative, "misses": [], "caption": caption})
        embedded.append(f"![Figure: {name}]({relative})")
        embedded.append(caption)
        image = work / relative
        write_png(image)
        (work / "diagrams" / f"{name}.mmd").write_text("flowchart LR\nA --> B\n")
        write_json(
            image.with_suffix(".json"),
            {
                "backend": "imagen",
                "policy": "imagen-cli-vars",
                "density": "article",
                "theme": "arctic-fox",
            },
        )
        write_json(image.with_suffix(".judge.json"), {"pass": True, "misses": []})

    (work / "paper.md").write_text(
        "# Loop engineering\n\n## Abstract\n\nA summary.\n\n"
        + "\n\n".join(embedded)
        + "\n\n## References\n\n1. https://one.example\n",
        encoding="utf-8",
    )
    write_json(
        work / "plan.json",
        {
            "sections": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "questions": [{"id": "q1"}, {"id": "q2"}, {"id": "q3"}],
        },
    )
    write_json(
        work / "sources.json",
        {
            "sources": [
                {"url": "https://one.example/doc"},
                {"url": "https://two.example/doc"},
                {"url": "https://three.example/doc"},
            ]
        },
    )
    write_json(
        work / "claims.json",
        {"claims": [{"status": "verified"}, {"status": "verified"}, {"status": "unverified"}]},
    )
    write_json(work / "diagrams.json", {"figures": figures})
    write_json(work / "check.json", {"passed": True})
    write_json(work / "review.json", {"done": True})
    write_json(
        work / ".harness" / "state.json",
        {"total_usd": 0.4, "phases": {"knowledge": {"valid": True}}},
    )


def test_the_complete_illustrated_artifact_passes(tmp_path):
    work = tmp_path / "paper"
    complete_artifact(work)

    report = e2e.validate(work, max_usd=1.0)

    assert report["passed"], report["failures"]
    assert report["figures"] == 2
    assert len(report["source_urls"]) == 3


def test_a_figure_with_a_fidelity_miss_is_not_publication_ready(tmp_path):
    work = tmp_path / "paper"
    complete_artifact(work)
    diagrams = json.loads((work / "diagrams.json").read_text())
    diagrams["figures"][0]["misses"] = ["lost the escalation exit"]
    write_json(work / "diagrams.json", diagrams)

    report = e2e.validate(work)

    assert not report["passed"]
    assert any("fidelity misses" in failure for failure in report["failures"])


def test_a_figure_without_the_plugin_judge_record_is_not_publication_ready(tmp_path):
    work = tmp_path / "paper"
    complete_artifact(work)
    (work / "diagrams" / "control-loop_imagen.judge.json").unlink()

    report = e2e.validate(work)

    assert not report["passed"]
    assert any("judge sidecar" in failure for failure in report["failures"])


def test_a_figure_with_the_wrong_theme_is_not_publication_ready(tmp_path):
    work = tmp_path / "paper"
    complete_artifact(work)
    sidecar = work / "diagrams" / "control-loop_imagen.json"
    rendered = json.loads(sidecar.read_text())
    rendered["theme"] = "claude-clay"
    write_json(sidecar, rendered)

    report = e2e.validate(work)

    assert not report["passed"]
    assert any("publication theme" in failure for failure in report["failures"])


def test_the_fixture_turns_can_use_a_scenario_specific_corpus(work, tmp_path):
    fixture = tmp_path / "scenario.json"
    fixture.write_text("{}")

    import loop  # noqa: PLC0415

    chosen = loop.pick_turns("fixture", work, None, None, fixture)

    assert chosen.backend.path == fixture
