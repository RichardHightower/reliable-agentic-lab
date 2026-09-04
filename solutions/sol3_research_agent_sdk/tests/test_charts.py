"""Chart render, sidecar, and the charted row."""

from __future__ import annotations

import json
from pathlib import Path

import charts
import checks
import paper


def make_run(work, turns, **kwargs):
    kwargs.setdefault("brain", None)
    kwargs.setdefault("log", lambda *a: None)
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns,
        state=paper.State.load_or_new(work, "a topic"),
        **kwargs,
    )


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
    assert checks.non_publication_images(body) == ["loop.png"]


def test_figure_assets_row_accepts_charts_when_doctrine_is_on():
    body = (
        "# T\n\n## Control\n\n"
        "The paper exits on done, then cost, then max turns [1].\n\n"
        "![Figure 1: done, then cost, then max turns](exits_imagen.png)\n\n"
        "![the three exits](charts/three-exits.png)\n\n"
        "Figure 1 shows done, then cost, then max turns."
    )
    score = checks.check(
        body,
        ["https://docs.langchain.com/oss/python/langchain/overview"],
        enforce_source_policy=True,
        enforce_loop_doctrine=True,
    )
    assert "figure_assets" not in score.signature()


def test_assemble_embeds_a_rendered_chart(work, turns):
    class Charted(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            drafted = super().outline(topic, prior_art, budget, note, brief)
            drafted["sections"][0]["figures"] = [
                {
                    "name": "three-exits",
                    "kind": "chart",
                    "shows": "the three exits",
                    "data_needed": "exit order",
                }
            ]
            return drafted

    run = make_run(work, Charted(root=work))
    paper.prior_art(run)
    paper.do_outline(run)
    data = run.file("data")
    data.mkdir(parents=True, exist_ok=True)
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
    paper.do_charts(run)
    section_dir = run.file("sections")
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "s1.md").write_text("## The problem\n\nA thing is true [1].\n", encoding="utf-8")
    run.write_json(
        "claims.json",
        {
            "claims": [
                {
                    "text": "A thing is true.",
                    "source_url": "https://example.invalid/doc",
                    "quote": "a thing is true",
                    "number": 1,
                    "status": "verified",
                    "section": "s1",
                }
            ]
        },
    )
    paper.assemble(run)
    body = run.file("paper.md").read_text(encoding="utf-8")
    assert "charts/three-exits.png" in body


def test_linear_runs_charts_after_diagram():
    names = [name for _n, name, _out, _fn in paper.LINEAR]
    assert names.index("diagram") < names.index("charts")
