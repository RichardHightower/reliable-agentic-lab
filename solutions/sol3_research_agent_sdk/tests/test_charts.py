"""Chart render, sidecar, and the charted row."""

from __future__ import annotations

import json
from pathlib import Path

import charts
import pytest
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


def test_assemble_embeds_a_rendered_diagram(work, turns):
    """Run 15 rendered loop-and-harness-architecture_imagen.png (597 KB)
    and never linked it. Charts had `_charts_for`. Diagrams did not (#370).
    """
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.do_outline(run)
    dest = run.file("diagrams")
    dest.mkdir(parents=True, exist_ok=True)
    png = dest / "loop-and-harness-architecture_imagen.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
    run.write_json(
        "diagrams.json",
        {
            "figures": [
                {
                    "name": "loop-and-harness-architecture",
                    "section": "s1",
                    "caption": "Loop and harness architecture",
                    "path": f"diagrams/{png.name}",
                }
            ]
        },
    )
    section_dir = run.file("sections")
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "s1.md").write_text("A thing is true [1].\n", encoding="utf-8")
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
    assert "diagrams/loop-and-harness-architecture_imagen.png" in body, body
    assert "Loop and harness architecture" in body


def test_assemble_puts_an_unsectioned_diagram_under_figures(work, turns):
    """A rendered figure the outline never placed still belongs in the paper."""
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.do_outline(run)
    dest = run.file("diagrams")
    dest.mkdir(parents=True, exist_ok=True)
    png = dest / "orphan_imagen.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
    run.write_json(
        "diagrams.json",
        {
            "figures": [
                {
                    "name": "orphan",
                    "section": "s-missing",
                    "caption": "An orphaned figure",
                    "path": f"diagrams/{png.name}",
                }
            ]
        },
    )
    section_dir = run.file("sections")
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "s1.md").write_text("A thing is true [1].\n", encoding="utf-8")
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
    assert "## Figures" in body, body
    assert "diagrams/orphan_imagen.png" in body


def test_linear_runs_charts_before_write():
    """`diagram` moved out of `LINEAR` (#476); `charts` is the only figure
    phase left here, and it still runs before the write/diagram/assemble
    cycle."""
    names = [name for _n, name, _out, _fn in paper.LINEAR]
    assert "diagram" not in names
    assert names.index("charts") < len(names)


def test_diagram_runs_after_write():
    """#476: a figure is commissioned from the section's own claims, which
    do not exist until the section is written. `diagram` sits in `CYCLE`,
    between `write` and `assemble`."""
    names = [name for _n, name, _fn in paper.CYCLE]
    assert names.index("write") < names.index("diagram") < names.index("assemble")


# -- the renderer is named, and a label is a name (#371) ------------------------


def test_the_sidecar_names_the_renderer_that_drew_the_chart(tmp_path):
    """matplotlib was not installed, the ImportError was swallowed, and a
    stdlib fallback with no text drew the first paper's chart. The review
    judge called it an unlabeled dump. Nothing on disk said why.
    """
    pytest.importorskip("matplotlib")
    spec = {"name": "c", "type": "bar", "x": "k", "y": "v", "section": "s1"}
    rows = [{"k": "a", "v": 1, "source": "u"}, {"k": "b", "v": 2, "source": "u"}]
    side = charts.render(spec, rows, tmp_path)
    assert side["renderer"] == "matplotlib", side
    assert side["title"], side
    assert side["xlabel"] == "k", side
    assert side["ylabel"] == "v", side


