"""Chart render, sidecar, and the charted row. Copied, not imported."""

from __future__ import annotations

import json
from pathlib import Path

import charts
import evidence
import paper
import paper_check
import stages


class SilentRunner(paper.Runner):
    def ask(self, role, prompt):
        raise stages.GateFailed("no recorded chartist reply", ("no_fixture",))


class StubBackend:
    name = "stub"


def _paper(tmp_path: Path, notes=None) -> paper.Paper:
    run = paper.Paper(
        topic="exits",
        runner=SilentRunner(),
        backend=StubBackend(),  # type: ignore[arg-type]
        work_dir=tmp_path,
        quiet=True,
    )
    if notes is not None:
        run.say = notes.append
    return run


def test_render_writes_png_and_sidecar(tmp_path: Path):
    rows = [
        {"x": "done", "y": 1, "source": "paper.py"},
        {"x": "cost", "y": 2, "source": "paper.py"},
        {"x": "max turns", "y": 3, "source": "paper.py"},
    ]
    spec = charts.default_spec({"name": "three-exits", "data_needed": "exits", "section": "s1"}, rows)
    record = charts.render(spec, rows, tmp_path)
    assert (tmp_path / "three-exits.png").exists()
    assert (tmp_path / "three-exits.json").exists()
    assert [item["y"] for item in record["values"]] == [1, 2, 3]


def test_charted_fails_an_invented_number(tmp_path: Path):
    rows = [{"x": "a", "y": 99.5, "source": "nowhere"}]
    spec = charts.default_spec({"name": "invented"}, rows)
    record = charts.render(spec, rows, tmp_path)
    body = f"![{record['caption']}](charts/invented.png)\n"
    failures = charts.charted_failures(body, [record], "paper.py done cost 1 2 3")
    assert any("99.5" in item for item in failures)


def test_charted_passes_when_values_and_caption_are_grounded(tmp_path: Path):
    rows = [{"x": "done", "y": 1, "source": "paper.py"}]
    spec = charts.default_spec({"name": "one", "data_needed": "done first"}, rows)
    record = charts.render(spec, rows, tmp_path)
    body = f"done first [1]\n\n![{record['caption']}](charts/one.png)\n"
    assert charts.charted_failures(body, [record], "1 done first paper.py [1]") == []


def test_figure_assets_accepts_charts():
    body = "![exits](charts/three-exits.png)\n![loop](loop.png)\n"
    assert paper_check.non_publication_figures(body) == ["loop.png"]


def test_figure_assets_row_accepts_charts():
    body = (
        "# T\n\n## Abstract\n\nA loop without an exit spends until someone notices. [1]\n\n"
        "## Introduction\n\n"
        "The paper exits on done, then cost, then max turns [1].\n\n"
        "![Figure 1: done, then cost, then max turns](figures/exits_imagen.png)\n\n"
        "![the three exits](charts/three-exits.png)\n\n"
        "## Limitations\n\nThis paper measures two runtimes only. [1]\n\n"
        "## References\n\n1. https://docs.langchain.com/one\n"
    )
    score = paper_check.check(
        body,
        ["https://docs.langchain.com/one"],
        min_words=0,
        min_section_words=5,
    )
    assert "figure_assets" not in score.signature()


def test_charts_stage_skips_with_no_data(tmp_path: Path):
    notes = []
    run = _paper(tmp_path, notes)
    run.outline = {
        "title": "T",
        "sections": [
            {
                "id": "s1",
                "heading": "The problem",
                "figures": [
                    {
                        "name": "latency",
                        "kind": "chart",
                        "shows": "p95",
                        "data_needed": "latency table by version",
                    }
                ],
            }
        ],
    }
    run.plan = {"title": "T"}
    result = run.stage_charts()
    assert result.artifacts["skipped"] == 1
    assert result.artifacts["rendered"] == 0
    assert any("no data" in str(item) for item in notes)
    assert not any("not rendered in this phase" in str(item) for item in notes)


def test_charts_stage_renders_when_data_arrives(tmp_path: Path):
    run = _paper(tmp_path)
    run.outline = {
        "title": "T",
        "sections": [
            {
                "id": "s1",
                "heading": "The problem",
                "figures": [
                    {
                        "name": "three-exits",
                        "kind": "chart",
                        "shows": "the three exits",
                        "data_needed": "exit order",
                    }
                ],
            }
        ],
    }
    run.plan = {"title": "T"}
    data = tmp_path / "data"
    data.mkdir()
    (data / "three-exits.json").write_text(
        json.dumps(
            {
                "name": "three-exits",
                "columns": ["exit", "order"],
                "rows": [["done", 1], ["cost", 2], ["max turns", 3]],
                "source": "paper.py",
            }
        ),
        encoding="utf-8",
    )
    result = run.stage_charts()
    assert result.artifacts["rendered"] == 1
    assert result.artifacts["skipped"] == 0
    assert (tmp_path / "charts" / "three-exits.png").exists()


def test_assemble_embeds_a_rendered_chart(tmp_path: Path):
    charts_payload = [
        {
            "name": "three-exits",
            "path": str(tmp_path / "charts" / "three-exits.png"),
            "caption": "the three exits [1]",
            "section": "s1",
        }
    ]
    outline = {
        "sections": [
            {"id": "s1", "heading": "Introduction", "figures": []},
        ]
    }
    body = stages.assemble(
        {"title": "T"},
        outline,
        {"Introduction": "Three exits. [1]"},
        [],
        evidence.Ledger(tmp_path / "evidence"),
        charts=charts_payload,
    )
    assert "charts/three-exits.png" in body


def test_stage_order_runs_charts_after_diagram():
    assert stages.STAGE_ORDER.index("diagram") < stages.STAGE_ORDER.index("charts")
    assert stages.STAGE_ORDER.index("charts") < stages.STAGE_ORDER.index("assemble")
