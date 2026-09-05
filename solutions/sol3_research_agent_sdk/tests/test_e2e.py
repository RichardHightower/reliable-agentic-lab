"""The illustrated white-paper acceptance contract, without a live provider."""

from __future__ import annotations

import json
import shutil
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
        work / "outline.approved.json",
        {
            "outline": {
                "title": "Loop engineering",
                "audience": "engineers",
                "thesis": "A summary.",
                "word_target_total": 1800,
                "sections": [
                    {"id": "a", "heading": "A", "key_questions": ["q1", "q2"]},
                    {"id": "b", "heading": "B", "key_questions": ["q3", "q4"]},
                    {"id": "c", "heading": "C", "key_questions": ["q5", "q6"]},
                ],
            },
            "approved_by": "judge",
            "approved_at": "2026-09-03T00:00:00+00:00",
            "sha256": "abc",
        },
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


def test_the_live_lane_commissions_the_paper_profile(tmp_path):
    """The live lane uses `--profile paper` and does not clamp questions or
    claims. `--max-questions 3 --max-claims 6` on a 4000-word paper is why
    two live runs never stamped (#335). Fixture stays on demo size.
    """
    live = e2e._child_command("live", tmp_path / "live", "python3", 30.0)
    assert live[live.index("--profile") + 1] == "paper"
    assert "--max-questions" not in live
    assert "--max-claims" not in live
    fixture = e2e._child_command("fixture", tmp_path / "fix", "python3", 1.0)
    assert "--profile" not in fixture
    assert fixture[fixture.index("--max-questions") + 1] == "3"
    assert fixture[fixture.index("--max-claims") + 1] == "6"


def test_the_fixture_turns_can_use_a_scenario_specific_corpus(work, tmp_path):
    fixture = tmp_path / "scenario.json"
    fixture.write_text("{}")

    import loop  # noqa: PLC0415

    chosen = loop.pick_turns("fixture", work, None, None, fixture)

    assert chosen.backend.path == fixture


# -- the live preflight -----------------------------------------------------
#
# The first live attempt spent $1.07 against an empty pack because the clone
# had no sibling brain (#308). An empty pack is a thinner outline, not a
# failed corpus_fit row, but this lane still refuses to start without one.


def no_brain(monkeypatch, tmp_path):
    monkeypatch.setattr(e2e.corpus, "DEFAULT_BRAIN", tmp_path / "absent" / "knowledge")
    monkeypatch.setattr(e2e.corpus, "_git_toplevel", lambda start: tmp_path / "clone")
    monkeypatch.delenv("RESEARCH_BRAINS", raising=False)


def test_the_live_preflight_refuses_a_run_with_no_brain(monkeypatch, tmp_path):
    no_brain(monkeypatch, tmp_path)
    missing = e2e._corpus_check(None, allow_thin=False)
    assert len(missing) == 1
    assert "no corpus brain was found" in missing[0]
    assert "sibling of this folder" in missing[0]
    assert "ALLOW_THIN_CORPUS" in missing[0]


def test_allow_thin_corpus_lets_the_run_start_anyway(monkeypatch, tmp_path):
    no_brain(monkeypatch, tmp_path)
    assert e2e._corpus_check(None, allow_thin=True) == []


def test_a_named_brain_that_exists_satisfies_the_preflight(monkeypatch, tmp_path):
    no_brain(monkeypatch, tmp_path)
    brain = tmp_path / "brain"
    brain.mkdir()
    assert e2e._corpus_check(str(brain), allow_thin=False) == []


def test_the_fixture_lane_never_asks_for_a_brain(monkeypatch, tmp_path):
    """`task e2e-fixture` reads a recorded corpus. A missing brain is not its problem."""
    no_brain(monkeypatch, tmp_path)
    monkeypatch.setattr(e2e.diagrams, "available", lambda: True)
    monkeypatch.setattr(e2e.shutil, "which", lambda binary: "/usr/bin/imagen")
    assert e2e._preflight("fixture") == []


def test_the_run_log_survives_the_child_deleting_its_own_work_dir(tmp_path, monkeypatch):
    """The child runs with `--fresh`, which rmtrees the directory the log is in.

    A handle opened inside that directory keeps writing to an unlinked inode:
    every write succeeds and no file appears. That is #318, and it cost the
    first live run its whole log.
    """
    out = tmp_path / "work" / "live"
    out.mkdir(parents=True)
    (out / "stale.txt").write_text("from a previous run")

    def fake_stream(command, log_path):
        log_path.write_text("phase one\n")
        shutil.rmtree(out, ignore_errors=True)   # what --fresh does
        out.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("phase two\n")
        return 0

    monkeypatch.setattr(e2e, "_stream", fake_stream)
    monkeypatch.setattr(e2e, "_preflight", lambda mode, **kw: [])
    monkeypatch.setattr(e2e, "validate", lambda work_dir, **kw: {"passed": True, "failures": []})

    assert e2e.run("live", out, "python3", 1.0) == 0
    report = json.loads((out / "e2e-report.json").read_text())
    assert (out / "run.log").read_text() == "phase one\nphase two\n"
    assert report["run_log"] == str(out / "run.log")
    assert "phase two" in report["log_tail"]
    assert not (out / "stale.txt").exists(), "the fresh wipe must still happen"


def test_the_staging_log_does_not_survive_beside_the_work_dir(tmp_path, monkeypatch):
    """One log, in the documented place. A leftover sibling is litter."""
    out = tmp_path / "work" / "live"

    def fake_stream(command, log_path):
        log_path.write_text("x\n")
        return 0

    monkeypatch.setattr(e2e, "_stream", fake_stream)
    monkeypatch.setattr(e2e, "_preflight", lambda mode, **kw: [])
    monkeypatch.setattr(e2e, "validate", lambda work_dir, **kw: {"passed": True, "failures": []})

    e2e.run("live", out, "python3", 1.0)
    assert (out / "run.log").exists()
    assert list(out.parent.glob(".*.run.log")) == []
