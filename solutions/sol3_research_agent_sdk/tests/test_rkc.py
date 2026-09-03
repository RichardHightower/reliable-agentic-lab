"""The knowledge bundle. What the run checked and threw out is the record."""

from __future__ import annotations

import re

import rkc


def test_the_self_check_runs():
    """It writes a bundle and validates it against the installed plugin."""
    assert rkc.demo() == 0


def test_a_ulid_uses_crockford_base32():
    """No I, L, O, or U, so an id cannot be misread back to a person."""
    for _ in range(20):
        assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", rkc.ulid())


def test_two_ulids_in_the_same_millisecond_differ():
    assert len({rkc.ulid() for _ in range(200)}) == 200


def test_a_long_slug_keeps_a_digest_so_it_stays_unique():
    first = rkc.slug("a" * 100 + "one")
    second = rkc.slug("a" * 100 + "two")
    assert first != second
    assert len(first) <= 64


def test_a_title_with_a_colon_does_not_break_the_front_matter(tmp_path):
    plan = {
        "sections": [{"id": "s1", "heading": "H: with a colon", "goal": "g"}],
        "questions": [{"id": "q1", "text": "why: because", "section": "s1"}],
    }
    claims = [
        {
            "id": "c1",
            "text": "A claim: with a colon.",
            "source_url": "https://e.invalid",
            "quote": "q",
            "section": "s1",
            "status": "verified",
        }
    ]
    root = tmp_path / "knowledge"
    rkc.write_bundle(
        root,
        topic="a: topic",
        area="an area",
        plan=plan,
        findings=[{"answer": "a", "sources": [{"url": "https://e.invalid", "title": "T: t"}]}],
        claims=claims,
    )
    ok, note = rkc.validate(root)
    assert ok, note


def test_a_contradicted_claim_is_recorded_as_rejected(tmp_path):
    """Losing it means the next run pays to rediscover the same wrong answer."""
    plan = {
        "sections": [{"id": "s1", "heading": "H", "goal": "g"}],
        "questions": [{"id": "q1", "text": "q", "section": "s1"}],
    }
    claims = [
        {
            "id": "c1",
            "text": "Wrong.",
            "source_url": "https://e.invalid",
            "quote": "q",
            "section": "s1",
            "status": "contradicted",
        }
    ]
    root = tmp_path / "knowledge"
    rkc.write_bundle(
        root,
        topic="t",
        area="a",
        plan=plan,
        findings=[{"answer": "a", "sources": [{"url": "https://e.invalid", "title": "T"}]}],
        claims=claims,
    )
    written = list((root / "research" / "claims").glob("*.md"))
    assert len(written) == 1
    assert 'status: "rejected"' in written[0].read_text()


def test_a_verdict_becomes_a_confidence(tmp_path):
    assert rkc.STATUS_FOR["verified"][1] > rkc.STATUS_FOR["disputed"][1]
    assert rkc.STATUS_FOR["disputed"][1] > rkc.STATUS_FOR["unverified"][1]
    assert rkc.STATUS_FOR["unverified"][1] > rkc.STATUS_FOR["contradicted"][1]


def test_validation_without_the_plugin_is_not_a_failure(tmp_path, monkeypatch):
    """A run must not die because an optional tool is missing."""
    monkeypatch.setattr(rkc, "VALIDATOR", tmp_path / "nope.py")
    ok, note = rkc.validate(tmp_path)
    assert ok
    assert "not installed" in note


def test_a_section_loop_finding_still_archives_its_source(tmp_path):
    """The section loop stores source as a dict, not a list. The bundle must not drop it."""
    plan = {
        "sections": [{"id": "s1", "heading": "H", "goal": "g"}],
        "questions": [{"id": "q1", "text": "q", "section": "s1"}],
    }
    findings = [
        {
            "claim": "A loop computes done.",
            "quote": "a loop computes done",
            "origin": "corpus",
            "source": {
                "kind": "corpus",
                "url_or_path": "brain:claim.seminar-exit-doctrine",
                "title": "Exit doctrine",
                "vendor": "Spillwave",
            },
        }
    ]
    claims = [
        {
            "id": "c1",
            "text": "A loop computes done.",
            "source_url": "brain:claim.seminar-exit-doctrine",
            "quote": "a loop computes done",
            "section": "s1",
            "status": "verified",
        }
    ]
    root = tmp_path / "knowledge"
    counts = rkc.write_bundle(
        root, topic="t", area="a", plan=plan, findings=findings, claims=claims
    )
    assert counts["sources"] == 1
    assert list((root / "research" / "source-assets").glob("*/original.md"))