def test_a_swallowed_renderer_error_is_named_in_the_sidecar(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ImportError("No module named 'matplotlib'")

    monkeypatch.setattr(charts, "_matplotlib_png", boom)
    spec = {"name": "c", "type": "bar", "x": "k", "y": "v", "section": "s1"}
    rows = [{"k": "a", "v": 1, "source": "u"}]
    side = charts.render(spec, rows, tmp_path)
    assert side["renderer"].startswith("stdlib fallback (ImportError"), side


def test_a_sentence_length_tick_label_is_cut_to_a_name(tmp_path, monkeypatch):
    """What `set_xticks` receives, not the PNG's size, which is fixed either way."""
    matplotlib = pytest.importorskip("matplotlib")
    import matplotlib.axes  # noqa: PLC0415

    seen = []
    original = matplotlib.axes.Axes.set_xticks

    def record(self, ticks, labels=None, **kw):
        seen.append(list(labels or []))
        return original(self, ticks, labels, **kw)

    monkeypatch.setattr(matplotlib.axes.Axes, "set_xticks", record)
    long = "traces annotated in the MAST study (more than 1,600), across seven frameworks"
    charts._matplotlib_png(tmp_path / "c.png", [long, "b"], [1.0, 2.0], {}, "bar")
    assert seen, "set_xticks never ran"
    assert all(len(lab) <= charts.TICK_LABEL_CHARS for lab in seen[-1]), seen[-1]
    assert seen[-1][0].endswith("…") and seen[-1][1] == "b"


def test_a_corpus_reference_is_not_a_host_to_check():
    """`corpus:` names a claim in the brain. It has no host and is not this row's business."""
    import checks  # noqa: PLC0415

    sources = ["corpus:claude.md (research/x.md:68-69)", "https://arxiv.org/abs/2503.13657"]
    assert checks.disallowed_reference_hosts(sources, ["arxiv.org"]) == []
    assert checks.disallowed_reference_hosts(["https://medium.com/x"], ["arxiv.org"]) == ["https://medium.com/x"]


# -- the ledger fallback answers the figure, not the ledger (#375) -------------

_LEDGER = {"entries": [{"section_id": "s1", "numbers": [
    {"measures": "traces annotated in the MAST study (more than 1,600)", "value": "1600"},
    {"measures": "multi-agent frameworks from which MAST traces were drawn", "value": "7"},
    {"measures": "inter-annotator agreement on MAST failure mode labels", "value": "0.88"},
    {"measures": "share of failures attributed to system-design and specification issues", "value": "41.8"},
    {"measures": "share of failures attributed to inter-agent misalignment", "value": "36.9"},
    {"measures": "share of failures attributed to task verification", "value": "21.3"},
    {"measures": "token cost multiple of Anthropic's multi-agent research system relative to chat", "value": "15"},
    {"measures": "models evaluated in the Chroma Context Rot report", "value": "18"},
]}]}


def test_the_ledger_fallback_keeps_only_the_numbers_the_figure_is_named_for():
    """Fifteen numbers of four kinds went on one axis. The name admits one."""
    figure = {
        "name": "token-cost-multipliers",
        "shows": "Relative token cost of a single-agent chat baseline versus a multi-agent research system.",
        "data_needed": "Reported token-cost multiples from the corpus: multi-agent systems use approximately 15x more tokens than chat.",
    }
    rows = charts._rows_from_ledger(_LEDGER, figure)
    assert [r["y"] for r in rows] == [15.0], rows


def test_the_ledger_fallback_matches_a_figure_about_failure_shares():
    figure = {"name": "failure-share-by-category", "shows": "MAST failure categories."}
    rows = charts._rows_from_ledger(_LEDGER, figure)
    assert sorted(r["y"] for r in rows) == [21.3, 36.9, 41.8], rows


def test_a_stopword_is_never_a_reason_to_admit_a_number():
    figure = {"name": "chart", "data_needed": "the and from that with"}
    rows = charts._rows_from_ledger(_LEDGER, figure)
    # No real term at all, so every number is admitted. That is the wide
    # match a figure with nothing to say falls back to, and it is not the bug.
    assert len(rows) == 8
    figure = {"name": "chart", "data_needed": "the report"}
    rows = charts._rows_from_ledger(_LEDGER, figure)
    assert [r["y"] for r in rows] == [18.0], "only the Chroma report row names a report"


# -- one value is a sentence, not a chart (#378) -------------------------------


def test_do_charts_skips_a_figure_the_ledger_serves_with_one_number(work, turns, monkeypatch):
    """The review judge: "conveys exactly one number that line 21 already states
    in a sentence." It failed `figured`, its caption failed `evidenced`, and the
    writer could not remove it because assembly appends it regardless.
    """
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    import diagrams  # noqa: PLC0415

    monkeypatch.setattr(diagrams, "available", lambda: False)
    run = paper.Run(
        topic="a topic", work_dir=work, turns=turns(root=work),
        state=paper.State.load_or_new(work, "a topic"), brain=None,
        log=lambda *a: None, enforce_research_policy=False,
    )
    paper.prior_art(run); paper.plan(run)
    stamped = json.loads((Path(work) / "outline.approved.json").read_text())
    outline = stamped.get("outline", stamped)
    outline["sections"][0]["figures"] = [{"name": "token-cost-multipliers", "kind": "chart",
                                          "shows": "token cost", "data_needed": "the 15x multiple"}]
    (Path(work) / "outline.approved.json").write_text(json.dumps(stamped), encoding="utf-8")
    (Path(work) / "paper_ledger.json").write_text(json.dumps({"entries": [{"section_id": "s1", "numbers": [
        {"measures": "token cost multiple of the multi-agent system", "value": "15"},
        {"measures": "traces annotated in the study", "value": "1600"},
    ]}]}), encoding="utf-8")
    meta = paper.do_charts(run)
    assert meta["skipped"] == 1, meta
    assert meta["rendered"] == 0, meta
    # #386, #464. Named, not a bare string: a reader (and `assemble`) needs
    # the owning section and the reason, not only the fact that one figure
    # never rendered.
    recorded = json.loads((Path(work) / "charts.json").read_text())["skipped"]
    assert recorded == [
        {
            "name": "token-cost-multipliers",
            "section": "s1",
            "reason": "1 value, a sentence, not a chart",
        }
    ], recorded
