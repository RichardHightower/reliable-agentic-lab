"""Publish the finished paper and its figures to a private gist.

A gist is a git repository with a flat namespace and no subdirectories, and its
web view will not render a relative image path. Publishing therefore takes four
steps, not one:

    1. create the gist from paper.md, and read back its id
    2. clone it
    3. copy the figures in flat, and rewrite every image path to a raw URL
    4. commit and push

A gist is secret by default, and secret is not private. It is unlisted, not
access controlled, and anyone holding the URL can read the paper and fetch every
figure. Treat the URL as the credential. This module never passes `--public`.

Publishing is opt-in and it runs only after the paper passes. A research tool
that pushes outward by default is a research tool that publishes a draft.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
CACHE = FOLDER / ".cache"

IMAGE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")
GIST_URL = re.compile(r"https://gist\.github\.com/(?:[^/]+/)?([0-9a-f]+)")

RAW = "https://gist.githubusercontent.com/{user}/{gist}/raw/{name}"


class PublishError(RuntimeError):
    """Publishing failed and nothing was pushed."""


def _gh(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args], cwd=cwd, text=True, capture_output=True, check=False, timeout=120
    )


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=False, timeout=120
    )


def preflight() -> None:
    """Fail with the reason, not with a git error three steps later."""
    if not shutil.which("gh"):
        raise PublishError("the gh CLI is not on PATH. Install it, then `gh auth login`.")
    status = _gh("auth", "status")
    if status.returncode != 0:
        raise PublishError("gh is not authenticated. Run `gh auth login`.")
    if "gist" not in (status.stdout + status.stderr):
        raise PublishError("the gh token has no `gist` scope. Run `gh auth refresh -s gist`.")


def asset_name(path: str) -> str:
    """A flat, unique filename for a figure inside the gist.

    A gist has no directories, so `diagrams/pipeline.png` and
    `appendix/pipeline.png` would collide on `pipeline.png`. Folding the
    separators into the name keeps them distinct.
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "-", path.strip("./")).strip("-")


def rewrite_images(body: str, mapping: dict[str, str]) -> str:
    """Point every local image at its raw gist URL. Leave everything else alone.

    Only markdown image syntax is touched. A link to a local file, a heading
    that happens to contain a path, and an image already on a remote host all
    survive untouched.
    """

    def swap(match: re.Match) -> str:
        target = match.group(2)
        return f"{match.group(1)}{mapping.get(target, target)}{match.group(3)}"

    return IMAGE.sub(swap, body)


def local_images(body: str) -> list[str]:
    """Every local image path the paper references, in first-seen order."""
    found: list[str] = []
    for target in IMAGE.findall(body):
        path = target[1]
        if path.startswith(("http://", "https://", "data:")) or path in found:
            continue
        found.append(path)
    return found


def publish(work_dir: Path | str, *, topic: str, dry_run: bool = False) -> dict:
    """Push `paper.md` and its figures. Returns the gist record."""
    work = Path(work_dir).resolve()
    paper = work / "paper.md"
    if not paper.exists():
        raise PublishError(f"{paper} does not exist. Nothing to publish.")
    preflight()

    body = paper.read_text(encoding="utf-8")
    images = local_images(body)
    record_path = work / "gist.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}

    user = _gh("api", "user", "-q", ".login").stdout.strip()
    if not user:
        raise PublishError("could not read the GitHub login from gh.")

    if dry_run:
        return {"user": user, "images": images, "dry_run": True}

    gist_id = record.get("id")
    if not gist_id:
        # No `--private` flag exists. `gh gist create` is secret by default and
        # `--public` is the opt-out, so the safe call is the one that passes
        # neither. Passing `--private` fails with "unknown flag", which is the
        # better of the two ways that API could have been designed.
        created = _gh("gist", "create", "--desc", topic, str(paper))
        if created.returncode != 0:
            raise PublishError(f"gh gist create failed: {created.stderr.strip()}")
        match = GIST_URL.search(created.stdout + created.stderr)
        if not match:
            raise PublishError(f"could not read a gist id from: {created.stdout.strip()}")
        gist_id = match.group(1)

    CACHE.mkdir(parents=True, exist_ok=True)
    clone = CACHE / f"gist-{gist_id}"
    if clone.exists():
        shutil.rmtree(clone)
    cloned = subprocess.run(
        ["git", "clone", "--quiet", f"https://gist.github.com/{gist_id}.git", str(clone)],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if cloned.returncode != 0:
        raise PublishError(f"could not clone the gist: {cloned.stderr.strip()}")

    mapping = {}
    for path in images:
        source = work / path
        if not source.exists():
            continue
        name = asset_name(path)
        shutil.copyfile(source, clone / name)
        mapping[path] = RAW.format(user=user, gist=gist_id, name=name)

    (clone / "paper.md").write_text(rewrite_images(body, mapping), encoding="utf-8")

    _git("add", "-A", cwd=clone)
    committed = _git("commit", "-m", f"Publish: {topic}", cwd=clone)
    # An unchanged republish is not a failure. Push anyway; git no-ops.
    if committed.returncode != 0 and "nothing to commit" not in committed.stdout:
        raise PublishError(f"could not commit to the gist: {committed.stderr.strip()}")
    pushed = _git("push", "--quiet", "origin", "HEAD", cwd=clone)
    if pushed.returncode != 0:
        raise PublishError(f"could not push the gist: {pushed.stderr.strip()}")

    record = {
        "id": gist_id,
        "url": f"https://gist.github.com/{user}/{gist_id}",
        "user": user,
        "topic": topic,
        "files": ["paper.md", *sorted(mapping.values())],
        "secret": True,
        "note": "A secret gist is unlisted, not access controlled. The URL is the credential.",
    }
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def demo() -> int:
    """Assert the pure parts. No network, no gh."""
    assert asset_name("diagrams/pipeline_imagen.png") == "diagrams-pipeline_imagen.png"
    assert asset_name("./a/b c.png") == "a-b-c.png"
    assert asset_name("diagrams/x.png") != asset_name("appendix/x.png")

    body = (
        "![fig](diagrams/x.png)\n"
        "[a link](diagrams/x.png)\n"
        "![remote](https://h/y.png)\n"
        "text about diagrams/x.png\n"
    )
    assert local_images(body) == ["diagrams/x.png"]
    out = rewrite_images(body, {"diagrams/x.png": "https://raw/x.png"})
    assert "![fig](https://raw/x.png)" in out
    assert "[a link](diagrams/x.png)" in out, "a plain link must not be rewritten"
    assert "![remote](https://h/y.png)" in out
    assert "text about diagrams/x.png" in out, "prose must not be rewritten"

    assert rewrite_images("![f](x.png)", {}) == "![f](x.png)", "no mapping, no change"
    assert GIST_URL.search("https://gist.github.com/RichardHightower/abc123").group(1) == "abc123"

    print("publish: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
