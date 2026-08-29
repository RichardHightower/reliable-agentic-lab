"""The Deep Agents port. One tool list per subagent, scope inside the tool."""

from __future__ import annotations

import sys
import types

import roles


def _by_name(subagents):
    return {agent["name"]: agent for agent in subagents}


def test_the_orchestrator_gets_no_subagent(contract, fake_langchain):
    assert set(_by_name(roles.subagents_for(contract, loop="enhancer"))) == {"doer", "judge"}


def test_the_judge_holds_no_custom_tools(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert judge["tools"] == []


def test_the_doer_holds_only_its_scoped_write_tool(contract, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    assert [tool.__name__ for tool in doer["tools"]] == ["write"]


def test_each_subagent_carries_its_purpose(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert "judge" in judge["system_prompt"]
    assert (
        judge["description"]
        == "Scores the attempt. Reads reports and the diff. Holds no write path."
    )


def test_the_write_tool_writes_inside_the_scope(contract, target_repo, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    write = doer["tools"][0]

    assert write("tickets/7.md", "body") == "wrote tickets/7.md"
    assert (target_repo / "tickets" / "7.md").read_text(encoding="utf-8") == "body"


def test_the_write_tool_refuses_outside_the_scope(contract, target_repo, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    write = doer["tools"][0]

    answer = write("app/x.py", "print()")

    assert answer.startswith("REFUSED")
    assert "tickets/**" in answer
    assert not (target_repo / "app" / "x.py").exists()


def test_the_judge_denies_every_write(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    rules = judge["permissions"]
    assert rules == [
        {"operations": ["write"], "paths": ["/**"], "mode": "deny"},
    ]


def test_the_doer_allows_tickets_then_denies_the_rest(contract, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    allow, deny = doer["permissions"]
    assert allow["mode"] == "allow"
    assert "/tickets/**" in allow["paths"]
    assert deny == {"operations": ["write"], "paths": ["/**"], "mode": "deny"}


def test_the_judge_asks_for_structured_output(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    schema = judge["response_format"]
    assert schema["required"] == ["kind", "present_fields"]
    assert "ready" not in schema["properties"]


def test_a_role_with_a_skill_mounts_it_instead_of_pasting_it(contract, fake_langchain):
    """This test asserted the opposite, and the assertion was the bug.

    Deep Agents loads a skill in two levels: metadata in the system prompt at
    startup, instructions only when the skill is invoked. The folder used to
    paste the whole body into `system_prompt` AND mount it, so the body was
    always resident and the mount saved nothing.
    """
    specs = _by_name(roles.subagents_for(contract, loop="enhancer"))
    body = (roles.SKILLS_DIR / "doer" / "SKILL.md").read_text(encoding="utf-8")
    distinctive = "tickets/<id>.enhancer-candidate.md"
    assert distinctive in body

    doer = specs["doer"]
    assert distinctive not in doer["system_prompt"]
    assert "read /skills/doer/SKILL.md" in doer["system_prompt"]
    assert doer["skills"] == ["/skills/doer/"]


def test_the_judge_skill_mounts_too(contract, fake_langchain):
    """It has had a SKILL.md since this folder was written. The line that set
    the key named only the doer, so it never mounted."""
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert "read /skills/judge/SKILL.md" in judge["system_prompt"]
    assert judge["skills"] == ["/skills/judge/"]


def test_the_judge_skill_names_the_standard_acceptance_criteria_heading():
    text = (roles.SKILLS_DIR / "judge" / "SKILL.md").read_text(encoding="utf-8")
    assert "Acceptance criteria" in text
    assert "(AC-n)" in text
    assert "add a box to the customer page" in text
    assert "fenced ASCII diagram" in text


def test_the_doer_skill_requires_the_standard_ticket_headings_and_ui_wireframe():
    text = (roles.SKILLS_DIR / "doer" / "SKILL.md").read_text(encoding="utf-8")
    assert "Acceptance criteria" in text
    assert "(AC-n)" in text
    assert "Wireframe" in text


def _install_fake_deepagents(monkeypatch, seen):
    def create_deep_agent(**kwargs):
        seen.update(kwargs)
        return "agent"

    def permission(**kwargs):
        return ("perm", kwargs)

    def profile(**kwargs):
        return ("profile", kwargs)

    def gp(**kwargs):
        return ("gp", kwargs)

    def register(model, harness):
        seen["registered"] = (model, harness)

    deepagents = types.ModuleType("deepagents")
    deepagents.create_deep_agent = create_deep_agent
    deepagents.FilesystemPermission = permission
    deepagents.HarnessProfile = profile
    deepagents.GeneralPurposeSubagentProfile = gp
    deepagents.register_harness_profile = register

    backends = types.ModuleType("deepagents.backends")

    class FilesystemBackend:
        def __init__(self, root_dir, virtual_mode=False):
            self.root_dir = root_dir
            self.virtual_mode = virtual_mode

    class CompositeBackend:
        def __init__(self, default, routes):
            self.default = default
            self.routes = routes

    backends.FilesystemBackend = FilesystemBackend
    backends.CompositeBackend = CompositeBackend
    deepagents.backends = backends

    monkeypatch.setitem(sys.modules, "deepagents", deepagents)
    monkeypatch.setitem(sys.modules, "deepagents.backends", backends)
    return deepagents


def test_build_agent_hands_the_subagents_to_deepagents(contract, monkeypatch, fake_langchain):
    seen = {}
    _install_fake_deepagents(monkeypatch, seen)

    assert roles.build_agent(contract, loop="enhancer") == "agent"
    assert seen["model"] == "anthropic:claude-sonnet-5"
    assert set(_by_name(seen["subagents"])) == {"doer", "judge"}
    assert seen["debug"] is False


def test_build_agent_forwards_a_one_call_debug_flag(contract, monkeypatch, fake_langchain):
    seen = {}
    _install_fake_deepagents(monkeypatch, seen)

    roles.build_agent(contract, loop="enhancer", debug=True)

    assert seen["debug"] is True


def test_build_agent_turns_off_the_general_purpose_subagent(contract, monkeypatch, fake_langchain):
    seen = {}
    _install_fake_deepagents(monkeypatch, seen)

    roles.build_agent(contract, loop="enhancer")

    model, harness = seen["registered"]
    assert model == "anthropic:claude-sonnet-5"
    assert harness[0] == "profile"
    assert harness[1]["excluded_tools"] == roles.ORCHESTRATOR_EXCLUDED_TOOLS
    assert harness[1]["general_purpose_subagent"] == ("gp", {"enabled": False})


def test_build_agent_mounts_the_crm_as_a_virtual_filesystem(contract, monkeypatch, fake_langchain):
    seen = {}
    _install_fake_deepagents(monkeypatch, seen)

    roles.build_agent(contract, loop="enhancer")

    backend = seen["backend"]
    assert backend.default.virtual_mode is True
    assert str(contract.repo.resolve()) == backend.default.root_dir
    assert "/skills/" in backend.routes
    assert "/memory/" in backend.routes
    assert seen["memory"] == ["/memory/AGENTS.md"]
    assert seen["skills"] == ["/skills/"]
    assert seen["permissions"] == [
        ("perm", {"operations": ["write"], "paths": ["/**"], "mode": "deny"})
    ]


def test_build_agent_passes_only_absolute_permission_paths(contract, monkeypatch, fake_langchain):
    """Deep Agents 0.7 rejects a relative path such as ``tickets/**``."""
    seen = {}
    _install_fake_deepagents(monkeypatch, seen)

    roles.build_agent(contract, loop="enhancer")

    for subagent in seen["subagents"]:
        for _, permission in subagent["permissions"]:
            assert all(path.startswith("/") for path in permission["paths"])
