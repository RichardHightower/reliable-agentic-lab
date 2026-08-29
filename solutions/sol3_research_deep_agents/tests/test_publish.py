"""The gist push. Hermetic: no `gh`, no `git`, no network."""

from __future__ import annotations

import json
from pathlib import Path

import publish
import pytest

BODY = (
    "---\ntitle: X\n---\n\n"
    "# Exit conditions\n\n"
    "A fact. [1]\n\n"
    "![A flowchart of the exits](figures/exits_imagen.png)\n\n"
    "![A sequence of the roles](figures/roles_imagen.png)\n\n"
    "![remote](https://example.com/x.png)\n\n"
    "## References\n\n1. https://a.example\n"
)


@pytest.fixture
def ready(tmp_path: Path) -> Path:
    work = tmp_path / "run"
    (work / "figures").mkdir(parents=True)
    (work / "whitepaper.md").write_text(BODY)
    (work / "figures" / "exits_imagen.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (work / "figures" / "roles_imagen.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (work / "gates.json").write_text(json.dumps({"passed": True, "failures": []}))
    return work


def test_demo_assertions_hold():
    publish.demo()


# -- the gate --------------------------------------------------------------


def test_a_failed_gate_blocks_the_push(ready):
    """This refusal is the difference between a gate and a warning."""
    (ready / "gates.json").write_text(json.dumps({"passed": False, "failures": ["grounded"]}))
    with pytest.raises(publish.PublishRefused) as exc:
        publish.push(ready, dry_run=True)
    assert "grounded" in str(exc.value)


def test_an_unassembled_paper_blocks(ready):
    (ready / "gates.json").unlink()
    with pytest.raises(publish.PublishRefused):
        publish.push(ready, dry_run=True)


def test_a_missing_paper_blocks(ready):
    (ready / "whitepaper.md").unlink()
    with pytest.raises(publish.PublishRefused):
        publish.push(ready, dry_run=True)


# -- staging ---------------------------------------------------------------


def test_a_dry_run_touches_neither_gh_nor_git(ready, tmp_path, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("a dry run must not shell out")

    monkeypatch.setattr(publish.subprocess, "run", explode)
    result = publish.push(ready, dry_run=True, out_dir=tmp_path / "staged")
    assert result.staged


def test_front_matter_is_stripped(ready, tmp_path):
    publish.push(ready, dry_run=True, out_dir=tmp_path / "staged")
    body = (tmp_path / "staged" / "whitepaper.md").read_text()
    assert body.startswith("# Exit conditions")
    assert "title: X" not in body


def test_figures_are_staged_with_an_order_prefix(ready, tmp_path):
    """A gist is flat, and figure names collide across papers."""
    publish.push(ready, dry_run=True, out_dir=tmp_path / "staged")
    staged = sorted(p.name for p in (tmp_path / "staged").iterdir())
    assert staged == ["01-exits_imagen.png", "02-roles_imagen.png", "whitepaper.md"]


def test_the_markdown_is_staged_first(ready, tmp_path):
    """A gist shows its first file. A reader landing on a PNG has to hunt."""
    result = publish.push(ready, dry_run=True, out_dir=tmp_path / "staged")
    assert result.staged[0].name == "whitepaper.md"


def test_local_image_links_become_raw_urls(ready, tmp_path):
    publish.push(ready, dry_run=True, gist_id="abc123", out_dir=tmp_path / "staged")
    body = (tmp_path / "staged" / "whitepaper.md").read_text()
    assert "/abc123/raw/01-exits_imagen.png" in body
    assert "/abc123/raw/02-roles_imagen.png" in body


def test_a_remote_image_is_left_alone(ready, tmp_path):
    publish.push(ready, dry_run=True, out_dir=tmp_path / "staged")
    body = (tmp_path / "staged" / "whitepaper.md").read_text()
    assert "https://example.com/x.png" in body


def test_a_missing_figure_keeps_its_original_link(ready, tmp_path):
    """Better a broken relative link than a raw URL to a file that is not there."""
    (ready / "figures" / "exits_imagen.png").unlink()
    publish.push(ready, dry_run=True, gist_id="abc123", out_dir=tmp_path / "staged")
    body = (tmp_path / "staged" / "whitepaper.md").read_text()
    assert "(figures/exits_imagen.png)" in body


# -- the id map ------------------------------------------------------------


def test_the_id_map_round_trips(tmp_path):
    path = tmp_path / "gist-ids.tsv"
    publish.write_id("a-paper", "abc123", path)
    publish.write_id("b-paper", "def456", path)
    assert publish.read_ids(path) == {"a-paper": "abc123", "b-paper": "def456"}


def test_the_id_map_ignores_comments(tmp_path):
    path = tmp_path / "gist-ids.tsv"
    path.write_text("# a comment\n\na-paper\tabc123\n")
    assert publish.read_ids(path) == {"a-paper": "abc123"}


def test_a_known_slug_refreshes_rather_than_creating(ready, tmp_path, monkeypatch):
    """One gist per paper, forever. A new gist per run means a reader is
    looking at draft three."""
    path = tmp_path / "gist-ids.tsv"
    publish.write_id("run", "abc123", path)
    monkeypatch.setattr(publish, "gh_owner", lambda: "owner")
    monkeypatch.setattr(
        publish, "create_gist", lambda *a: pytest.fail("must not create a second gist")
    )
    synced = {}
    monkeypatch.setattr(publish, "sync", lambda gid, staged: synced.setdefault("id", gid) or True)

    result = publish.push(ready, id_map=path)
    assert synced["id"] == "abc123"
    assert result.created is False
    assert result.url == "https://gist.github.com/owner/abc123"


def test_a_first_push_records_the_new_id(ready, tmp_path, monkeypatch):
    path = tmp_path / "gist-ids.tsv"
    monkeypatch.setattr(publish, "gh_owner", lambda: "owner")
    monkeypatch.setattr(publish, "create_gist", lambda seed, desc: "newid42")
    monkeypatch.setattr(publish, "sync", lambda gid, staged: True)

    result = publish.push(ready, id_map=path)
    assert result.created is True
    assert publish.read_ids(path)["run"] == "newid42"


# -- secrecy ---------------------------------------------------------------


def test_gist_create_never_asks_for_a_public_gist(monkeypatch):
    """`gh gist create` is secret by default. Nothing here may change that."""
    seen = []
    monkeypatch.setattr(
        publish, "_retry", lambda argv, **kw: seen.append(argv) or "https://gist.github.com/u/abc1"
    )
    assert publish.create_gist(Path("x.md"), "a paper") == "abc1"
    assert seen[0][:3] == ["gh", "gist", "create"]
    assert "--public" not in seen[0]
    assert "-p" not in seen[0]


def test_a_gist_id_is_read_from_the_create_output(monkeypatch):
    monkeypatch.setattr(
        publish, "_retry", lambda argv, **kw: "Creating gist...\nhttps://gist.github.com/deadbeef99"
    )
    assert publish.create_gist(Path("x.md"), "d") == "deadbeef99"


def test_unreadable_create_output_fails_loudly(monkeypatch):
    monkeypatch.setattr(publish, "_retry", lambda argv, **kw: "something went sideways")
    with pytest.raises(publish.PublishFailed):
        publish.create_gist(Path("x.md"), "d")


# -- retries ---------------------------------------------------------------


def test_a_transient_failure_is_retried(monkeypatch):
    calls = {"n": 0}

    class Proc:
        def __init__(self, code):
            self.returncode = code
            self.stdout = "ok"
            self.stderr = "flaky"

    def run(argv, **kwargs):
        calls["n"] += 1
        return Proc(0 if calls["n"] == 3 else 1)

    monkeypatch.setattr(publish.subprocess, "run", run)
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    assert publish._retry(["gh", "x"], what="x") == "ok"
    assert calls["n"] == 3


def test_a_persistent_failure_gives_up(monkeypatch):
    class Proc:
        returncode = 1
        stdout = ""
        stderr = "gone"

    monkeypatch.setattr(publish.subprocess, "run", lambda argv, **kw: Proc())
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    with pytest.raises(publish.PublishFailed):
        publish._retry(["gh", "x"], what="x")
