"""Push a finished white paper to a stable, secret GitHub gist.

Modeled on the article publisher this repo's author already runs:

    articles/gist/refresh-article-gist.sh

That script is 500 lines because it handles multi-part series and an article
tree. One white paper needs none of that, so this keeps its four load-bearing
rules and drops the rest.

**One gist per paper, forever.** The id lives in `gist-ids.tsv` next to this
file. Every later run refreshes the same gist, so a link you shared last month
still shows this month's paper. Creating a new gist per run is how a reader ends
up reading draft three.

**Secret, never public.** `gh gist create` defaults to secret, and no code path
here passes `--public`. Secret means unlisted, not private: anyone with the link
can read it. That is the point of the link, and it is worth saying out loud
before you paste one into a channel.

**Figures inline.** A gist is flat and renders only absolute image URLs, so each
figure is copied to the gist root under an `NN-` order prefix and every relative
image link is rewritten to the raw URL. Without this the paper publishes with
broken images and looks fine locally.

**The gate comes first.** `push` refuses when `gates.json` says a hard gate
failed. That refusal is the difference between a gate and a warning.

Publishing sends work out of this machine, so nothing calls it unless you ask.
`task paper` never publishes. `task publish` does.

    task publish -- --slug my-paper --dry-run --out /tmp/staged
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ID_MAP = HERE / "gist-ids.tsv"
PAPER_NAME = "whitepaper.md"
GATES_NAME = "gates.json"

OWNER_FALLBACK = "RichardHightower"
RAW_BASE = "https://gist.githubusercontent.com"
GIST_BASE = "https://gist.github.com"

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
REMOTE = re.compile(r"\Ahttps?://")

RETRIES = 4
BACKOFF = 3
GH_TIMEOUT = 120


class PublishRefused(RuntimeError):
    """The paper is not publishable. Fix the paper, not this file."""


class PublishFailed(RuntimeError):
    """GitHub did not cooperate. Retrying is reasonable."""


@dataclass
class Published:
    url: str = ""
    gist_id: str = ""
    staged: list[Path] = field(default_factory=list)
    created: bool = False
    unchanged: bool = False


# -- the id map -----------------------------------------------------------


def read_ids(path: Path = ID_MAP) -> dict[str, str]:
    if not path.exists():
        return {}
    ids = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        slug, _, gist_id = line.partition("\t")
        if gist_id.strip():
            ids[slug.strip()] = gist_id.strip()
    return ids


def write_id(slug: str, gist_id: str, path: Path = ID_MAP) -> None:
    """Append the row, and commit the file. A lost id means a second gist."""
    ids = read_ids(path)
    if ids.get(slug) == gist_id:
        return
    ids[slug] = gist_id
    rows = [
        "# tab-separated: slug<TAB>gist_id. Secret gists, one per paper.",
        "# publish.py appends a row on the first push. Commit this file so the",
        "# URL stays stable forever.",
    ]
    rows += [f"{name}\t{value}" for name, value in sorted(ids.items())]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


# -- staging --------------------------------------------------------------


def strip_front_matter(body: str) -> str:
    return FRONT_MATTER.sub("", body, count=1)


def figure_names(body: str) -> list[str]:
    """Every local figure the paper references, in the order it uses them."""
    names = []
    for _, target in IMAGE.findall(body):
        if REMOTE.match(target):
            continue
        name = Path(target).name
        if name not in names:
            names.append(name)
    return names


def staged_name(index: int, name: str) -> str:
    """`NN-` prefixed, because a gist is flat and figure names collide."""
    return f"{index:02d}-{name}"


def rewrite_images(body: str, mapping: dict[str, str], owner: str, gist_id: str) -> str:
    """Point every local image at its raw gist URL. A gist renders nothing else."""
    base = f"{RAW_BASE}/{owner}/{gist_id}/raw"

    def swap(match: re.Match) -> str:
        alt, target = match.group(1), match.group(2)
        if REMOTE.match(target):
            return match.group(0)
        name = mapping.get(Path(target).name)
        return match.group(0) if name is None else f"![{alt}]({base}/{name})"

    return IMAGE.sub(swap, body)


def check_gates(work_dir: Path) -> None:
    """Refuse a paper that failed its own gates. This is the whole point."""
    path = work_dir / GATES_NAME
    if not path.exists():
        raise PublishRefused(
            f"no {GATES_NAME} in {work_dir}. Run the assemble stage before publishing."
        )
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report.get("passed"):
        raise PublishRefused(
            f"the paper failed these hard gates: {report.get('failures')}. "
            "Fix them and reassemble. Publishing a paper that failed its own "
            "checks is worse than not publishing."
        )


def stage(work_dir: Path | str, out_dir: Path | str, *, gist_id: str, owner: str) -> list[Path]:
    """Build the exact file set the gist will hold. No `gh`, no `git`, no network.

    This is the whole transform, which is what makes `--dry-run` a real test and
    not a smoke check. Everything after this is plumbing.
    """
    work_dir, out_dir = Path(work_dir), Path(out_dir)
    paper = work_dir / PAPER_NAME
    if not paper.exists():
        raise PublishRefused(f"no {PAPER_NAME} in {work_dir}.")
    out_dir.mkdir(parents=True, exist_ok=True)

    body = strip_front_matter(paper.read_text(encoding="utf-8"))
    written: list[Path] = []
    mapping: dict[str, str] = {}

    for index, name in enumerate(figure_names(body), start=1):
        source = _find_figure(work_dir, name)
        if source is None:
            # A missing figure is not a reason to abandon the push. The link is
            # rewritten only for figures that exist, so the rest still render.
            continue
        target = out_dir / staged_name(index, name)
        shutil.copy2(source, target)
        mapping[name] = target.name
        written.append(target)

    target = out_dir / PAPER_NAME
    target.write_text(rewrite_images(body, mapping, owner, gist_id), encoding="utf-8")
    # The markdown goes first. A gist shows its first file, and a reader who
    # lands on `01-cover.png` has to hunt for the paper.
    return [target, *written]


def _find_figure(work_dir: Path, name: str) -> Path | None:
    for candidate in (work_dir / "figures" / name, work_dir / name):
        if candidate.exists():
            return candidate
    matches = sorted(work_dir.rglob(name))
    return matches[0] if matches else None


# -- github ---------------------------------------------------------------


def _retry(argv: list[str], *, what: str, cwd: Path | None = None) -> str:
    """Four attempts, linear backoff. GitHub fails transiently and often."""
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            proc = subprocess.run(
                argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=GH_TIMEOUT
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last = str(exc)
        else:
            if proc.returncode == 0:
                return proc.stdout.strip()
            last = proc.stderr.strip()[:300]
        if attempt < RETRIES:
            time.sleep(attempt * BACKOFF)
    raise PublishFailed(f"{what} failed after {RETRIES} attempts: {last}")


def gh_owner() -> str:
    try:
        proc = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return OWNER_FALLBACK
    return proc.stdout.strip() or OWNER_FALLBACK


def create_gist(seed: Path, description: str) -> str:
    """A new secret gist. `gh gist create` is secret unless told otherwise.

    There is deliberately no `--public` here, and no flag that could add one.
    """
    out = _retry(
        ["gh", "gist", "create", "--desc", description, str(seed)],
        what="gh gist create",
    )
    for line in reversed(out.split("\n")):
        match = re.search(r"gist\.github\.com/(?:[\w-]+/)?([0-9a-f]+)", line)
        if match:
            return match.group(1)
    raise PublishFailed(f"could not read a gist id from: {out[:200]}")


def sync(gist_id: str, staged: list[Path]) -> bool:
    """Replace the gist's file set through git. Returns whether anything changed.

    Git rather than `gh gist edit` because git is binary safe, which matters for
    PNG figures, and because `git add -A` records deletions. Editing file by file
    leaves last run's figures behind forever.
    """
    with tempfile.TemporaryDirectory(prefix="sol3-gist-") as tmp:
        repo = Path(tmp) / "repo"
        _retry(
            ["git", "clone", "--quiet", f"{GIST_BASE}/{gist_id}.git", str(repo)],
            what="git clone of the gist",
        )
        for existing in repo.iterdir():
            if existing.name == ".git":
                continue
            shutil.rmtree(existing) if existing.is_dir() else existing.unlink()
        for path in staged:
            shutil.copy2(path, repo / path.name)

        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        unchanged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=repo, check=False, capture_output=True
        )
        if unchanged.returncode == 0:
            return False
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=sol3-publish",
                "-c",
                "user.email=sol3-publish@users.noreply.github.com",
                "commit",
                "--quiet",
                "-m",
                "Refresh the white paper",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        _retry(["git", "push", "--quiet", "origin", "HEAD"], what="git push to the gist", cwd=repo)
        return True


# -- the entry point ------------------------------------------------------


def push(  # noqa: PLR0913  (the CLI surface, one keyword per flag)
    work_dir: Path | str,
    *,
    title: str = "",
    slug: str = "",
    dry_run: bool = False,
    out_dir: Path | str | None = None,
    gist_id: str = "",
    id_map: Path = ID_MAP,
) -> Published:
    """Stage the paper and push it. `dry_run` stages and stops."""
    work_dir = Path(work_dir)
    slug = slug or work_dir.name
    check_gates(work_dir)

    known = read_ids(id_map)
    gist_id = gist_id or known.get(slug, "")

    if dry_run:
        target = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="sol3-stage-"))
        staged = stage(work_dir, target, gist_id=gist_id or "DRYRUN", owner="DRYRUN")
        return Published(url=f"(dry run) {target}", gist_id=gist_id, staged=staged)

    owner = gh_owner()
    created = False
    if not gist_id:
        with tempfile.TemporaryDirectory(prefix="sol3-seed-") as tmp:
            seed = Path(tmp) / PAPER_NAME
            seed.write_text(
                strip_front_matter((work_dir / PAPER_NAME).read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            gist_id = create_gist(seed, title or slug)
        write_id(slug, gist_id, id_map)
        created = True

    with tempfile.TemporaryDirectory(prefix="sol3-stage-") as tmp:
        staged = stage(work_dir, Path(tmp), gist_id=gist_id, owner=owner)
        changed = sync(gist_id, staged)

    return Published(
        url=f"{GIST_BASE}/{owner}/{gist_id}",
        gist_id=gist_id,
        staged=[Path(p.name) for p in staged],
        created=created,
        unchanged=not changed,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--work-dir", default=None, help="the paper's work directory")
    parser.add_argument("--slug", default=None, help="the paper slug under work/paper/")
    parser.add_argument("--title", default="", help="the gist description")
    parser.add_argument("--dry-run", action="store_true", help="stage only, no gh and no git")
    parser.add_argument("--out", default=None, help="where a dry run stages its files")
    args = parser.parse_args(argv)

    if args.work_dir:
        work_dir = Path(args.work_dir)
    elif args.slug:
        work_dir = HERE / "work" / "paper" / args.slug
    else:
        print("give --work-dir or --slug")
        return 2

    try:
        result = push(
            work_dir,
            title=args.title,
            dry_run=args.dry_run,
            out_dir=args.out,
        )
    except (PublishRefused, PublishFailed) as exc:
        print(f"refused: {exc}" if isinstance(exc, PublishRefused) else f"failed: {exc}")
        return 1

    for path in result.staged:
        print(f"  {path.name}")
    if result.created:
        print("created a new secret gist. Commit gist-ids.tsv so the URL stays stable.")
    if result.unchanged:
        print("no changes. The gist was already up to date.")
    print(result.url)
    return 0


def demo() -> None:
    body = (
        "---\ntitle: X\nauthor: Y\n---\n\n"
        "# Paper\n\n![A flowchart of the loop](figures/loop_imagen.png)\n\n"
        "![remote](https://example.com/x.png)\n"
    )
    stripped = strip_front_matter(body)
    assert stripped.startswith("# Paper"), stripped[:40]
    assert "title: X" not in stripped

    assert figure_names(stripped) == ["loop_imagen.png"], "a remote image is not staged"
    assert staged_name(1, "loop_imagen.png") == "01-loop_imagen.png"

    out = rewrite_images(
        stripped, {"loop_imagen.png": "01-loop_imagen.png"}, "owner", "abc123"
    )
    assert f"{RAW_BASE}/owner/abc123/raw/01-loop_imagen.png" in out
    assert "https://example.com/x.png" in out, "a remote image is left alone"

    # A figure that was never staged keeps its original link rather than
    # pointing at a raw URL that does not exist.
    out = rewrite_images(stripped, {}, "owner", "abc123")
    assert "(figures/loop_imagen.png)" in out

    # Check the argv the code actually builds, not the source text. A grep for
    # the flag matches this comment and proves nothing.
    seen = []
    real_retry = globals()["_retry"]
    globals()["_retry"] = lambda argv, **kw: seen.append(argv) or "https://gist.github.com/u/abc123"
    try:
        assert create_gist(Path(__file__), "a paper") == "abc123"
    finally:
        globals()["_retry"] = real_retry
    assert seen and "--public" not in seen[0], f"gh gist create must stay secret: {seen}"
    assert seen[0][:3] == ["gh", "gist", "create"]

    print("publish: all demo assertions passed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        raise SystemExit(main())
