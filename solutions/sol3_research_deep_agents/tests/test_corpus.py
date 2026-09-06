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


URL_SHA = "sha256:0000000000000000000000000000000000000000000000000000000000000388"


def _url_brain(tmp_path: Path, source_front: str, source_body: str) -> Path:
    """One claim, one evidence, one source. The source front matter and body vary."""
    root = tmp_path / "urlbrain"
    research = root / "research"
    for folder in ("claims", "evidence", "sources"):
        (research / folder).mkdir(parents=True, exist_ok=True)
    (research / "claims" / "claim.url-probe.01TEST.md").write_text(
        '---\ntype: "Claim"\nid: "claim.url-probe.01TEST"\n'
        'description: "A locator needs a public url on the hit."\n'
        "confidence: 0.9\n"
        'links:\n  - rel: evidenced_by\n    target: "evidence.url-probe.01TEST"\n'
        "---\n\n# Claim\n\nA locator needs a public url on the hit.\n",
        encoding="utf-8",
    )
    (research / "evidence" / "evidence.url-probe.01TEST.md").write_text(
        '---\ntype: "Evidence"\nid: "evidence.url-probe.01TEST"\n'
        'text: "Quoted for the url probe."\n'
        f'source_hash: "{URL_SHA}"\n'
        'locator:\n  variant: "quote"\n'
        '  asset_path: "research/source-assets/url-probe/original.md"\n'
        "  start_line: 1\n  end_line: 2\n"
        "---\n\nQuoted for the url probe.\n",
        encoding="utf-8",
    )
    (research / "sources" / "source.url-probe.01TEST.md").write_text(
        '---\ntype: "SourceDocument"\nid: "source.url-probe.01TEST"\n'
        'title: "Url probe source"\nvendor: "Spillwave"\nsource_kind: "reference_doc"\n'
        f'source_hash: "{URL_SHA}"\n'
        f"{source_front}---\n\n{source_body}",
        encoding="utf-8",
    )
    return root


def _url_hit(root: Path):
    hits = corpus.search("locator public url", [root], limit=5)
    assert hits, "the probe brain has to yield its one claim"
    return hits[0]


def test_a_front_matter_url_wins_over_a_body_url(tmp_path):
    root = _url_brain(
        tmp_path,
        'url: "https://arxiv.org/abs/2503.13657"\n',
        "Retrieved for: locators\n\nhttps://example.org/decoy\n",
    )
    assert _url_hit(root).url == "https://arxiv.org/abs/2503.13657"


def test_a_body_url_is_lifted_when_the_front_matter_has_none(tmp_path):
    root = _url_brain(tmp_path, "", "https://example.org/paper\n\nRetrieved for: locators\n")
    assert _url_hit(root).url == "https://example.org/paper"


def test_a_capture_with_no_url_is_empty_and_does_not_crash(tmp_path):
    root = _url_brain(tmp_path, "", "Retrieved for the sol3 fixture corpus.\n")
    hit = _url_hit(root)
    assert hit.url == ""
    assert hit.source_title == "Url probe source"


def test_a_hit_carries_the_evidence_source_hash(tmp_path):
    root = _url_brain(tmp_path, "", "Retrieved for the sol3 fixture corpus.\n")
    assert _url_hit(root).source_hash == URL_SHA


def test_the_pack_carries_the_url_in_json_and_markdown(tmp_path):
    root = _url_brain(tmp_path, 'url: "https://arxiv.org/abs/2503.13657"\n', "Retrieved.\n")
    packed = corpus.pack("locator public url", [root], tmp_path / "pack", limit=5)
    js = json.loads((tmp_path / "pack" / "brain-pack.json").read_text(encoding="utf-8"))
    assert js["hits"][0]["url"] == "https://arxiv.org/abs/2503.13657"
    assert js["hits"][0]["source_hash"] == URL_SHA
    assert packed["hits"][0]["url"] == "https://arxiv.org/abs/2503.13657"
    md = (tmp_path / "pack" / "brain-pack.md").read_text(encoding="utf-8")
    source_line = "**Source.** Url probe source (Spillwave), reference_doc"
    assert f"{source_line} <https://arxiv.org/abs/2503.13657>" in md


def test_format_hits_shows_a_url_only_when_there_is_one():
    with_url = corpus.Hit(key="b:c1", claim="c", quote="q", url="https://example.org/paper")
    without = corpus.Hit(key="b:c2", claim="c", quote="q")
    assert "  URL: https://example.org/paper" in corpus.format_hits([with_url])
    assert "URL:" not in corpus.format_hits([without])


def test_a_valueless_front_matter_url_falls_through_to_the_body(tmp_path):
    """`url:` with nothing after it parses to a dict. It is not a url."""
    root = _url_brain(tmp_path, "url:\n", "https://example.org/body\n\nRetrieved.\n")
    assert _url_hit(root).url == "https://example.org/body"