def test_the_ledger_becomes_a_finding(tmp_path):
    plan = {
        "sections": [{"id": "s1", "heading": "H", "goal": "g"}],
        "questions": [],
    }
    claims = [
        {
            "id": "c1",
            "text": "A thing is true.",
            "source_url": "https://e.invalid",
            "quote": "q",
            "section": "s1",
            "status": "verified",
        }
    ]
    root = tmp_path / "knowledge"
    counts = rkc.write_bundle(
        root,
        topic="t",
        area="a",
        plan=plan,
        findings=[{"sources": [{"url": "https://e.invalid", "title": "T"}]}],
        claims=claims,
        ledger={
            "entries": [
                {
                    "section_id": "s1",
                    "heading": "H",
                    "claims": [{"claim": "A thing is true.", "ref": "1"}],
                    "numbers": [],
                    "terms_defined": [{"term": "done", "definition": "the first exit"}],
                }
            ]
        },
    )
    bodies = [p.read_text() for p in (root / "research" / "findings").glob("*.md")]
    assert any("Ledger: H" in body for body in bodies)
    assert counts["findings"] == 2


def _git_repo(path, branch="main"):
    import subprocess  # noqa: PLC0415

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "sol3@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "sol3"], cwd=path, check=True)
    subprocess.run(["git", "checkout", "-q", "-B", branch], cwd=path, check=True)
    (path / "README").write_text("brain\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)
    return path


def test_ingest_refuses_to_write_main(tmp_path):
    repo = _git_repo(tmp_path / "brain")
    knowledge = repo / "knowledge"
    knowledge.mkdir()
    bundle = tmp_path / "bundle"
    (bundle / "research" / "claims").mkdir(parents=True)
    (bundle / "research" / "claims" / "claim.x.md").write_text("x\n", encoding="utf-8")
    result = rkc.ingest_brain(bundle, knowledge, open_pr=False)
    assert result["ok"] is False
    assert "main" in result["reason"]
    assert not (knowledge / "research" / "claims" / "claim.x.md").exists()


def test_ingest_copies_onto_a_worktree_branch(tmp_path):
    import subprocess  # noqa: PLC0415

    repo = _git_repo(tmp_path / "brain")
    subprocess.run(["git", "checkout", "-q", "-b", "ingest/sol3"], cwd=repo, check=True)
    knowledge = repo / "knowledge"
    knowledge.mkdir()
    bundle = tmp_path / "bundle"
    (bundle / "research" / "claims").mkdir(parents=True)
    (bundle / "research" / "claims" / "claim.x.md").write_text("a new claim\n", encoding="utf-8")
    result = rkc.ingest_brain(bundle, knowledge, open_pr=False)
    assert result["ok"] is True
    assert result["copied"] == 1
    assert result["branch"] == "ingest/sol3"
    assert (knowledge / "research" / "claims" / "claim.x.md").read_text() == "a new claim\n"
    assert result["commit"]


def test_ingest_does_not_overwrite_an_existing_claim(tmp_path):
    import subprocess  # noqa: PLC0415

    repo = _git_repo(tmp_path / "brain")
    subprocess.run(["git", "checkout", "-q", "-b", "ingest/sol3"], cwd=repo, check=True)
    knowledge = repo / "knowledge"
    dest = knowledge / "research" / "claims"
    dest.mkdir(parents=True)
    (dest / "claim.x.md").write_text("original\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    (bundle / "research" / "claims").mkdir(parents=True)
    (bundle / "research" / "claims" / "claim.x.md").write_text("replacement\n", encoding="utf-8")
    result = rkc.ingest_brain(bundle, knowledge, open_pr=False, commit=False)
    assert result["ok"] is True
    assert result["copied"] == 0
    assert (dest / "claim.x.md").read_text() == "original\n"
