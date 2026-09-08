"""`corpus.pack`'s relevance floor: count is not relevance. #405

`corpus.search` ranks by distinct query terms and returns any claim that
matches at least one of them. A brain of a few hundred claims will match one
term of almost any topic, so a large brain used to read as "thick" on a
topic it has nothing to do with, and the scout skipped the map it should
have run. `pack` now only counts a hit toward "thick" once its `score`
clears `_relevance_floor`, and it records how many cleared it as `relevant`
in `brain-pack.json`.
"""

from __future__ import annotations

from pathlib import Path

import corpus
import paper
import pytest
import research
from conftest import FIXTURES

CREATINE_TOPIC = "Creatine supplementation for preventing muscle loss during a calorie deficit"
LOOP_TOPIC = "loop engineering exit criteria"


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    corpus.clear_cache()
    yield
    corpus.clear_cache()


def _claim(root: Path, claim_id: str, text: str, confidence: float = 0.9) -> None:
    claims = root / "research" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / f"claim.{claim_id}.md").write_text(
        f'---\ntype: "Claim"\nid: "claim.{claim_id}"\n'
        f'description: "{text}"\nconfidence: {confidence}\n---\n\n# Claim\n\n{text}\n',
        encoding="utf-8",
    )


def _fifty_loop_engineering_claims(root: Path) -> Path:
    """Fifty claims about loop engineering. None mention creatine.

    Ten say "loss" once (token loss on a stalled retry) and ten say "during"
    once (a retry storm during a run): plain English a real second brain
    picks up by accident. Each of those twenty also carries "loop" and
    "exit", so it scores two proper terms on the loop-engineering topic
    (clears the floor) but only one term on the creatine topic (does not).
    The other thirty are filler and match neither topic.
    """
    for i in range(10):
        _claim(
            root,
            f"loss-{i}",
            f"A stalled retry loop {i} must exit before token loss becomes unbounded.",
        )
    for i in range(10):
        _claim(
            root,
            f"during-{i}",
            f"During a retry storm {i}, the loop must exit before the queue backs up.",
        )
    for i in range(30):
        _claim(
            root,
            f"filler-{i}",
            f"A judge verdict {i} names blocking issues by rule and detail.",
        )
    return root


@pytest.fixture
def loop_brain(tmp_path):
    return _fifty_loop_engineering_claims(tmp_path / "loop-brain")


def _build_paper(work_dir: Path, topic: str, brains: list[Path]) -> paper.Paper:
    return paper.Paper(
        topic=topic,
        runner=paper.FixtureRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=work_dir,
        quiet=True,
        brains=brains,
    )


# -- the floor itself --------------------------------------------------------


def test_relevance_floor_is_two_terms_at_four_or_more():
    assert corpus._relevance_floor(4) == 2
    assert corpus._relevance_floor(8) == 2


def test_relevance_floor_is_half_the_terms_below_four():
    assert corpus._relevance_floor(1) == 0.5
    assert corpus._relevance_floor(2) == 1
    assert corpus._relevance_floor(3) == 1.5


# -- pack: thin on noise, thick on its own subject ---------------------------


def test_a_fifty_claim_brain_packs_thin_on_an_unrelated_topic(loop_brain, tmp_path):
    assert len(corpus.claim_files(loop_brain)) == 50

    packed = corpus.pack(CREATINE_TOPIC, [loop_brain], tmp_path / "pack")

    assert len(packed["hits"]) == 20, "loss and during are one-term noise, twenty of them"
    assert packed["relevant"] == 0, "none of the twenty carry a second creatine term"
    assert packed["corpus_thin"] is True

    js = corpus.json.loads((tmp_path / "pack" / "brain-pack.json").read_text(encoding="utf-8"))
    assert js["relevant"] == 0
    assert js["corpus_thin"] is True


def test_the_same_brain_packs_thick_on_its_own_topic(loop_brain, tmp_path):
    packed = corpus.pack(LOOP_TOPIC, [loop_brain], tmp_path / "pack")

    assert packed["relevant"] == 20, "loop plus exit is two real terms on all twenty"
    assert packed["corpus_thin"] is False


def test_a_two_term_topic_uses_the_half_of_terms_floor(tmp_path):
    """Below four terms, one shared term is enough: half of two is one."""
    root = tmp_path / "brain"
    for i in range(10):
        _claim(root, f"queue-{i}", f"The queue backs up {i} without a retry budget.")

    packed = corpus.pack("queue budget", [root], tmp_path / "pack")

    assert packed["relevant"] == 10, "score 1 clears a floor of 1 (half of two terms)"
    assert packed["corpus_thin"] is False


# -- the log line: hits, relevant, thin --------------------------------------


def test_stage_corpus_summary_names_the_relevant_count(loop_brain, tmp_path):
    run = _build_paper(tmp_path / "run", CREATINE_TOPIC, [loop_brain])

    result = run.stage_corpus("")

    # Substrings, not the exact string: `relevant` is now a hard index into
    # what `corpus.pack` returns, and pinning the whole sentence made every
    # future word choice here a fixture break for no reason.
    assert "hits" in result.summary
    assert "relevant" in result.summary
    assert "thin" in result.summary


# -- the scout: runs on thin, skips on thick ---------------------------------


def test_the_scout_runs_on_the_thin_pack_and_skips_on_the_thick_pack(loop_brain, tmp_path):
    thin_run = _build_paper(tmp_path / "thin", CREATINE_TOPIC, [loop_brain])
    thin_run.stage_corpus("")
    thin_meta = thin_run.stage_scout("")
    assert thin_meta.artifacts["skipped"] is False

    thick_run = _build_paper(tmp_path / "thick", LOOP_TOPIC, [loop_brain])
    thick_run.stage_corpus("")
    thick_meta = thick_run.stage_scout("")
    assert thick_meta.artifacts["skipped"] is True
