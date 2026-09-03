"""corpus.py: search, pack, resolve, shard walk, missing root."""

from __future__ import annotations

import json
from pathlib import Path

import corpus
import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "brain"


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    corpus.clear_cache()
    yield
    corpus.clear_cache()


def test_the_fixture_brain_has_fifty_claims():
    assert len(corpus.claim_files(FIXTURE)) >= 50


def test_search_ranks_by_distinct_terms_then_confidence():
    hits = corpus.search("exit criteria done cost max turns", [FIXTURE], limit=5)
    assert hits
    assert hits[0].score >= hits[-1].score
    assert "exit" in hits[0].claim.lower() or "done" in hits[0].claim.lower()


def test_search_walks_sharded_and_flat_claims():
    files = corpus.claim_files(FIXTURE)
    assert any("harness-ch03" in p.as_posix() for p in files)
    assert any(p.parent.name == "claims" and p.name.startswith("claim.seminar-") for p in files)


def test_a_hit_resolves_evidence_quote_and_source():
    hits = corpus.search("exit doctrine rubric", [FIXTURE], limit=3)
    assert hits
    hit = hits[0]
    assert hit.quote
    assert hit.source_title
    assert hit.locator.asset_path
    assert hit.epistemic in {"corroborated", "source_supported", "unsupported"}
    assert hit.key.startswith("brain:")


def test_resolve_round_trips_a_key():
    hits = corpus.search("writer scope sections", [FIXTURE], limit=1)
    found = corpus.resolve(hits[0].key, [FIXTURE])
    assert found is not None
    assert found.claim_id == hits[0].claim_id
    assert corpus.resolve("nope:missing", [FIXTURE]) is None


def test_subject_filter_keeps_the_named_shard():
    hits = corpus.search("budget", [FIXTURE], subjects=["harness-ch03"], limit=20)
    assert hits
    assert all("harness-ch03" in (h.subject + h.claim_id) for h in hits)


def test_seminar_glob_keeps_seminar_claims():
    hits = corpus.search("loop", [FIXTURE], subjects=["seminar-*"], limit=40)
    assert hits
    assert all("seminar-" in h.claim_id for h in hits)


def test_a_missing_root_is_a_note_not_an_error(tmp_path):
    packed = corpus.pack("topic", [tmp_path / "absent"], tmp_path / "pack")
    assert packed["corpus_thin"] is True
    assert packed["hits"] == []
    text = (tmp_path / "pack" / "brain-pack.md").read_text(encoding="utf-8")
    assert "missing root" in text or "No second brain" in text


def test_pack_writes_markdown_and_json_and_keys(tmp_path):
    packed = corpus.pack("exit criteria", [FIXTURE], tmp_path / "pack", limit=10)
    assert packed["keys"]
    assert len(packed["hits"]) <= 10
    md = (tmp_path / "pack" / "brain-pack.md").read_text(encoding="utf-8")
    js = json.loads((tmp_path / "pack" / "brain-pack.json").read_text(encoding="utf-8"))
    assert "Not verified" in md
    assert packed["keys"][0] in md
    assert js["keys"] == packed["keys"]
    assert "subjects" in js


def test_pack_marks_thin_when_few_hits(tmp_path):
    packed = corpus.pack("zzqxj7vm", [FIXTURE], tmp_path / "pack")
    assert packed["hits"] == []
    assert packed["corpus_thin"] is True


def test_default_roots_stack_flag_and_env_and_fall_back_to_sibling(tmp_path):
    extra = tmp_path / "flag"
    extra.mkdir()
    env_root = tmp_path / "env"
    env_root.mkdir()
    assert corpus.default_roots(extra=[extra], env=str(env_root)) == [extra, env_root]
    assert corpus.default_roots(extra=None, env=str(env_root)) == [env_root]
    assert corpus.default_roots(extra=None, env=None) == [corpus.DEFAULT_BRAIN]


def test_ingest_refuses_to_write_main(tmp_path):
    import subprocess  # noqa: PLC0415

    repo = tmp_path / "brain"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "sol3@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "sol3"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-B", "main"], cwd=repo, check=True)
    (repo / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    knowledge = repo / "knowledge"
    knowledge.mkdir()
    bundle = tmp_path / "bundle"
    (bundle / "research" / "claims").mkdir(parents=True)
    (bundle / "research" / "claims" / "claim.x.md").write_text("x\n", encoding="utf-8")
    result = corpus.ingest_brain(bundle, knowledge, open_pr=False)
    assert result["ok"] is False
    assert "main" in result["reason"]
    assert not (knowledge / "research" / "claims" / "claim.x.md").exists()


def test_ingest_copies_onto_a_worktree_branch(tmp_path):
    import subprocess  # noqa: PLC0415

    repo = tmp_path / "brain"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "sol3@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "sol3"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-B", "ingest/sol3"], cwd=repo, check=True)
    (repo / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    knowledge = repo / "knowledge"
    knowledge.mkdir()
    bundle = tmp_path / "bundle"
    (bundle / "research" / "claims").mkdir(parents=True)
    (bundle / "research" / "claims" / "claim.x.md").write_text("a new claim\n", encoding="utf-8")
    result = corpus.ingest_brain(bundle, knowledge, open_pr=False)
    assert result["ok"] is True
    assert result["copied"] == 1
    assert (knowledge / "research" / "claims" / "claim.x.md").read_text() == "a new claim\n"
