"""On a second-brain miss, scout before the outline. #367

The briefing is a map, not research. A fat pack skips. A dead scout is a note.
"""

from __future__ import annotations

import json
from pathlib import Path

import paper
import turns as turns_mod


def make_run(work, turns, **kwargs):
    kwargs.setdefault("brain", None)
    kwargs.setdefault("log", lambda *a: None)
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns,
        state=paper.State.load_or_new(work, "a topic"),
        **kwargs,
    )


def proposal(host, org_type="preprint"):
    return {"host": host, "org_type": org_type}


class ScoutTurns:
    """Answers the scout and records what it was asked."""

    def __init__(self, payload=None, boom=False):
        self.payload = payload or {
            "headings": ["Epidemiology", "Treatment"],
            "domains": [proposal("cdc.gov", "government")],
            "titles": ["A flagship"],
        }
        self.boom = boom
        self.asked = []

    def scout(self, topic):
        self.asked.append(("scout", topic))
        if self.boom:
            raise RuntimeError("perplexity is down")
        return self.payload

    def outline(self, topic, prior_art, budget=None, note="", brief=""):
        self.asked.append(("outline", topic, prior_art, budget, note, brief))
        words = int((budget or {}).get("words") or 400)
        return {
            "title": f"On {topic}",
            "audience": "engineers",
            "thesis": "An abstract.",
            "word_target_total": words,
            "sections": [
                {
                    "id": "s1",
                    "heading": "The problem",
                    "objective": "State it.",
                    "abstract": "This section states the problem.",
                    "key_questions": [f"what is {topic}", f"why does {topic} fail"],
                    "claims_to_support": ["The problem is structural."],
                    "required_evidence": ["a primary specification"],
                    "word_target": words,
                    "figures": [],
                    "depends_on": [],
                }
            ],
        }

    def plan(self, topic, prior_art, budget=None, note="", brief=""):
        return self.outline(topic, prior_art, budget, note, brief)

    def judge_outline(self, drafted, note=""):
        return {
            "passed": True,
            "score": 1.0,
            "blocking_issues": [],
            "actionable_changes": [],
        }

    def source_allowlist(self, topic, headings, prior_art=""):
        self.asked.append(("sources", topic, headings, prior_art))
        return {"domains": [proposal("nature.com", "peer_reviewed_publisher")]}


class _FakeResult:
    ok = True
    stop_reason = None
    structured = {"headings": [], "domains": []}
    output = "{}"


class _FakeBackend:
    def __init__(self):
        self.prompts: list[str] = []

    def run(self, root, prompt, allow, output_format, role):
        self.prompts.append(prompt)
        return _FakeResult()


def test_the_scout_schema_and_prompt_ask_for_the_field(tmp_path):
    """The schema and the prompt both carry `field`. #469"""
    assert "field" in turns_mod.SCOUT_SCHEMA["properties"]
    backend = _FakeBackend()
    turns = turns_mod.SdkTurns(backend=backend, work_dir=tmp_path)
    turns.scout("a topic")
    prompt = backend.prompts[0]
    assert "field" in prompt.lower()
    assert "prefer arxiv.org" not in prompt.lower()


def test_linear_runs_scout_after_the_pack_and_before_the_outline():
    names = [name for _n, name, _out, _fn in paper.LINEAR]
    assert names.index("corpus_pack") < names.index("scout")
    assert names.index("scout") < names.index("outline")
    assert names.index("scout") < names.index("sources")


def test_a_fat_pack_skips_the_scout(work):
    turns = ScoutTurns()
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": False, "hits": [{}] * 10})
    meta = paper.scout(run)
    assert meta["skipped"] is True
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["skipped"] is True
    assert payload["reason"] == "pack is thick"
    assert turns.asked == []
    text = (work / "corpus" / "scout-briefing.md").read_text()
    assert "Skipped" in text


