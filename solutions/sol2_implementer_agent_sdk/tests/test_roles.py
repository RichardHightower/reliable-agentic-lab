"""The cast and the fence. Two places enforce scope and you need both."""

from __future__ import annotations

import asyncio

import pytest
import roleplan
import roles


def call(hook, *, agent, tool="Write", path="/tmp/crm/app/main.py"):
    data = {"tool_name": tool, "tool_input": {"file_path": path}}
    if agent is not None:
        data["agent_type"] = agent
    return asyncio.run(hook(data, "id", None))


@pytest.fixture
def hook(repo, contract):
    return roles.scope_hook(repo, roleplan.plan(contract, "implementer"))


# -- the cast ---------------------------------------------------------------


def test_the_cast_is_the_five_implementer_roles(contract):
    assert tuple(roleplan.plan(contract, "implementer")) == (
        "orchestrator",
        "planner",
        "test_implementer",
        "code_implementer",
        "judge",
    )


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_the_judge_writes_nothing_in_every_loop(loop):
    judge = roleplan.plan(None, loop)["judge"]
    assert not judge.can_write
    assert judge.allow == ()


def test_the_orchestrator_only_spawns(contract):
    orchestrator = roleplan.plan(contract, "implementer")["orchestrator"]
    assert orchestrator.tools == ("Task",)
    assert not orchestrator.can_write


def test_no_role_in_this_cast_holds_a_shell(contract):
    """A shell is the path around the hook. It matches Edit, Write, and
    NotebookEdit, and none of those is `sed -i`."""
    cast = roleplan.plan(contract, "implementer")
    assert [name for name, role in cast.items() if "Bash" in role.tools] == []


def test_the_write_scopes_are_the_ones_the_repo_declared(contract):
    cast = roleplan.plan(contract, "implementer")
    assert cast["planner"].allow == ("steps.jsonl",)
    assert cast["test_implementer"].allow == ("tests/**",)
    assert cast["code_implementer"].allow == ("app/**",)
    assert "tests/**" in cast["code_implementer"].deny


def test_an_override_that_widens_a_reader_is_refused(monkeypatch):
    monkeypatch.setitem(roleplan.OVERRIDES, ("implementer", "judge"), {"tools": ("Read", "Write")})
    with pytest.raises(ValueError, match="reader"):
        roleplan.plan(None, "implementer")


# -- the hook ---------------------------------------------------------------


def test_a_write_inside_scope_gets_no_opinion(hook, repo):
    assert call(hook, agent="implementer-code-implementer", path=f"{repo}/app/main.py") == {}
    assert call(hook, agent="implementer-test-implementer", path=f"{repo}/tests/test_x.py") == {}
    assert call(hook, agent="implementer-planner", path=f"{repo}/steps.jsonl") == {}


def test_the_code_implementer_cannot_write_a_test(hook, repo):
    """The regression test for this whole change.

    This port registered one hook per writing role, so all three ran on every
    `Write`. An empty dict means "no opinion", so the code implementer was
    denied by its own hook and waved through by the test implementer's, and the
    effective scope was the union of all three allow lists. The separation Lab
    2 exists to teach did not survive a real run.
    """
    denied = call(hook, agent="implementer-code-implementer", path=f"{repo}/tests/test_x.py")
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "code_implementer" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_test_implementer_cannot_write_the_code(hook, repo):
    assert call(hook, agent="implementer-test-implementer", path=f"{repo}/app/main.py")


def test_the_planner_cannot_write_either_of_them(hook, repo):
    assert call(hook, agent="implementer-planner", path=f"{repo}/app/main.py")
    assert call(hook, agent="implementer-planner", path=f"{repo}/tests/test_x.py")


