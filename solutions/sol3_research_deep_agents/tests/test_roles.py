"""Tool lists, path checks, and the harness fence. All three layers, no SDK."""

from __future__ import annotations

from pathlib import Path

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
    for role in ("planner", "diagrammer", "writer", "reviewer"):
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
    for role in ("researcher", "planner", "writer", "reviewer", "diagrammer"):
        assert "check_docs" not in names(specs[role]), role


def test_only_the_planner_gets_the_brain(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", repo=Path(".")))
    assert "recall" in names(specs["planner"])
    for role in ("researcher", "verifier", "writer", "reviewer", "diagrammer"):
        assert "recall" not in names(specs[role]), role


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
    assert set(props) == {"failed_rows", "notes"}
    assert "ship" not in props and "verdict" not in props


def test_paper_writer_mounts_its_skill_and_cannot_browse_the_run(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", repo=Path(".")))["writer"]
    body = (roles.SKILLS_DIR / "writer" / "SKILL.md").read_text(encoding="utf-8")
    assert "technical white paper" in body.lower()
    assert "technical white paper" not in spec["system_prompt"].lower()
    assert "/skills/writer/SKILL.md" in spec["system_prompt"]
    assert spec["skills"] == ["/skills/writer/"]
    assert names(spec) == []
    assert spec["permissions"] == [
        {"operations": ["read"], "paths": ["/skills/writer/**"], "mode": "allow"},
        {"operations": ["read", "write"], "paths": ["/**"], "mode": "deny"},
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


def test_build_agent_binds_the_bounded_model_to_writer_only(
    fake_langchain, fake_deepagents, tmp_path, monkeypatch
):
    graph_model = object()
    writer_model = object()
    monkeypatch.setattr(roles, "bounded_model", lambda _model, **_kwargs: graph_model)
    monkeypatch.setattr(roles, "bounded_writer_model", lambda _model: writer_model)

    roles.build_agent(None, loop="paper", repo=tmp_path)

    specs = by_name(fake_deepagents["subagents"])
    assert fake_deepagents["model"] is graph_model
    assert specs["writer"]["model"] is writer_model
    assert all("model" not in specs[name] for name in specs if name != "writer")


def test_build_paper_agents_compiles_one_direct_graph_per_role(fake_langchain, fake_deepagents, tmp_path):
    agents = roles.build_paper_agents(None, loop="paper", repo=tmp_path)

    assert set(agents) == {"planner", "researcher", "verifier", "diagrammer", "writer", "reviewer"}


def test_build_agent_leaves_parent_debug_off_by_default(fake_langchain, fake_deepagents, tmp_path):
    roles.build_agent(None, loop="paper", repo=tmp_path)
    assert fake_deepagents["debug"] is False


def test_build_agent_can_turn_on_parent_debug(fake_langchain, fake_deepagents, tmp_path):
    """Subagent dict specs have no debug field; the compiled parent owns it."""
    roles.build_agent(None, loop="paper", repo=tmp_path, debug=True)
    assert fake_deepagents["debug"] is True
    assert all("debug" not in spec for spec in fake_deepagents["subagents"])
