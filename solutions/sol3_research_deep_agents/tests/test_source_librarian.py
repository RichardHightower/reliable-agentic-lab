"""The source-admission wall, and the librarian that feeds it.

Copied from the Agent SDK port, not imported. Python admits. A model that
could widen its own allowlist would be deciding what counts as reputable,
which is how blogs re-enter the paper (#304).
"""

from __future__ import annotations

import json
from pathlib import Path

import paper
import source_policy as sp
from conftest import FIXTURES, build_run


def proposal(host, org_type, why="because"):
    return {"host": host, "org_type": org_type, "why": why}


def admitted(*items):
    return sp.admit(list(items))["admitted"]


def why_dropped(host, org_type):
    dropped = sp.admit([proposal(host, org_type)])["dropped"]
    return dropped[0]["why"] if dropped else ""


def test_a_preprint_host_is_kept():
    assert admitted(proposal("arxiv.org", "preprint")) == ["arxiv.org"]


def test_a_government_tld_is_kept_as_a_tld():
    assert admitted(proposal(".gov", "government")) == [".gov"]


def test_named_trade_press_is_kept():
    assert admitted(proposal("infoworld.com", "trade_press")) == ["infoworld.com"]


def test_a_url_is_reduced_to_its_host():
    assert admitted(proposal("https://arxiv.org/list/cs.AI", "preprint")) == ["arxiv.org"]


def test_a_wildcard_and_a_www_prefix_are_stripped():
    assert admitted(proposal("*.nature.com", "peer_reviewed_publisher")) == ["nature.com"]
    assert admitted(proposal("www.acm.org", "professional_society")) == ["acm.org"]


def test_an_aggregator_is_dropped_whatever_it_claims():
    for org_type in ("trade_press", "vendor_docs", "university"):
        assert why_dropped("medium.com", org_type) == "on the denylist"


def test_wikipedia_is_dropped_under_every_type():
    assert why_dropped("en.wikipedia.org", "university") == "on the denylist"
    assert why_dropped("wikipedia.org", "professional_society") == "on the denylist"


def test_cable_news_cannot_relabel_itself_in():
    assert why_dropped("cnn.com", "wire_service") == "on the denylist"
    assert why_dropped("cnn.com", "trade_press") == "on the denylist"


def test_a_real_wire_service_is_kept():
    assert admitted(proposal("reuters.com", "wire_service")) == ["reuters.com"]


def test_the_org_tld_is_never_admitted():
    assert "not an admitted top level domain" in why_dropped(".org", "peer_reviewed_publisher")
    assert admitted(proposal("arxiv.org", "preprint")) == ["arxiv.org"]


def test_an_invented_org_type_is_dropped():
    assert "is not one of" in why_dropped("example.com", "blog")
    assert "is not one of" in why_dropped("example.com", "cable_news")
    assert "is not one of" in why_dropped("example.com", "encyclopedia")


def test_a_bare_word_is_not_a_host():
    assert why_dropped("science", "peer_reviewed_publisher") != ""


def test_a_duplicate_takes_one_slot():
    kept = admitted(
        proposal("arxiv.org", "preprint"),
        proposal("https://arxiv.org", "preprint"),
    )
    assert kept == ["arxiv.org"]


def test_the_cap_holds_at_twenty():
    kept = sp.admit([proposal(f"h{index}.gov", "government") for index in range(25)])
    assert len(kept["admitted"]) == 20
    assert any("over the cap" in item["why"] for item in kept["dropped"])


def test_a_specification_outranks_trade_press_for_the_last_slot():
    kept = sp.admit(
        [proposal("infoworld.com", "trade_press"), proposal("w3.org", "standards_body")],
        cap=1,
    )
    assert kept["admitted"] == ["w3.org"]


def test_the_same_proposal_admits_the_same_order():
    items = [
        proposal("infoworld.com", "trade_press"),
        proposal("arxiv.org", "preprint"),
        proposal(".gov", "government"),
    ]
    assert sp.admit(items)["admitted"] == sp.admit(list(reversed(items)))["admitted"]


def test_too_few_admitted_keeps_the_seed():
    assert sp.run_allowlist(["a.gov", "b.gov"]) == sp.SEED_ALLOWLIST
    assert sp.run_allowlist([]) == sp.SEED_ALLOWLIST