def test_the_deny_envelope_key_by_key(hook, repo):
    """A typo in this shape fails open, so it is asserted key by key."""
    denied = call(hook, agent="implementer-code-implementer", path=f"{repo}/tests/test_x.py")
    assert set(denied) == {"hookSpecificOutput"}
    output = denied["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "app/**" in output["permissionDecisionReason"]
    assert "tests/test_x.py" in output["permissionDecisionReason"]


def test_a_write_with_no_agent_is_denied(hook, repo):
    """The orchestrator holds only the spawn tool. A write from it breaks its
    contract, and a write from an agent nobody configured is worse."""
    denied = call(hook, agent=None, path=f"{repo}/app/main.py")
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "orchestrator" in denied["hookSpecificOutput"]["permissionDecisionReason"]
    assert call(hook, agent="general-purpose", path=f"{repo}/app/main.py")


def test_a_path_outside_the_repo_is_denied(hook):
    denied = call(hook, agent="implementer-code-implementer", path="/etc/passwd")
    assert "outside the target repo" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_traversal_out_and_back_is_denied(hook, repo):
    assert call(hook, agent="implementer-code-implementer", path=f"{repo}/../elsewhere/app/x.py")


def test_a_read_tool_gets_no_opinion(hook, repo):
    assert call(hook, agent="implementer-code-implementer", tool="Read") == {}


def test_a_tool_call_with_no_path_gets_no_opinion(hook):
    assert asyncio.run(hook({"tool_name": "Write", "tool_input": {}}, "id", None)) == {}


def test_every_path_key_is_checked(hook):
    for key in roles.PATH_KEYS:
        data = {
            "tool_name": "Write",
            "tool_input": {key: "/etc/passwd"},
            "agent_type": "implementer-code-implementer",
        }
        assert asyncio.run(hook(data, "id", None)), key


# -- options_for ------------------------------------------------------------


def test_max_turns_uses_the_sdk_field_name(fake_sdk, contract):
    """`max_turns=` on an AgentDefinition raises TypeError on the real SDK.

    A fake that takes `**kwargs` swallows the difference, which is why the
    fake in conftest is an explicit dataclass.
    """
    fake_sdk()
    for agent in roles.options_for(contract).agents.values():
        assert agent.maxTurns > 0


def test_a_subagent_waits_for_its_verdict(fake_sdk, contract):
    """SDK 2.1.198 defaults a subagent to background."""
    fake_sdk()
    for agent in roles.options_for(contract).agents.values():
        assert agent.background is False


def test_the_allowlist_covers_every_tool_the_cast_holds(fake_sdk, contract):
    """`allowed_tools` gates a subagent's calls too, not just the parent's."""
    fake_sdk()
    options = roles.options_for(contract)
    for role in roleplan.plan(contract, "implementer").values():
        for tool in role.tools:
            assert tool in options.allowed_tools, f"{role.name} would be denied {tool}"
    assert "Task" in options.allowed_tools and "Agent" in options.allowed_tools


def test_nothing_in_this_cast_gets_a_shell(fake_sdk, contract):
    fake_sdk()
    options = roles.options_for(contract)
    assert "Bash" in options.disallowed_tools
    assert "Bash" not in options.allowed_tools


def test_the_permission_mode_denies_rather_than_prompts(fake_sdk, contract):
    fake_sdk()
    assert roles.options_for(contract).permission_mode == "dontAsk"


def test_a_reader_carries_the_write_tools_as_a_deny_list(fake_sdk, contract):
    fake_sdk()
    agents = roles.options_for(contract).agents
    assert agents["implementer-judge"].disallowedTools == roles.NO_WRITE
    assert agents["implementer-code-implementer"].disallowedTools == []


def test_the_builtin_agents_are_disabled(fake_sdk, contract):
    """`general-purpose` ships with filesystem tools. That is the hole."""
    fake_sdk()
    assert roles.options_for(contract).env["CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS"] == "1"


def test_the_plugin_is_loaded(fake_sdk, contract):
    fake_sdk()
    options = roles.options_for(contract)
    assert options.plugins == [{"type": "local", "path": str(roles.PLUGIN)}]
    assert options.system_prompt.startswith("You are the implementer orchestrator")


def test_the_cost_ceiling_comes_off_the_contract(fake_sdk, contract):
    """`.loop.yml` declares `usd: 2.00`, and it used to reach nothing."""
    fake_sdk()
    assert roles.options_for(contract).max_budget_usd == 2.0
    assert roles.options_for(contract, max_usd=0.5).max_budget_usd == 0.5


def test_no_role_build_requests_project_settings(fake_sdk, contract):
    """#567, widened by follow-up 3 (judge of PR #570). A write-capable
    role's build must never request project settings, so a target repo's
    own `.claude/settings.json` deny can never outrank the scope hook. The
    judge is no exception: this port declares no MCP server, so the one
    stated reason for `setting_sources=["project"]` never applied to it
    either, and leaving it exposed made it the one role a target repo's
    deny list could still silently starve."""
    fake_sdk()
    for name in ("planner", "test_implementer", "code_implementer", "judge"):
        options = roles.options_for(contract, role_names=frozenset({name}))
        assert options.setting_sources == [], name


def test_the_judge_can_still_read_without_project_settings(fake_sdk, contract):
    """#567 follow-up 3. Dropping project settings for the judge must not
    cost it the tools its verdict depends on: `Read`, `Glob`, and `Grep` are
    granted through `tools=[...]`/`allowed_tools`, never through
    `setting_sources`, so the judge still reads."""
    fake_sdk()
    options = roles.options_for(contract, role_names=frozenset({"judge"}))
    judge_agent = options.agents["implementer-judge"]
    for tool in ("Read", "Glob", "Grep"):
        assert tool in judge_agent.tools, tool
        assert tool in options.allowed_tools, tool


def test_the_real_options_for_hook_permits_the_test_implementer_and_denies_the_code_implementer(
    fake_sdk, contract, repo
):
    """#567. Not `roles.scope_hook()` called by hand, the hook that
    `options_for` itself wires onto the options it returns for each
    single-role build. Project settings are gone for both of these builds
    now (the test above), so this hook is the only opinion either agent
    gets, and it must still keep the two roles apart."""
    fake_sdk()
    test_hook = roles.options_for(
        contract, role_names=frozenset({"test_implementer"})
    ).hooks["PreToolUse"][0].hooks[0]
    code_hook = roles.options_for(
        contract, role_names=frozenset({"code_implementer"})
    ).hooks["PreToolUse"][0].hooks[0]

    assert call(test_hook, agent="implementer-test-implementer", path=f"{repo}/tests/test_x.py") == {}
    denied = call(code_hook, agent="implementer-code-implementer", path=f"{repo}/tests/test_x.py")
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_options_can_expose_only_one_phase_role(fake_sdk, contract):
    fake_sdk()
    options = roles.options_for(
        contract,
        max_turns=4,
        role_names=frozenset({"test_implementer"}),
    )
    assert set(options.agents) == {"implementer-test-implementer"}
    assert options.max_turns == 4
    assert options.agents["implementer-test-implementer"].maxTurns == 4


def test_the_hook_is_registered_once_per_write_tool(fake_sdk, contract):
    """Three matchers, not nine. One hook serves the cast."""
    fake_sdk()
    hooks = roles.options_for(contract).hooks["PreToolUse"]
    assert sorted(h.matcher for h in hooks) == sorted(roles.WRITE_TOOL_NAMES)
    assert len(hooks) == 3


def test_every_role_gets_its_prompt_from_the_plugin(fake_sdk, contract):
    """A one-line `You are the planner.` is how a port drifts, silently."""
    fake_sdk()
    agents = roles.options_for(contract).agents
    assert set(agents) == {
        "implementer-planner",
        "implementer-test-implementer",
        "implementer-code-implementer",
        "implementer-judge",
    }
    for name, agent in agents.items():
        assert len(agent.prompt) > 400, name
        assert agent.description, name


def test_each_role_with_a_skill_directory_gets_the_skill(fake_sdk, contract):
    """Mount, do not paste. The skill body must not also live in the prompt."""
    fake_sdk()
    agents = roles.options_for(contract).agents
    expected = {
        "implementer-planner": "planner",
        "implementer-test-implementer": "test_implementer",
        "implementer-code-implementer": "code_implementer",
        "implementer-judge": "judge",
    }
    for name, skill in expected.items():
        assert agents[name].skills == [skill], name
        body = (roles.PLUGIN / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        # Front matter plus a distinctive sentence must not be inlined.
        distinctive = next(
            line.strip() for line in body.splitlines() if line.startswith("# ")
        )
        assert distinctive not in agents[name].prompt, name


def test_an_agent_file_that_widens_its_tools_is_refused(fake_sdk, contract, monkeypatch):
    """Drift in a tool list is how a reader quietly becomes a writer."""
    fake_sdk()
    real = roles.agent_files

    def widened():
        files = real()
        files["implementer-judge"]["tools"] = [*files["implementer-judge"]["tools"], "Write"]
        return files

    monkeypatch.setattr(roles, "agent_files", widened)
    with pytest.raises(ValueError, match="role table"):
        roles.options_for(contract)


def test_one_write_produces_exactly_one_opinion(fake_sdk, contract, repo):
    """Drive every registered hook the way the runtime would, not just one.

    The bug this replaces was in the wiring, not in any single hook: one
    closure per writing role meant three of them ran on every `Write`, each
    bound to a different scope. Two returned an empty dict, which is "no
    opinion".

    How the CLI combines several opinions is not something this port can read
    from the Python SDK, so it does not rely on knowing. It registers one
    opinion instead. That is checkable here, and it is true whichever way the
    aggregation falls.
    """
    fake_sdk()
    matchers = [m for m in roles.options_for(contract).hooks["PreToolUse"] if m.matcher == "Write"]
    assert len(matchers) == 1

    data = {
        "tool_name": "Write",
        "tool_input": {"file_path": f"{repo}/tests/test_x.py"},
        "agent_type": "implementer-code-implementer",
    }
    opinions = [
        asyncio.run(hook(data, "id", None)) for matcher in matchers for hook in matcher.hooks
    ]
    voiced = [o for o in opinions if o]
    assert len(voiced) == 1
    assert voiced[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
