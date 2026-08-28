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


def test_reviewer_holds_only_a_reader(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", repo=Path(".")))["reviewer"]
    assert names(spec) == ["read_file"]


def test_only_the_researcher_gets_search(fake_langchain):
    specs = by_name(roles.subagents_for(None, "paper", backend=Boundary(), repo=Path(".")))
    assert "search" in names(specs["researcher"])
    for role in ("planner", "diagrammer", "writer", "reviewer"):
        assert "search" not in names(specs[role]), role


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


def test_reader_does_not_raise_on_a_missing_file(fake_langchain, tmp_path):
    assert roles.read_tool(tmp_path)("nope.md").startswith("no such file")


def test_recall_is_honest_when_there_is_no_brain(fake_langchain):
    assert roles.second_brain_tool(None)("loops").startswith("NO BRAIN")


def test_recall_finds_prior_research(fake_langchain, tmp_path):
    (tmp_path / "area.md").write_text("# Loop Engineering\nexit conditions matter\n")
    out = roles.second_brain_tool(tmp_path)("exit conditions")
    assert "area.md" in out


def test_permissions_deny_a_reader_everything():
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    rules = roles.permission_rules(roleplan.plan(None, "paper")["reviewer"])
    assert rules == [{"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}]


def test_permissions_put_deny_before_allow():
    """First match wins, so a role's deny list must come first or its allow
    list silently wins on an overlap."""
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    rules = roles.permission_rules(roleplan.plan(None, "paper")["writer"])
    assert rules[0]["mode"] == "deny"
    assert "evidence/**" in rules[0]["paths"]
    assert rules[1]["mode"] == "allow"
    assert rules[-1] == {"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}


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


def test_skills_reach_the_prompt(fake_langchain):
    spec = by_name(roles.subagents_for(None, "paper", repo=Path(".")))["writer"]
    assert "white paper" in spec["system_prompt"].lower()
    assert spec["skills"] == ["/skills/writer/"]


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
