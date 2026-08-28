"""How this runtime says "this role may not write that file".

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. Returning an empty dict means "no opinion", which lets the call through,
so a typo anywhere in the deny envelope fails open. The full shape gets asserted
key by key for that reason.

`options_for` imports the SDK lazily, so the `fake_sdk` fixture is enough to
reach it. Nothing here installs `claude-agent-sdk`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import roleplan
import roles


def call(repo: Path, role, tool: str = "Write", **tool_input) -> dict:
    check = roles.scope_hook(Path(repo), role)
    return asyncio.run(check({"tool_name": tool, "tool_input": tool_input}, "tool-use-id", None))


@pytest.fixture
def doer(contract):
    return roleplan.plan(contract, "enhancer")["doer"]


# -- scope_hook ------------------------------------------------------------


def test_the_hook_allows_a_write_inside_scope(repo, doer):
    assert call(repo, doer, file_path=str(repo / "tickets" / "T001.md")) == {}


def test_the_hook_denies_a_write_outside_scope(repo, doer):
    """The full shape matters. A typo anywhere in it fails open."""
    output = call(repo, doer, file_path=str(repo / "app" / "models.py"))["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "outside that scope" in output["permissionDecisionReason"]


def test_the_deny_reason_names_what_the_role_may_write(repo, doer):
    reason = call(repo, doer, file_path=str(repo / "app" / "models.py"))["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "doer may write tickets/**" in reason
    assert "app/models.py" in reason


def test_a_role_with_no_allow_list_reads_as_writing_nothing(repo, contract):
    judge = roleplan.plan(contract, "enhancer")["judge"]
    reason = call(repo, judge, file_path=str(repo / "a.md"))["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "may write nothing" in reason


@pytest.mark.parametrize("tool", ["Edit", "Write", "NotebookEdit"])
def test_every_write_tool_is_guarded(repo, doer, tool):
    result = call(repo, doer, tool, file_path=str(repo / "app" / "models.py"))
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("tool", ["Read", "Glob", "Grep", "Bash", "Task"])
def test_the_hook_has_no_opinion_about_a_tool_that_cannot_write(repo, doer, tool):
    assert call(repo, doer, tool, file_path=str(repo / "app" / "models.py")) == {}


@pytest.mark.parametrize("key", roles.PATH_KEYS)
def test_the_hook_finds_the_path_under_every_key_a_tool_may_use(repo, doer, key):
    result = call(repo, doer, "Write", **{key: str(repo / "app" / "models.py")})
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_hook_has_no_opinion_when_no_input_names_a_path(repo, doer):
    """There is nothing to check, so there is nothing to deny."""
    assert call(repo, doer, "Write", content="body") == {}


def test_a_path_outside_the_repo_is_denied(repo, doer):
    """Fail closed. A path outside the repo matches no allow rule for any role.

    Letting it through because it did not match the allow list is the fail-open
    bug, and it is the one that reaches `/etc`.
    """
    result = call(repo, doer, file_path="/etc/hosts")
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "outside the target repo" in output["permissionDecisionReason"]


def test_a_relative_path_that_escapes_the_repo_is_denied(repo, doer):
    result = call(repo, doer, file_path=str(repo / ".." / "elsewhere.md"))
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_denied_scope_beats_an_allowed_one(repo, contract):
    code = roleplan.plan(contract, "implementer")["code_implementer"]
    assert call(repo, code, file_path=str(repo / "app" / "models.py")) == {}
    denied = call(repo, code, file_path=str(repo / "tests" / "test_models.py"))
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_every_writing_role_denies_an_out_of_scope_write_in_every_loop(repo, contract, loop):
    for role in roleplan.plan(contract, loop).values():
        if not role.can_write:
            continue
        result = call(repo, role, file_path=str(repo / "etc" / "nope.txt"))
        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", f"{loop}/{role.name} let an out-of-scope write through"


# -- options_for -----------------------------------------------------------


def test_options_for_needs_the_sdk(contract):
    """Without the package there is nothing to build, and that must be loud."""
    with pytest.raises(ImportError):
        roles.options_for(contract, loop="enhancer")


def test_options_for_builds_one_subagent_per_role_that_is_not_the_orchestrator(contract, fake_sdk):
    """The orchestrator is the caller, not a subagent it can delegate to itself."""
    options = roles.options_for(contract, loop="enhancer")
    assert set(options.agents) == {"doer", "judge"}


def test_a_role_name_becomes_a_hyphenated_agent_name(contract, fake_sdk):
    options = roles.options_for(contract, loop="implementer")
    assert "test-implementer" in options.agents
    assert "test_implementer" not in options.agents


def test_each_subagent_carries_its_own_tool_list(contract, fake_sdk):
    options = roles.options_for(contract, loop="enhancer")
    assert "Write" in options.agents["doer"].tools
    assert "Write" not in options.agents["judge"].tools, "the judge holds no write tool"


def test_each_subagent_carries_its_purpose_as_its_prompt(contract, fake_sdk):
    doer = roles.options_for(contract, loop="enhancer").agents["doer"]
    assert doer.description == roleplan.PURPOSE["doer"]
    assert doer.prompt.startswith("You are the doer.")


def test_the_options_point_at_the_target_repo(contract, fake_sdk):
    assert roles.options_for(contract, loop="enhancer").cwd == str(contract.repo)


def test_allowed_tools_is_derived_from_the_cast_rather_than_restated(contract, fake_sdk):
    """A loop whose cast writes nothing must not be handed Write."""
    options = roles.options_for(contract, loop="enhancer")
    expected = sorted(
        {tool for role in roleplan.plan(contract, "enhancer").values() for tool in role.tools}
    )
    assert options.allowed_tools == expected


def test_allowed_tools_is_sorted_and_deduplicated(contract, fake_sdk):
    tools = roles.options_for(contract, loop="implementer").allowed_tools
    assert tools == sorted(set(tools))


def test_the_research_cast_gets_websearch_and_no_orchestrator_agent(contract, fake_sdk):
    options = roles.options_for(contract, loop="research")
    assert "WebSearch" in options.allowed_tools
    assert "orchestrator" not in options.agents


def test_options_for_needs_a_contract_even_though_the_table_does_not(fake_sdk):
    """A known boundary, recorded rather than worked around.

    `roleplan.plan(None, "research")` works, because research runs against a
    question and has no `.loop.yml`. `options_for` still reads `contract.repo`
    for `cwd`, so it needs one. This folder is the enhancer, `loop.py` always
    passes a Contract, and this module is this folder's local `roles.py`.
    Widening it here would make the copy drift from the other ports.
    """
    with pytest.raises(AttributeError):
        roles.options_for(None, loop="research")


def test_a_hook_is_registered_for_every_write_tool_on_every_writing_role(contract, fake_sdk):
    hooks = roles.options_for(contract, loop="enhancer").hooks["PreToolUse"]
    assert sorted(hook.matcher for hook in hooks) == ["Edit", "NotebookEdit", "Write"]


def test_a_role_that_cannot_write_gets_no_hook(contract, fake_sdk):
    """The judge holds neither Edit nor Write, so there is nothing to guard."""
    plan = roleplan.plan(contract, "enhancer")
    writers = [role for role in plan.values() if role.can_write]
    hooks = roles.options_for(contract, loop="enhancer").hooks["PreToolUse"]
    assert len(hooks) == len(writers) * 3


def test_the_registered_hook_is_the_one_that_denies(repo, contract, fake_sdk):
    """A hook that is built but never wired up is a scope that is never enforced."""
    hook = roles.options_for(contract, loop="enhancer").hooks["PreToolUse"][0].hooks[0]
    result = asyncio.run(
        hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(Path(contract.repo) / "app/x.py")},
            },
            "id",
            None,
        )
    )
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_subagent_inherits_the_projects_mcp_servers(contract, fake_sdk):
    assert roles.options_for(contract, loop="enhancer").setting_sources == ["project"]
