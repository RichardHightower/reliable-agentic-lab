"""The source-admission wall, and the librarian that feeds it.

The provider takes twenty domains for the whole run. The seed list is vendor
documentation, which is right for a paper about those vendors and close to
useless for one about oncology or monetary policy. The librarian proposes this
topic's twenty.

Python admits. A model that could widen its own allowlist would be deciding
what counts as reputable, which is how blogs re-enter the paper (#304).
"""

from __future__ import annotations

import json

import paper
import pytest
import source_policy as sp


def proposal(host, org_type, why="because"):
    return {"host": host, "org_type": org_type, "why": why}


def admitted(*items):
    return sp.admit(list(items))["admitted"]


def why_dropped(host, org_type):
    dropped = sp.admit([proposal(host, org_type)])["dropped"]
    return dropped[0]["why"] if dropped else ""


# -- what the wall admits ---------------------------------------------------


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


# -- what the wall refuses --------------------------------------------------


def test_an_aggregator_is_dropped_whatever_it_claims():
    for org_type in ("trade_press", "vendor_docs", "university"):
        assert why_dropped("medium.com", org_type) == "on the denylist"


def test_wikipedia_is_dropped_under_every_type():
    """Fine for designing a publisher map. Not a thing the paper may cite."""
    assert why_dropped("en.wikipedia.org", "university") == "on the denylist"
    assert why_dropped("wikipedia.org", "professional_society") == "on the denylist"


def test_cable_news_cannot_relabel_itself_in():
    """`cable_news` is not in the enum, so the only way in is a false type.

    On a timely query cable news outranks the journals. The news-shaped analog
    of a primary source is a wire service.
    """
    assert why_dropped("cnn.com", "wire_service") == "on the denylist"
    assert why_dropped("cnn.com", "trade_press") == "on the denylist"


def test_a_real_wire_service_is_kept():
    assert admitted(proposal("reuters.com", "wire_service")) == ["reuters.com"]


def test_the_org_tld_is_never_admitted():
    """arXiv and the ACM are `.org`. So is every content mill. Name the hosts."""
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


# -- the cap and the order --------------------------------------------------


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


# -- the fallback -----------------------------------------------------------


def test_too_few_admitted_keeps_the_seed():
    """A librarian that admits two hosts is worse than no librarian."""
    assert sp.run_allowlist(["a.gov", "b.gov"]) == sp.SEED_ALLOWLIST
    assert sp.run_allowlist([]) == sp.SEED_ALLOWLIST


def test_enough_admitted_replaces_the_seed():
    hosts = ["a.gov", "b.gov", "c.gov"]
    assert sp.run_allowlist(hosts) == tuple(hosts)


# -- the phase --------------------------------------------------------------


class LibrarianTurns:
    """A `Turns` that answers the librarian and records what it was asked."""

    def __init__(self, domains, boom=False):
        self.domains = domains
        self.boom = boom
        self.asked: list[tuple] = []
        self.allowed_domains = sp.SEED_ALLOWLIST

    def source_allowlist(self, topic, headings, prior_art=""):
        self.asked.append((topic, headings, prior_art))
        if self.boom:
            raise RuntimeError("the librarian is unavailable")
        return {"domains": self.domains}


def run_for(work, turns):
    approved = {
        "outline": {
            "title": "A paper",
            "sections": [{"id": "s1", "heading": "The problem"}],
        }
    }
    run = paper.Run(topic="a topic", work_dir=work, turns=turns, state=paper.State())
    run.write_json("outline.approved.json", approved)
    return run


def test_the_phase_writes_the_artifact(work):
    turns = LibrarianTurns(
        [proposal("arxiv.org", "preprint"), proposal(".gov", "government"),
         proposal("medium.com", "trade_press"), proposal("nature.com", "peer_reviewed_publisher")]
    )
    run = run_for(work, turns)
    meta = paper.source_allowlist(run)

    recorded = json.loads((work / "corpus" / "source_allowlist.json").read_text())
    assert recorded["admitted"] == [".gov", "nature.com", "arxiv.org"]
    assert any(item["host"] == "medium.com" for item in recorded["dropped"])
    assert recorded["proposed"] and meta["dropped"] == 1
    assert meta["seed"] is False


def test_the_phase_hands_the_list_to_the_turns(work):
    """Setting it on the Run alone would leave every search on the seed."""
    turns = LibrarianTurns(
        [proposal("arxiv.org", "preprint"), proposal(".gov", "government"),
         proposal("nature.com", "peer_reviewed_publisher")]
    )
    run = run_for(work, turns)
    paper.source_allowlist(run)
    assert turns.allowed_domains == (".gov", "nature.com", "arxiv.org")
    assert run.allowed_domains == turns.allowed_domains


def test_the_librarian_sees_the_topic_and_the_headings(work):
    turns = LibrarianTurns([])
    run = run_for(work, turns)
    paper.source_allowlist(run)
    topic, headings, _prior = turns.asked[0]
    assert topic == "a topic"
    assert headings == ["The problem"]


def test_a_dead_librarian_falls_back_to_the_seed(work):
    """A failure here is a note, never a stop."""
    turns = LibrarianTurns([], boom=True)
    run = run_for(work, turns)
    meta = paper.source_allowlist(run)
    assert meta["seed"] is True
    assert run.allowed_domains == sp.SEED_ALLOWLIST
    assert (work / "corpus" / "source_allowlist.json").exists()


def test_a_turns_with_no_librarian_still_runs(work):
    class Plain:
        pass

    run = run_for(work, Plain())
    meta = paper.source_allowlist(run)
    assert meta["admitted"] == 0
    assert run.allowed_domains == sp.SEED_ALLOWLIST


# -- the post-filter uses the run's list ------------------------------------


def test_the_post_filter_rejects_a_host_the_run_did_not_admit():
    """The provider filter is advisory. A redirect can escape a domain."""
    admitted_hosts = ("arxiv.org",)
    assert sp.is_allowed_url("https://arxiv.org/abs/1", allowed_domains=admitted_hosts)
    assert not sp.is_allowed_url("https://medium.com/p/1", allowed_domains=admitted_hosts)
    assert not sp.is_allowed_url("https://docs.langchain.com/x", allowed_domains=admitted_hosts)


def test_scout_cannot_add_an_aggregator():
    merged = sp.merge_scout_domains(["https://medium.com/p/1"], seed=("arxiv.org",))
    assert "medium.com" not in merged


def test_the_librarian_holds_no_search_tool_and_no_write_path():
    """Searching to decide where to search would let its first results choose."""
    import roleplan  # noqa: PLC0415

    role = roleplan.plan(None, "research")["source_librarian"]
    assert not role.can_write
    for forbidden in ("WebSearch", "Bash", "Write", "Edit"):
        assert forbidden not in role.tools
