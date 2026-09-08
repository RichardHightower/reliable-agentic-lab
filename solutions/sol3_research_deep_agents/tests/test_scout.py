"""On a second-brain miss, scout before the outline. #367

Copied from the Agent SDK port, not imported. The briefing is a map, not
research. A fat pack skips. A dead scout is a note.
"""

from __future__ import annotations

import json
from pathlib import Path

import paper
import stages
from conftest import FIXTURES, build_run


def proposal(host, org_type="preprint"):
    return {"host": host, "org_type": org_type}


class ScoutRunner(paper.FixtureRunner):
    def __init__(self, path, payload=None, boom=False):
        super().__init__(path)
        self.payload = payload or {
            "headings": ["Epidemiology", "Treatment"],
            "domains": [proposal("cdc.gov", "government")],
            "titles": ["A flagship"],
        }
        self.boom = boom
        self.asked: list[tuple] = []

    def ask(self, role, prompt):
        if "briefing, not research" in prompt.lower() or (
            role == "researcher" and "Map the field" in prompt
        ):
            self.asked.append((role, prompt))
            if self.boom:
                raise RuntimeError("perplexity is down")
            return paper.Reply(text="", data=self.payload, usd=0.01)
        return super().ask(role, prompt)


def test_stage_order_runs_scout_after_the_pack_and_before_the_plan():
    assert stages.STAGE_ORDER.index("corpus") < stages.STAGE_ORDER.index("scout")
    assert stages.STAGE_ORDER.index("scout") < stages.STAGE_ORDER.index("plan")
    assert stages.STAGE_ORDER.index("scout") < stages.STAGE_ORDER.index("sources")


def test_a_fat_pack_skips_the_scout(run_dir):
    runner = ScoutRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": False, "hits": [{}] * 10}), encoding="utf-8"
    )
    meta = run.stage_scout("")
    assert meta.artifacts["skipped"] is True
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert payload["skipped"] is True
    assert runner.asked == []
    assert "Skipped" in (dest / "scout-briefing.md").read_text()


def test_a_thin_pack_writes_the_briefing(run_dir):
    runner = ScoutRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    meta = run.stage_scout("")
    assert meta.artifacts["skipped"] is False
    assert runner.asked and runner.asked[0][0] == "researcher"
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert "Epidemiology" in payload["headings"]
    assert "cdc.gov" in payload["admitted"]
    # The model proposed a host, so Python does not also force arxiv.org onto
    # a topic it never named. #469
    assert payload["seeded_by_field"] is False
    text = (dest / "scout-briefing.md").read_text()
    assert "This is a map, not evidence" in text


def test_a_dead_scout_does_not_stop_the_run(run_dir):
    runner = ScoutRunner(FIXTURES / "replies.json", boom=True)
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    meta = run.stage_scout("")
    assert meta.artifacts["skipped"] is False
    payload = json.loads((dest / "scout-briefing.json").read_text())
    # A dead scout named no field either. Seeding arxiv.org onto an
    # undetermined field was the same field-blindness this ticket reported,
    # one layer up, so a blank field now seeds nothing. #469
    assert payload["admitted"] == []


def test_an_empty_scout_proposal_seeds_by_field(run_dir):
    """A biomedical topic seeds PubMed and PMC, not arxiv alone. #469"""
    runner = ScoutRunner(
        FIXTURES / "replies.json",
        payload={"headings": ["Epidemiology"], "domains": [], "titles": [], "field": "biomedical"},
    )
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert payload["seeded_by_field"] is True
    assert "pubmed.ncbi.nlm.nih.gov" in payload["admitted"]
    assert "pmc.ncbi.nlm.nih.gov" in payload["admitted"]
    assert payload["admitted"] != ["arxiv.org"]


def test_an_empty_scout_proposal_on_a_software_topic_still_seeds_arxiv(run_dir):
    runner = ScoutRunner(
        FIXTURES / "replies.json",
        payload={"headings": ["APIs"], "domains": [], "titles": [], "field": "software"},
    )
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert payload["admitted"] == ["arxiv.org"]


def test_an_unlisted_field_seeds_doi_org_beside_the_scouts_own_host(run_dir):
    """An economics topic never gets the vendor doc list, and keeps its own
    host beside doi.org. #469"""
    runner = ScoutRunner(
        FIXTURES / "replies.json",
        payload={
            "headings": ["Policy"],
            "domains": [proposal("nber.org", "preprint")],
            "titles": [],
            "field": "economics",
        },
    )
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert "doi.org" in payload["admitted"]
    assert "nber.org" in payload["admitted"]
    assert "docs.langchain.com" not in payload["admitted"]


def test_the_scout_prompt_asks_for_the_field_not_arxiv(run_dir):
    """The prompt stops nudging toward arxiv.org and asks for the field. #469"""
    runner = ScoutRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    prompt = runner.asked[0][1]
    assert "Prefer arxiv.org" not in prompt
    assert "field" in prompt.lower()


def test_the_scout_cannot_admit_an_aggregator(run_dir):
    runner = ScoutRunner(
        FIXTURES / "replies.json",
        payload={
            "headings": ["Background"],
            "domains": [
                proposal("medium.com", "trade_press"),
                proposal("cdc.gov", "government"),
            ],
            "titles": [],
        },
    )
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert "medium.com" not in payload["admitted"]
    assert "cdc.gov" in payload["admitted"]
    assert any(item["host"] == "medium.com" for item in payload["dropped"])


def test_the_planner_sees_the_briefing_on_a_thin_pack(run_dir):
    runner = ScoutRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    asked = []
    original = runner.ask

    def capture(role, prompt):
        asked.append((role, prompt))
        return original(role, prompt)

    runner.ask = capture
    run.stage_plan("")
    planner = next(prompt for role, prompt in asked if role == "planner")
    assert "Epidemiology" in planner
    assert "map of the field" in planner.lower() or "not evidence" in planner.lower()


def test_the_librarian_sees_the_briefing(run_dir):
    runner = ScoutRunner(FIXTURES / "replies.json")
    run = build_run(run_dir, runner=runner)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    run.stage_scout("")
    (Path(run_dir) / "outline.json").write_text(
        json.dumps({"sections": [{"heading": "The problem"}]}), encoding="utf-8"
    )
    asked = []
    original = runner.ask

    def capture(role, prompt):
        asked.append((role, prompt))
        return original(role, prompt)

    runner.ask = capture
    run.stage_sources("")
    librarian = next(prompt for role, prompt in asked if role == "source_librarian")
    assert "The problem" in librarian
    assert "cdc.gov" in librarian or "Epidemiology" in librarian


def test_offline_fixture_scout_is_a_map_not_a_finding(run_dir):
    """The recorded researcher briefing must not look like a claim list."""
    run = build_run(run_dir)
    dest = Path(run_dir) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "brain-pack.json").write_text(
        json.dumps({"corpus_thin": True, "hits": []}), encoding="utf-8"
    )
    meta = run.stage_scout("")
    assert meta.artifacts["skipped"] is False
    payload = json.loads((dest / "scout-briefing.json").read_text())
    assert "Background" in payload["headings"]
    assert "claims" not in payload
    assert payload["admitted"]
