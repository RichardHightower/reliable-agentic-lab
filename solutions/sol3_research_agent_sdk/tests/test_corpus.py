"""corpus.py: search, pack, resolve, shard walk, missing root."""

from __future__ import annotations

import json
from pathlib import Path

import corpus
import outline as outlines
import paper
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


def test_unknown_corpus_refs_fail_validation(tmp_path):
    packed = corpus.pack("exit criteria", [FIXTURE], tmp_path / "pack", limit=5)
    drafted = {
        "title": "t",
        "audience": "a",
        "thesis": "x",
        "word_target_total": 400,
        "sections": [
            {
                "id": "s1",
                "heading": "The problem",
                "objective": "State it.",
                "abstract": "Two sentences about the problem. A third names the stake.",
                "key_questions": ["what is the problem", "why existing approaches fail"],
                "claims_to_support": ["The problem is structural."],
                "required_evidence": ["a primary specification"],
                "word_target": 400,
                "figures": [],
                "depends_on": [],
                "corpus_refs": ["not-a-real-key"],
            }
        ],
    }
    errors = outlines.validate(drafted, corpus_keys=packed["keys"])
    assert any("unknown key" in item for item in errors)


def test_known_corpus_refs_pass_validation(tmp_path):
    packed = corpus.pack("exit criteria", [FIXTURE], tmp_path / "pack", limit=5)
    drafted = {
        "title": "t",
        "audience": "a",
        "thesis": "x",
        "word_target_total": 400,
        "sections": [
            {
                "id": "s1",
                "heading": "The problem",
                "objective": "State it.",
                "abstract": "Two sentences about the problem. A third names the stake.",
                "key_questions": ["what is the problem", "why existing approaches fail"],
                "claims_to_support": ["The problem is structural."],
                "required_evidence": ["a primary specification"],
                "word_target": 400,
                "figures": [],
                "depends_on": [],
                "corpus_refs": packed["keys"][:1],
            }
        ],
    }
    assert outlines.validate(drafted, corpus_keys=packed["keys"]) == []


def test_corpus_pack_phase_writes_the_pack_files(work, turns):
    run = paper.Run(
        topic="exit criteria in a paper loop",
        work_dir=work,
        turns=turns(),
        state=paper.State.load_or_new(work, "exit criteria in a paper loop"),
        brain=FIXTURE,
        brains=[FIXTURE],
    )
    meta = paper.corpus_pack(run)
    assert meta["hits"] >= 1
    assert (work / "corpus" / "brain-pack.md").is_file()
    assert (work / "corpus" / "brain-pack.json").is_file()
    text = (work / "corpus" / "brain-pack.md").read_text(encoding="utf-8")
    assert "Not verified" in text


def test_corpus_pack_notes_a_missing_brain(work, turns):
    run = paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns(),
        state=paper.State.load_or_new(work, "a topic"),
        brain=None,
        brains=[],
    )
    meta = paper.corpus_pack(run)
    assert meta["hits"] == 0
    assert meta["corpus_thin"] is True
    text = (work / "corpus" / "brain-pack.md").read_text(encoding="utf-8")
    assert "No second brain" in text


def test_the_researcher_and_verifier_hold_corpus_search():
    import roleplan  # noqa: PLC0415

    roles = roleplan.plan(None, "research")
    assert "mcp__corpus__corpus_search" in roles["researcher"].tools
    assert "mcp__corpus__corpus_search" in roles["verifier"].tools
    assert "Bash" not in roles["researcher"].tools
    assert not roles["researcher"].can_write
    assert not roles["verifier"].can_write


def test_default_roots_stack_flag_and_env_and_fall_back_to_sibling(tmp_path):
    extra = tmp_path / "flag"
    extra.mkdir()
    env_root = tmp_path / "env"
    env_root.mkdir()
    assert corpus.default_roots(extra=[extra], env=str(env_root)) == [extra, env_root]
    assert corpus.default_roots(extra=None, env=str(env_root)) == [env_root]
    assert corpus.default_roots(extra=None, env=None) == [corpus.DEFAULT_BRAIN]


# -- brain discovery --------------------------------------------------------
#
# The default brain is a sibling of the primary checkout. A clone, a worktree,
# or a scratchpad has no such sibling, so the pack came back empty and the run
# failed outline rubric rows that cannot pass against an empty pack (#308).


def test_the_candidate_list_records_every_place_it_looked():
    rows = corpus.brain_candidates()
    sources = [row["source"] for row in rows]
    assert "sibling of this folder" in sources
    assert all("path" in row and "exists" in row for row in rows)
    assert str(corpus.DEFAULT_BRAIN) in [row["path"] for row in rows]


def test_a_named_brain_is_first_and_is_honored_even_when_absent(tmp_path):
    """A typo the operator can see beats a silent fall back to another corpus."""
    missing = tmp_path / "not-here"
    rows = corpus.brain_candidates(extra=[missing])
    assert rows[0] == {"source": "--brain", "path": str(missing), "exists": False}
    assert corpus.default_roots(extra=[missing]) == [missing]


def test_the_candidate_list_never_invents_a_brain_inside_the_clone(tmp_path):
    before = set(p.name for p in Path(corpus.FOLDER).iterdir())
    corpus.brain_candidates(extra=[tmp_path / "nope"])
    assert set(p.name for p in Path(corpus.FOLDER).iterdir()) == before


def test_a_checkout_with_no_sibling_brain_records_it_and_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "DEFAULT_BRAIN", tmp_path / "absent" / "knowledge")
    monkeypatch.setattr(corpus, "_git_toplevel", lambda start: tmp_path / "clone")
    rows = corpus.brain_candidates()
    assert [row["exists"] for row in rows] == [False, False]
    assert corpus.default_roots() == [corpus.DEFAULT_BRAIN]


def test_a_git_probe_that_fails_is_not_a_crash(monkeypatch):
    monkeypatch.setattr(corpus, "_git_toplevel", lambda start: None)
    assert corpus.brain_candidates()


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
