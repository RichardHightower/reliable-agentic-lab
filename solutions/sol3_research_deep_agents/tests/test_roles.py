"""Tool lists, path checks, and the harness fence. All three layers, no SDK."""

from __future__ import annotations

from pathlib import Path

import pathlib

import roles


def names(spec):
    return sorted(getattr(tool, "name", getattr(tool, "__name__", "?")) for tool in spec["tools"])


def by_name(specs):
    return {spec["name"]: spec for spec in specs}


class Boundary:
    """A stand-in for a research backend. Records what it was asked."""

    name = "stub"
    cost_per_call = 0.0

    def __init__(self, answer="an answer", citations=("https://a.example",), note=""):
        self.asked = []
        self._answer = answer
        self._citations = list(citations)
        self._note = note

    def search(self, question):
        import research  # noqa: PLC0415  (sys.path is set by conftest first)

        self.asked.append(question)
        return research.Finding(
            question=question,
            answer=self._answer,
            citations=self._citations,
            backend=self.name,
            note=self._note,
        )


def test_reviewer_holds_no_custom_tools(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", repo=Path(".")))["reviewer"]
    assert names(spec) == []


def test_only_the_researcher_gets_search(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", backend=Boundary(), repo=Path(".")))
    assert "search" in names(specs["researcher"])
    for role in ("planner", "diagrammer", "writer", "reviewer", "outline-judge", "outline-editor", "section-judge", "ledger", "chartist", "source-librarian"):
        assert "search" not in names(specs[role]), role


def test_researcher_must_return_a_structured_evidence_report(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", backend=Boundary(), repo=Path(".")))[
        "researcher"
    ]
    assert spec["response_format"]["required"] == ["answer", "sources", "claims"]
    source = spec["response_format"]["properties"]["sources"]["items"]
    assert source["required"] == ["title", "url", "vendor", "quote"]


def test_only_the_verifier_gets_docs(fake_langchain):
    specs = by_name(
        roles.subagents_for(
            None, "paper", backend=Boundary(), docs_backend=Boundary(), repo=Path(".")
        )
    )
    assert "check_docs" in names(specs["verifier"])
    for role in ("researcher", "planner", "writer", "reviewer", "diagrammer", "outline-judge", "section-judge", "ledger", "chartist", "source-librarian"):
        assert "check_docs" not in names(specs[role]), role


def test_only_the_planner_gets_the_brain(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", repo=Path(".")))
    assert "recall" in names(specs["planner"])
    for role in ("researcher", "verifier", "writer", "reviewer", "diagrammer", "outline-judge", "section-judge", "ledger", "chartist", "source-librarian"):
        assert "recall" not in names(specs[role]), role


def test_researcher_and_verifier_hold_corpus_search(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", repo=Path(".")))
    assert "corpus_search" in names(specs["researcher"])
    assert "corpus_search" in names(specs["verifier"])
    for role in ("planner", "writer", "reviewer", "diagrammer", "outline-judge", "section-judge", "ledger", "chartist", "source-librarian"):
        assert "corpus_search" not in names(specs[role]), role


def test_write_tool_refuses_out_of_scope(fake_langchain, tmp_path):
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    role = roleplan.plan(None, "paper")["writer"]
    write = roles.scoped_write_tool(tmp_path, role)
    assert write("paper/body.md", "ok").startswith("wrote")
    refusal = write("evidence/claim.x.md", "forged")
    assert refusal.startswith("REFUSED")
    assert not (tmp_path / "evidence" / "claim.x.md").exists()


def test_write_tool_refusal_names_the_scope(fake_langchain, tmp_path):
    """A refusal that names the scope changes the next action. A raw traceback
    starts a retry loop."""
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    role = roleplan.plan(None, "paper")["verifier"]
    refusal = roles.scoped_write_tool(tmp_path, role)("paper/body.md", "x")
    assert "evidence/**" in refusal
    assert "paper/body.md" in refusal


def test_search_tool_reports_an_empty_answer(fake_langchain):
    """An empty answer must not read like a successful one. A loop that cannot
    tell the difference cites nothing and says nothing."""
    tool = roles.search_tool(Boundary(answer="", citations=(), note="no key"))
    assert tool("anything").startswith("NO ANSWER")


def test_search_tool_stops_a_second_provider_call_in_one_request(fake_langchain):
    import research  # noqa: PLC0415  (sys.path is set by conftest first)

    boundary = Boundary()
    budget = research.Budget(max_calls=4, max_usd=1)
    budget.begin_request(max_calls=1)
    tool = roles.search_tool(boundary, budget)

    assert "CITATIONS:" in tool("first")
    assert tool("second").startswith("NO ANSWER. request search budget")
    assert boundary.asked == ["first"]


def test_recall_is_honest_when_there_is_no_brain(fake_langchain):
    assert roles.second_brain_tool(None)("loops").startswith("NO BRAIN")


def test_recall_finds_prior_research(fake_langchain, tmp_path):
    (tmp_path / "area.md").write_text("# Loop Engineering\nexit conditions matter\n")
    out = roles.second_brain_tool(tmp_path)("exit conditions")
    assert "area.md" in out


def test_recall_answers_a_question_not_just_a_keyword(fake_langchain, tmp_path):
    """The planner asks questions. A literal phrase match never matches one.

    `recall("agent loop exit conditions")` returned nothing against a brain
    where `corpus.search` on the same root returned 40 hits. The planner then
    reported no brain and planned around a corpus the run had already packed,
    and the outline judge rejected the contradiction three times (#322).
    """
    (tmp_path / "area.md").write_text(
        "# Loop Engineering\nA loop checks its exit conditions in order.\n"
    )
    out = roles.second_brain_tool(tmp_path)("what are the loop exit conditions")
    assert "area.md" in out, out
    assert not out.startswith("no prior research")


def test_recall_prefers_the_curated_claims(fake_langchain, tmp_path):
    """A claim carries a key, a quote, and a source. A grep line carries none."""
    import corpus  # noqa: PLC0415

    brain = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "brain"
    query = "exit conditions"
    assert corpus.search(query, [brain], limit=12), "the fixture brain must have claims"
    out = roles.second_brain_tool(brain)(query)
    assert ":claim." in out, out
    assert "[source_supported]" in out, "a claim carries its epistemic state"


def test_recall_still_says_so_when_nothing_matches(fake_langchain, tmp_path):
    (tmp_path / "area.md").write_text("# Unrelated\nnothing to see\n")
    out = roles.second_brain_tool(tmp_path)("quantum tunnelling in badgers")
    assert out.startswith("no prior research mentions")


def test_recall_does_not_match_on_one_common_word(fake_langchain, tmp_path):
    """Every term must appear. An any-term match returns the word "the"."""
    (tmp_path / "area.md").write_text("# Notes\nthe loop is fine\n")
    assert roles.second_brain_tool(tmp_path)("the badger loop").startswith("no prior research")


def test_permissions_deny_a_reader_everything():
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    rules = roles.permission_rules(roleplan.plan(None, "paper")["reviewer"])
    assert rules == [{"operations": ["write"], "paths": ["/**"], "mode": "deny"}]


def test_permissions_put_deny_before_allow():
    """First match wins, so a role's deny list must come first or its allow
    list silently wins on an overlap."""
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    rules = roles.permission_rules(roleplan.plan(None, "paper")["writer"])
    assert rules[0]["mode"] == "deny"
    assert "/evidence/**" in rules[0]["paths"]
    assert rules[1]["mode"] == "allow"
    assert rules[-1] == {"operations": ["write"], "paths": ["/**"], "mode": "deny"}


def test_verifier_response_cannot_state_a_truth_state():
    """The model reports what it found. Python counts sources and decides."""
    props = roles.VERIFIER_RESPONSE["properties"]["checked"]["items"]["properties"]
    assert set(props) == {"claim_id", "second_source_url", "corroborate_status", "quote"}
    assert "truth_state" not in props
    assert props["corroborate_status"]["enum"] == ["agreed", "disagreed", "not_found"]


def test_reviewer_response_cannot_state_a_verdict():
    props = roles.REVIEWER_RESPONSE["properties"]
    assert set(props) == {"failed_rows", "notes", "score"}
    assert "ship" not in props and "verdict" not in props


def test_paper_writer_gets_its_skill_inline_and_cannot_browse_the_run(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", repo=Path(".")))["writer"]
    body = (roles.SKILLS_DIR / "writer" / "SKILL.md").read_text(encoding="utf-8")
    assert "technical white paper" in body.lower()
    assert "technical white paper" in spec["system_prompt"].lower()
    assert "do not read, list, search" in spec["system_prompt"].lower()
    assert "skills" not in spec
    assert names(spec) == []
    assert spec["permissions"] == [
        {"operations": ["read", "write"], "paths": ["/**"], "mode": "deny"}
    ]


def test_build_agent_fences_the_harness(fake_langchain, fake_deepagents, tmp_path):
    """Layer three. Without this, the default general-purpose subagent walks
    around every tool list above it."""
    roles.build_agent(None, loop="paper", repo=tmp_path)

    profile = fake_deepagents["harness_profile"]
    assert profile.general_purpose_subagent.enabled is False
    assert "write_file" in profile.excluded_tools
    assert "execute" in profile.excluded_tools

    assert fake_deepagents["backend"].default.virtual_mode is True
    assert set(fake_deepagents["backend"].routes) == {"/skills/", "/memory/"}

    orchestrator = fake_deepagents["permissions"]
    assert [rule.mode for rule in orchestrator] == ["deny"]


def test_build_agent_passes_every_subagent_permission(fake_langchain, fake_deepagents, tmp_path):
    roles.build_agent(None, loop="paper", repo=tmp_path)
    for spec in fake_deepagents["subagents"]:
        assert spec["permissions"], spec["name"]
        assert spec["permissions"][-1].mode == "deny"
        for permission in spec["permissions"]:
            assert all(path.startswith("/") for path in permission.paths)


def test_outline_max_tokens_is_wider_than_the_shared_graph_ceiling():
    """#407: the recorded truncation happened inside `GRAPH_MAX_TOKENS`. The
    outline-emitting roles need more room than that shared default."""
    assert roles.OUTLINE_MAX_TOKENS > roles.GRAPH_MAX_TOKENS


def test_build_agent_binds_the_bounded_model_to_writer_only(
    fake_langchain, fake_deepagents, tmp_path, monkeypatch
):
    graph_model = object()
    writer_model = object()
    outline_model = object()
    monkeypatch.setattr(roles, "bounded_model", lambda _model, **_kwargs: graph_model)
    monkeypatch.setattr(roles, "bounded_writer_model", lambda _model: writer_model)
    monkeypatch.setattr(roles, "bounded_outline_model", lambda _model: outline_model)

    roles.build_agent(None, loop="paper", repo=tmp_path)

    specs = by_name(fake_deepagents["subagents"])
    assert fake_deepagents["model"] is graph_model
    assert specs["writer"]["model"] is writer_model
    # The editor also gets its own model, and a stronger one. It repairs what
    # the judge faulted, so it has to keep pace with the judge. Both it and
    # the planner re-emit a whole outline, so both share the wider output cap.
    assert specs["outline-editor"]["model"] is outline_model
    assert specs["planner"]["model"] is outline_model
    assert all(
        "model" not in specs[name]
        for name in specs
        if name not in ("writer", "outline-editor", "planner")
    )


def test_build_paper_agents_bounds_the_outline_editor_and_planner_output(
    fake_langchain, fake_deepagents, tmp_path, monkeypatch
):
    """The live per-role pipeline shares one `create_deep_agent` call site, so
    this is the options-building seam: assert on the model roles.py computes
    for each role, the same seam a revert of the cap would have to touch."""
    import sys

    calls = []

    def recording_create(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(sys.modules["deepagents"], "create_deep_agent", recording_create)

    outline_model = object()
    plain_model = object()
    monkeypatch.setattr(roles, "bounded_outline_model", lambda _model: outline_model)
    monkeypatch.setattr(roles, "bounded_model", lambda _model, **_kwargs: plain_model)

    roles.build_paper_agents(None, loop="paper", repo=tmp_path)

    by_role = {
        call["system_prompt"].split(".", 1)[0].removeprefix("You are the "): call["model"]
        for call in calls
    }
    assert by_role["outline_editor"] is outline_model
    assert by_role["planner"] is outline_model
    assert by_role["researcher"] is plain_model
    assert by_role["outline_judge"] is plain_model


def test_build_paper_agents_compiles_one_direct_graph_per_role(fake_langchain, fake_deepagents, tmp_path):
    agents = roles.build_paper_agents(None, loop="paper", repo=tmp_path)

    assert set(agents) == {
        "planner",
        "outline_editor",
        "source_librarian",
        "outline_judge",
        "researcher",
        "verifier",
        "locator",
        "section_judge",
        "ledger",
        "diagrammer",
        "chartist",
        "writer",
        "reviewer",
    }


def test_build_agent_leaves_parent_debug_off_by_default(fake_langchain, fake_deepagents, tmp_path):
    roles.build_agent(None, loop="paper", repo=tmp_path)
    assert fake_deepagents["debug"] is False


def test_build_agent_can_turn_on_parent_debug(fake_langchain, fake_deepagents, tmp_path):
    """Subagent dict specs have no debug field; the compiled parent owns it."""
    roles.build_agent(None, loop="paper", repo=tmp_path, debug=True)
    assert fake_deepagents["debug"] is True
    assert all("debug" not in spec for spec in fake_deepagents["subagents"])


# -- the locator: one tool, and it is not search ----------------------------


def test_the_locator_holds_exactly_locate(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", backend=Boundary(), docs_backend=Boundary(), repo=Path(".")))
    assert names(specs["locator"]) == ["locate"]


def test_the_researcher_never_gets_locate(fake_langchain):
    """An open-web call inside the researcher would walk around the allowlist."""
    specs = by_name(roles.subagents_for(None, "paper", backend=Boundary(), docs_backend=Boundary(), repo=Path(".")))
    for role in specs:
        if role != "locator":
            assert "locate" not in names(specs[role]), role


def test_the_locator_cannot_write(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", backend=Boundary(), repo=Path(".")))["locator"]
    assert {"operations": ["write"], "paths": ["/**"], "mode": "deny"} in spec["permissions"]


def test_locate_tool_reports_a_miss_rather_than_an_empty_string(fake_langchain):
    class NoWeb:
        name = "stub"
        cost_per_call = 0.0

        def locate(self, question):
            import research  # noqa: PLC0415

            return research.Finding(question, "", note="nothing came back")

    assert roles.locate_tool(NoWeb())("q").startswith("NO ANSWER.")


def test_the_locator_card_names_no_allowlist_domain():
    """A domain in the card is a filter, and this turn is not filtered."""
    import source_policy  # noqa: PLC0415

    card = (roles.SKILLS_DIR / "locator" / "SKILL.md").read_text(encoding="utf-8")
    for entry in source_policy.SEED_ALLOWLIST:
        assert entry not in card, entry


def test_the_researcher_card_still_says_the_search_is_filtered():
    card = (roles.SKILLS_DIR / "researcher" / "SKILL.md").read_text(encoding="utf-8")
    assert "domain-filtered" in card
    assert "corpus_search" in card and "source_urls" in card


def test_corpus_search_prints_a_url_only_when_the_hit_has_one(fake_langchain, tmp_path):
    import corpus  # noqa: PLC0415

    hits = [
        corpus.Hit(key="b:c1", claim="c", quote="q", source_title="T", url="https://a.example/p"),
        corpus.Hit(key="b:c2", claim="c", quote="q", source_title="T"),
    ]
    search = roles.corpus_search_tool([tmp_path])
    monkey = corpus.search
    corpus.search = lambda *_a, **_k: hits
    try:
        text = search("q")
    finally:
        corpus.search = monkey
    assert text.count("URL: https://a.example/p") == 1
    assert text.count("URL:") == 1
