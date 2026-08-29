"""Publishing. The image rewrite is pure, so it is tested without a network."""

from __future__ import annotations

import json

import publish
import pytest


def test_the_self_check_runs():
    assert publish.demo() == 0


def test_only_markdown_images_are_rewritten():
    body = (
        "![fig](diagrams/x.png)\n"
        "[a link](diagrams/x.png)\n"
        "Prose that mentions diagrams/x.png.\n"
        "![remote](https://h/y.png)\n"
    )
    out = publish.rewrite_images(body, {"diagrams/x.png": "https://raw/x.png"})
    assert "![fig](https://raw/x.png)" in out
    assert "[a link](diagrams/x.png)" in out
    assert "Prose that mentions diagrams/x.png." in out
    assert "![remote](https://h/y.png)" in out


def test_an_unmapped_image_is_left_alone():
    assert publish.rewrite_images("![f](x.png)", {}) == "![f](x.png)"


def test_two_figures_with_the_same_basename_stay_distinct():
    """A gist is flat. `a/x.png` and `b/x.png` would collide on `x.png`."""
    assert publish.asset_name("a/x.png") != publish.asset_name("b/x.png")


def test_publishing_without_a_paper_refuses(tmp_path):
    with pytest.raises(publish.PublishError, match="Nothing to publish"):
        publish.publish(tmp_path, topic="t")


def test_a_failed_e2e_report_is_never_published(tmp_path):
    (tmp_path / "paper.md").write_text("# p")
    (tmp_path / "e2e-report.json").write_text(json.dumps({"passed": False}))

    with pytest.raises(publish.PublishError, match="did not pass"):
        publish.publish(tmp_path, topic="t")


def test_a_missing_gh_is_named_as_the_reason(tmp_path, monkeypatch):
    """Fail with the reason, not with a git error three steps later."""
    (tmp_path / "paper.md").write_text("# p")
    monkeypatch.setattr(publish.shutil, "which", lambda name: None)
    with pytest.raises(publish.PublishError, match="gh CLI is not on PATH"):
        publish.publish(tmp_path, topic="t")


def test_a_token_without_the_gist_scope_is_named(tmp_path, monkeypatch):
    (tmp_path / "paper.md").write_text("# p")
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/gh")

    class Ok:
        returncode = 0
        stdout = "Logged in. Token scopes: 'repo', 'workflow'"
        stderr = ""

    monkeypatch.setattr(publish, "_gh", lambda *a, **k: Ok())
    with pytest.raises(publish.PublishError, match=r"gist. scope"):
        publish.publish(tmp_path, topic="t")


def test_a_republish_reuses_the_recorded_gist(tmp_path, monkeypatch):
    """A second publish must update the link, not hand out a different one."""
    (tmp_path / "paper.md").write_text("# p")
    (tmp_path / "gist.json").write_text(json.dumps({"id": "abc123"}))
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/gh")
    calls = []

    class Result:
        def __init__(self, stdout="", code=0):
            self.stdout, self.stderr, self.returncode = stdout, "", code

    def gh(*args, **kwargs):
        calls.append(args)
        if args[0] == "auth":
            return Result("Token scopes: 'gist'")
        if args[0] == "api":
            return Result("someone\n")
        raise AssertionError(f"it created a second gist: {args}")

    monkeypatch.setattr(publish, "_gh", gh)
    monkeypatch.setattr(publish, "_git", lambda *a, **k: Result())
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: Result())
    (publish.CACHE / "gist-abc123").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(publish.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(publish.shutil, "copyfile", lambda *a, **k: None)

    record = publish.publish(tmp_path, topic="t")
    assert record["id"] == "abc123"
    assert ("gist", "create") not in [tuple(c[:2]) for c in calls]
    assert record["secret"] is True
    assert "not access controlled" in record["note"]


def test_it_never_asks_for_a_public_gist(tmp_path, monkeypatch):
    """`gh gist create` is secret by default and `--public` is the opt-out.
    There is no `--private` flag, and passing one fails with "unknown flag"."""
    (tmp_path / "paper.md").write_text("# p")
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/gh")
    seen = []

    class Result:
        def __init__(self, stdout=""):
            self.stdout, self.stderr, self.returncode = stdout, "", 0

    def gh(*args, **kwargs):
        seen.append(args)
        if args[0] == "auth":
            return Result("Token scopes: 'gist'")
        if args[0] == "api":
            return Result("someone\n")
        return Result("https://gist.github.com/someone/abc123\n")

    monkeypatch.setattr(publish, "_gh", gh)
    monkeypatch.setattr(publish, "_git", lambda *a, **k: Result())
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: Result())
    monkeypatch.setattr(publish.shutil, "rmtree", lambda *a, **k: None)
    (publish.CACHE / "gist-abc123").mkdir(parents=True, exist_ok=True)

    publish.publish(tmp_path, topic="t")
    create = next(args for args in seen if args[:2] == ("gist", "create"))
    assert "--public" not in create
    assert "--private" not in create


def test_a_dry_run_touches_nothing(tmp_path, monkeypatch):
    (tmp_path / "paper.md").write_text("# p\n\n![f](diagrams/x.png)")
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/gh")

    class Result:
        def __init__(self, stdout=""):
            self.stdout, self.stderr, self.returncode = stdout, "", 0

    monkeypatch.setattr(
        publish,
        "_gh",
        lambda *a, **k: Result("Token scopes: 'gist'" if a[0] == "auth" else "someone\n"),
    )
    out = publish.publish(tmp_path, topic="t", dry_run=True)
    assert out == {"user": "someone", "images": ["diagrams/x.png"], "dry_run": True}
    assert not (tmp_path / "gist.json").exists()


def test_an_existing_pdf_is_included_in_the_gist_record(tmp_path, monkeypatch):
    (tmp_path / "paper.md").write_text("# p")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.7")
    (tmp_path / "gist.json").write_text(json.dumps({"id": "abc123"}))
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/gh")

    class Result:
        def __init__(self, stdout="", code=0):
            self.stdout, self.stderr, self.returncode = stdout, "", code

    monkeypatch.setattr(
        publish,
        "_gh",
        lambda *a, **k: Result("Token scopes: 'gist'" if a[0] == "auth" else "someone\n"),
    )
    monkeypatch.setattr(publish, "_git", lambda *a, **k: Result())
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: Result())
    monkeypatch.setattr(publish.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(publish.shutil, "copyfile", lambda *a, **k: None)
    (publish.CACHE / "gist-abc123").mkdir(parents=True, exist_ok=True)

    record = publish.publish(tmp_path, topic="t")

    assert "paper.pdf" in record["files"]
