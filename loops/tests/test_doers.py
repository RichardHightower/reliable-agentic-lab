"""Checks for the doer backends.

Both tests here are for the same failure: a doer that reports success while
writing nothing. That bug does not raise, does not log, and does not fail a
suite. It surfaces two steps later as a red gate that refuses, which sends the
reader looking in the wrong place.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loops import doers


def _repo(tmp_path: Path) -> Path:
    """A git repo with a `known-good` branch and one file on it."""
    repo = tmp_path / "origin"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "models.py").write_text("VERSION = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--quiet", "-m", "one"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "checkout", "--quiet", "-b", "known-good"], cwd=repo, check=True)
    (repo / "app" / "models.py").write_text("VERSION = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--quiet", "-m", "two"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "checkout", "--quiet", "main"], cwd=repo, check=True)
    return repo


def test_reference_reads_a_ref_that_exists_only_on_the_remote(tmp_path):
    """The bug this catches: a fresh `git clone` creates one local branch.

    `known-good` exists only as `origin/known-good`, so `git ls-tree known-good`
    fails. The doer used to swallow that and copy nothing, and Module 2 then
    escalated on a red gate that had nothing to do with the real problem.
    """
    origin = _repo(tmp_path)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "--quiet", str(origin), str(clone)], check=True)

    # This is the state an attendee is in five minutes into the workshop.
    assert (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "known-good"],
            cwd=clone,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )

    result = doers.ReferenceBackend("known-good").run(repo=clone, prompt="", allow=["app/**"])
    assert result.wrote == ["app/models.py"]
    assert (clone / "app" / "models.py").read_text() == "VERSION = 2\n"


def test_reference_refuses_when_the_ref_is_nowhere(tmp_path):
    """Writing nothing must be an error, never a quiet success."""
    origin = _repo(tmp_path)
    with pytest.raises(doers.RefNotFound) as caught:
        doers.ReferenceBackend("no-such-branch").run(repo=origin, prompt="", allow=["app/**"])
    message = str(caught.value)
    assert "no-such-branch" in message
    assert "fetch" in message


def test_build_passes_an_already_built_backend_through_unchanged():
    """A runtime port hands build() a Backend it already constructed itself.

    build() must return that exact object, not try to string-dispatch on it.
    This is what lets implementer.run/fixer.run/enhancer.run accept a real
    SDK-backed Backend without themselves knowing SDKs exist.
    """
    backend = doers.NoneBackend()
    assert doers.build(backend) is backend


def test_build_still_string_dispatches_as_before():
    assert isinstance(doers.build("none"), doers.NoneBackend)
    assert isinstance(doers.build("reference"), doers.ReferenceBackend)
    assert isinstance(doers.build("claude"), doers.CliBackend)