def test_enough_admitted_replaces_the_seed():
    hosts = ["a.gov", "b.gov", "c.gov"]
    assert sp.run_allowlist(hosts) == tuple(hosts)


class LibrarianRunner(paper.FixtureRunner):
    def __init__(self, path, domains=None, boom=False):
        super().__init__(path)
        self.domains = domains or []
        self.boom = boom
        self.asked: list[tuple] = []

    def ask(self, role, prompt):
        if role != "source_librarian":
            return super().ask(role, prompt)
        self.asked.append((role, prompt))
        if self.boom:
            raise RuntimeError("the librarian is unavailable")
        return paper.Reply(text="", data={"domains": self.domains}, usd=0.01)


def test_the_phase_writes_the_artifact(run_dir, stub_renderer):
    runner = LibrarianRunner(
        FIXTURES / "replies.json",
        [
            proposal("arxiv.org", "preprint"),
            proposal(".gov", "government"),
            proposal("medium.com", "trade_press"),
            proposal("nature.com", "peer_reviewed_publisher"),
        ],
    )
    run = build_run(run_dir, runner=runner)
    (Path(run_dir) / "outline.json").write_text(
        json.dumps({"sections": [{"heading": "The problem"}]}), encoding="utf-8"
    )
    meta = run.stage_sources("")

    recorded = json.loads((Path(run_dir) / "corpus" / "source_allowlist.json").read_text())
    assert recorded["admitted"] == [".gov", "nature.com", "arxiv.org"]
    assert any(item["host"] == "medium.com" for item in recorded["dropped"])
    assert recorded["proposed"] and meta.artifacts["dropped"] == 1
    assert meta.artifacts["seed"] is False
    assert run.allowed_domains == (".gov", "nature.com", "arxiv.org")
    assert run.backend.allowlist == run.allowed_domains


def test_the_librarian_sees_the_topic_and_the_headings(run_dir, stub_renderer):
    runner = LibrarianRunner(FIXTURES / "replies.json", [])
    run = build_run(run_dir, runner=runner)
    (Path(run_dir) / "outline.json").write_text(
        json.dumps({"sections": [{"heading": "The problem"}]}), encoding="utf-8"
    )
    run.stage_sources("")
    _role, prompt = runner.asked[0]
    assert "Exit conditions" in prompt or "a topic" in prompt.lower() or run.topic in prompt
    assert "The problem" in prompt


def test_a_dead_librarian_falls_back_to_the_seed(run_dir, stub_renderer):
    runner = LibrarianRunner(FIXTURES / "replies.json", boom=True)
    run = build_run(run_dir, runner=runner)
    meta = run.stage_sources("")
    assert meta.artifacts["seed"] is True
    assert run.allowed_domains == sp.SEED_ALLOWLIST
    assert (Path(run_dir) / "corpus" / "source_allowlist.json").exists()


def test_offline_fixture_never_requires_a_live_librarian(run_dir, stub_renderer):
    """No recorded librarian reply. The phase keeps the seed and proceeds."""
    run = build_run(run_dir)
    meta = run.stage_sources("")
    assert meta.artifacts["seed"] is True
    assert run.allowed_domains == sp.SEED_ALLOWLIST


def test_the_post_filter_rejects_a_host_the_run_did_not_admit():
    admitted_hosts = ("arxiv.org",)
    assert sp.url_allowed("https://arxiv.org/abs/1", admitted_hosts)
    assert not sp.url_allowed("https://medium.com/p/1", admitted_hosts)
    assert not sp.url_allowed("https://docs.langchain.com/x", admitted_hosts)


def test_a_gov_tld_admits_an_agency_host():
    assert sp.url_allowed("https://nist.gov/x", (".gov",))
    assert sp.url_allowed("https://www.cdc.gov/x", (".gov",))
    assert not sp.url_allowed("https://example.com/x", (".gov",))


def test_scout_cannot_add_an_aggregator():
    merged = sp.merge_allowlist(["https://medium.com/p/1"], seed=("arxiv.org",))
    assert "medium.com" not in merged


def test_the_librarian_holds_no_write_path():
    import roleplan  # noqa: PLC0415

    librarian = roleplan.plan(None, "paper")["source_librarian"]
    assert not librarian.can_write
    assert "Write" not in librarian.tools and "WebSearch" not in librarian.tools