def test_a_thin_pack_writes_the_briefing(work):
    turns = ScoutTurns()
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    meta = paper.scout(run)
    assert meta["skipped"] is False
    assert turns.asked == [("scout", "a topic")]
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["skipped"] is False
    assert "Epidemiology" in payload["headings"]
    assert "cdc.gov" in payload["admitted"]
    # The model proposed a host, so Python does not also force arxiv.org onto
    # a topic it never named. #469
    assert payload["seeded_by_field"] is False
    text = (work / "corpus" / "scout-briefing.md").read_text()
    assert "This is a map, not evidence" in text
    assert "Epidemiology" in text


def test_a_dead_scout_does_not_stop_the_run(work):
    """A failure here is a note, never a stop. Same spirit as the librarian."""
    turns = ScoutTurns(boom=True)
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    meta = paper.scout(run)
    assert meta["skipped"] is False
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["admitted"] == ["arxiv.org"]
    assert (work / "corpus" / "scout-briefing.md").exists()


def test_an_empty_scout_proposal_seeds_by_field(work):
    """A biomedical topic seeds PubMed and PMC, not arxiv alone. #469"""
    turns = ScoutTurns(
        {"headings": ["Epidemiology"], "domains": [], "titles": [], "field": "biomedical"}
    )
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    paper.scout(run)
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["seeded_by_field"] is True
    assert "pubmed.ncbi.nlm.nih.gov" in payload["admitted"]
    assert "pmc.ncbi.nlm.nih.gov" in payload["admitted"]
    assert payload["admitted"] != ["arxiv.org"]


def test_an_empty_scout_proposal_on_a_software_topic_still_seeds_arxiv(work):
    turns = ScoutTurns({"headings": ["APIs"], "domains": [], "titles": [], "field": "software"})
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    paper.scout(run)
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["admitted"] == ["arxiv.org"]


def test_the_scout_cannot_admit_an_aggregator(work):
    turns = ScoutTurns(
        {
            "headings": ["Background"],
            "domains": [
                proposal("medium.com", "trade_press"),
                proposal("cdc.gov", "government"),
            ],
            "titles": [],
        }
    )
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    paper.scout(run)
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert "medium.com" not in payload["admitted"]
    assert "cdc.gov" in payload["admitted"]
    assert any(item["host"] == "medium.com" for item in payload["dropped"])


def test_a_skipped_briefing_is_not_fed_to_the_outliner(work):
    turns = ScoutTurns()
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": False, "hits": [{}] * 10})
    (work / "corpus" / "brain-pack.md").write_text("# Pack\n\nTen hits.\n", encoding="utf-8")
    paper.scout(run)
    paper.do_outline(run)
    asked = next(item for item in turns.asked if item[0] == "outline")
    prior = asked[2]
    assert "Ten hits" in prior
    assert "Epidemiology" not in prior
    assert "Skipped" not in prior


def test_the_outliner_sees_the_briefing_on_a_thin_pack(work):
    turns = ScoutTurns()
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    (work / "corpus" / "brain-pack.md").write_text("# Pack\n\nNo second brain.\n", encoding="utf-8")
    paper.scout(run)
    paper.do_outline(run)
    asked = next(item for item in turns.asked if item[0] == "outline")
    prior = asked[2]
    assert "Epidemiology" in prior
    assert "This is a map, not evidence" in prior
    assert "No second brain" in prior


def test_the_librarian_sees_the_briefing(work):
    turns = ScoutTurns()
    run = make_run(work, turns)
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    paper.scout(run)
    run.write_json(
        "outline.approved.json",
        {"outline": {"title": "A paper", "sections": [{"id": "s1", "heading": "The problem"}]}},
    )
    paper.source_allowlist(run)
    asked = next(item for item in turns.asked if item[0] == "sources")
    _topic, headings, prior = asked[1], asked[2], asked[3]
    assert headings == ["The problem"]
    assert "cdc.gov" in prior or "Epidemiology" in prior


def test_a_turns_with_no_scout_still_writes_the_briefing(work):
    class Plain:
        pass

    run = make_run(work, Plain())
    run.write_json("corpus/brain-pack.json", {"corpus_thin": True, "hits": []})
    meta = paper.scout(run)
    assert meta["skipped"] is False
    payload = json.loads((work / "corpus" / "scout-briefing.json").read_text())
    assert payload["admitted"] == ["arxiv.org"]
