"""The cast and the fence, for a loop that runs with nobody watching."""

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
def hook(target_repo, contract):
    return roles.scope_hook(target_repo, roleplan.plan(contract, "fixer"))


# -- the cast ---------------------------------------------------------------


def test_the_cast_is_the_three_fixer_roles(contract):
    assert tuple(roleplan.plan(contract, "fixer")) == (
        "orchestrator",
        "code_implementer",
        "judge",
    )


def test_the_judge_writes_nothing(contract):
    judge = roleplan.plan(contract, "fixer")["judge"]
    assert not judge.can_write
    assert judge.allow == ()


def test_the_orchestrator_only_spawns(contract):
    orchestrator = roleplan.plan(contract, "fixer")["orchestrator"]
    assert orchestrator.tools == ("Task",)
    assert not orchestrator.can_write


def test_no_role_in_this_cast_holds_a_shell(contract):
    """The judge used to. A shell is the path around the hook, which matches
    Edit, Write, and NotebookEdit and not `sed -i`."""
    cast = roleplan.plan(contract, "fixer")
    assert [name for name, role in cast.items() if "Bash" in role.tools] == []


def test_the_coder_is_denied_the_tests(contract):
    coder = roleplan.plan(contract, "fixer")["code_implementer"]
    assert coder.allow == ("app/**",)
    assert "tests/**" in coder.deny


# -- the hook ---------------------------------------------------------------


def test_a_write_inside_scope_gets_no_opinion(hook, target_repo):
    assert call(hook, agent="fixer-code-implementer", path=f"{target_repo}/app/main.py") == {}


def test_the_fixer_cannot_weaken_a_test(hook, target_repo):
    """The whole point of the loop. A fixer that can edit the failing test does
    not have to fix anything."""
    denied = call(hook, agent="fixer-code-implementer", path=f"{target_repo}/tests/test_x.py")
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_deny_envelope_key_by_key(hook, target_repo):
    """A typo in this shape fails open, and under the old permission mode the
    hook was the only gate there was."""
    denied = call(hook, agent="fixer-code-implementer", path=f"{target_repo}/tests/test_x.py")
    assert set(denied) == {"hookSpecificOutput"}
    output = denied["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "app/**" in output["permissionDecisionReason"]


def test_the_judge_cannot_write_through_the_hook(hook, target_repo):
    assert call(hook, agent="fixer-judge", path=f"{target_repo}/app/main.py")


def test_a_write_with_no_agent_is_denied(hook, target_repo):
    denied = call(hook, agent=None, path=f"{target_repo}/app/main.py")
    assert "orchestrator" in denied["hookSpecificOutput"]["permissionDecisionReason"]
    assert call(hook, agent="general-purpose", path=f"{target_repo}/app/main.py")


def test_a_path_outside_the_repo_is_denied(hook):
    denied = call(hook, agent="fixer-code-implementer", path="/etc/passwd")
    assert "outside the target repo" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_read_tool_gets_no_opinion(hook, target_repo):
    assert call(hook, agent="fixer-code-implementer", tool="Read") == {}


def test_every_path_key_is_checked(hook):
    for key in roles.PATH_KEYS:
        data = {
            "tool_name": "Write",
            "tool_input": {key: "/etc/passwd"},
            "agent_type": "fixer-code-implementer",
        }
        assert asyncio.run(hook(data, "id", None)), key


# -- what reaches the SDK ---------------------------------------------------


def test_the_permission_mode_denies_rather_than_prompts(fake_sdk, contract):
    """This assertion used to read `acceptEdits`, and it was pinning the bug.

    `acceptEdits` auto-accepts every file edit before the allow list is
    consulted, so the hook above becomes the only fence, and that hook fails
    open on a typo. The deck justified it with "nobody is chatting", which is
    the argument for `dontAsk`: the SDK defines that as "deny anything not
    pre-approved". Both modes never prompt. Only one fails closed.
    """
    fake_sdk()
    assert roles.options_for(contract, loop="fixer").permission_mode == "dontAsk"


def test_max_turns_uses_the_sdk_field_name(fake_sdk, contract):
    """`max_turns=` raises TypeError on the real SDK, and the old fake took
    `**kwargs`, so it accepted any spelling."""
    fake_sdk()
    for agent in roles.options_for(contract, loop="fixer").agents.values():
        assert agent.maxTurns > 0


def test_a_subagent_waits_for_its_verdict(fake_sdk, contract):
    fake_sdk()
    for agent in roles.options_for(contract, loop="fixer").agents.values():
        assert agent.background is False


def test_the_allowlist_covers_every_tool_the_cast_holds(fake_sdk, contract):
    """Under `dontAsk` this list is the enforced boundary, which is the second
    gate `acceptEdits` gave away."""
    fake_sdk()
    options = roles.options_for(contract, loop="fixer")
    for role in roleplan.plan(contract, "fixer").values():
        for tool in role.tools:
            assert tool in options.allowed_tools, f"{role.name} would be denied {tool}"
    assert "Task" in options.allowed_tools and "Agent" in options.allowed_tools


def test_nothing_in_this_cast_gets_a_shell(fake_sdk, contract):
    fake_sdk()
    options = roles.options_for(contract, loop="fixer")
    assert "Bash" in options.disallowed_tools
    assert "Bash" not in options.allowed_tools


def test_a_reader_carries_the_write_tools_as_a_deny_list(fake_sdk, contract):
    fake_sdk()
    agents = roles.options_for(contract, loop="fixer").agents
    assert agents["fixer-judge"].disallowedTools == roles.NO_WRITE
    assert agents["fixer-code-implementer"].disallowedTools == []


def test_the_builtin_agents_are_disabled(fake_sdk, contract):
    """`general-purpose` ships with filesystem tools. Unattended, that is the
    hole nobody is watching."""
    fake_sdk()
    options = roles.options_for(contract, loop="fixer")
    assert options.env["CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS"] == "1"


def test_the_plugin_is_loaded(fake_sdk, contract):
    fake_sdk()
    options = roles.options_for(contract, loop="fixer")
    assert options.plugins == [{"type": "local", "path": str(roles.PLUGIN)}]
    assert options.system_prompt.startswith("You are the fixer orchestrator")
    assert "Merging is never yours" in options.system_prompt


def test_the_money_ceiling_reaches_the_runtime(fake_sdk, contract):
    """`.loop.yml` declares `usd: 2.00` and it used to reach nothing."""
    fake_sdk()
    assert roles.options_for(contract, loop="fixer").max_budget_usd == 2.0


def test_the_hook_is_registered_once_per_write_tool(fake_sdk, contract):
    fake_sdk()
    hooks = roles.options_for(contract, loop="fixer").hooks["PreToolUse"]
    assert sorted(h.matcher for h in hooks) == sorted(roles.WRITE_TOOL_NAMES)
    assert len(hooks) == 3


def test_every_role_gets_its_prompt_from_the_plugin(fake_sdk, contract):
    fake_sdk()
    agents = roles.options_for(contract, loop="fixer").agents
    assert set(agents) == {"fixer-code-implementer", "fixer-judge"}
    for name, agent in agents.items():
        assert len(agent.prompt) > 400, name


def test_an_agent_file_that_widens_its_tools_is_refused(fake_sdk, contract, monkeypatch):
    fake_sdk()
    real = roles.agent_files

    def widened():
        files = real()
        files["fixer-judge"]["tools"] = [*files["fixer-judge"]["tools"], "Write"]
        return files

    monkeypatch.setattr(roles, "agent_files", widened)
    with pytest.raises(ValueError, match="role table"):
        roles.options_for(contract, loop="fixer")
