"""The SDK wiring. Two places enforce scope and you need both."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import roleplan
import roles

WORK = Path("/tmp/sol3-test-work")


def call(hook, *, agent, tool="Write", path="/tmp/sol3-test-work/paper.md"):
    data = {"tool_name": tool, "tool_input": {"file_path": path}}
    if agent is not None:
        data["agent_type"] = agent
    return asyncio.run(hook(data, "id", None))


@pytest.fixture
def hook():
    return roles.scope_hook(WORK, roleplan.plan(None, "research"))


def test_a_write_inside_scope_gets_no_opinion(hook):
    """An empty dict means "no opinion", which lets the call through."""
    assert call(hook, agent="research-writer", path=f"{WORK}/sections/s1.md") == {}


def test_the_deny_envelope_key_by_key(hook):
    """A typo in this shape fails open, so it is asserted key by key."""
    denied = call(hook, agent="research-writer", path=f"{WORK}/paper.md")
    assert set(denied) == {"hookSpecificOutput"}
    output = denied["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "sections/**" in output["permissionDecisionReason"]
    assert "paper.md" in output["permissionDecisionReason"]


def test_a_reader_that_tries_to_write_is_denied(hook):
    """`agent_type` is what tells the one writer from the five readers."""
    for reader in (
        "research-outliner",
        "research-diagrammer",
        "research-chartist",
        "research-judge",
        "research-outline-judge",
        "research-section-judge",
        "research-ledger",
    ):
        assert call(hook, agent=reader, path=f"{WORK}/sections/s1.md"), reader


def test_the_writer_cannot_reach_the_run_state(hook):
    """A writer that can edit claims.json can grant itself its own evidence."""
    assert call(hook, agent="research-writer", path=f"{WORK}/claims.json")
    assert call(hook, agent="research-writer", path=f"{WORK}/.harness/state.json")


def test_a_write_with_no_agent_is_denied(hook):
    """The orchestrator holds only `Agent`. A write from it breaks its contract."""
    denied = call(hook, agent=None)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "orchestrator" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_an_unknown_agent_is_denied(hook):
    assert call(hook, agent="general-purpose")


def test_a_path_outside_the_work_directory_is_denied(hook):
    """Letting it through because it did not match the allow list is fail-open."""
    denied = call(hook, agent="research-writer", path="/etc/passwd")
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "outside the work directory" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_traversal_out_and_back_is_denied(hook):
    assert call(hook, agent="research-writer", path=f"{WORK}/../elsewhere/paper.md")


def test_a_read_tool_gets_no_opinion(hook):
    assert call(hook, agent="research-writer", tool="Read") == {}
    assert call(hook, agent="research-writer", tool="Bash") == {}


def test_a_tool_call_with_no_path_gets_no_opinion(hook):
    assert asyncio.run(hook({"tool_name": "Write", "tool_input": {}}, "id", None)) == {}


def test_every_path_key_is_checked(hook):
    for key in roles.PATH_KEYS:
        data = {
            "tool_name": "Write",
            "tool_input": {key: "/etc/passwd"},
            "agent_type": "research-writer",
        }
        assert asyncio.run(hook(data, "id", None)), key


# -- options_for -----------------------------------------------------------


def test_the_allowlist_covers_every_tool_the_cast_holds(fake_sdk, work, monkeypatch):
    """`allowed_tools` gates a subagent's calls too, not just the parent's.

    Reading it as the parent's tool list is what broke the first live run: the
    researcher held Perplexity and Context7 and had every call denied.
    """
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    fake_sdk()
    options = roles.options_for(work)
    for role in roleplan.plan(None, "research").values():
        for tool in role.tools:
            assert tool in options.allowed_tools, f"{role.name} would be denied {tool}"
    assert "mcp__perplexity__perplexity_search" in options.allowed_tools
    assert "mcp__perplexity__perplexity_ask" in options.allowed_tools
    assert "mcp__corpus__corpus_search" in options.allowed_tools
    assert "Write" in options.allowed_tools


def test_the_run_can_spawn_under_either_tool_name(fake_sdk, work):
    """The CLI calls it `Task`. Some SDK versions expose it as `Agent`."""
    fake_sdk()
    allowed = roles.options_for(work).allowed_tools
    assert "Task" in allowed and "Agent" in allowed


def test_nothing_in_this_cast_gets_a_shell(fake_sdk, work):
    """Denied once at the top, rather than trusting six tool lists to keep
    omitting it."""
    fake_sdk()
    options = roles.options_for(work)
    assert "Bash" in options.disallowed_tools
    assert "Bash" not in options.allowed_tools


def test_the_permission_mode_denies_rather_than_prompts(fake_sdk, work):
    fake_sdk()
    options = roles.options_for(work)
    assert options.permission_mode == "dontAsk"
    assert options.system_prompt.startswith("You are the research orchestrator")


def test_the_parent_is_kept_from_writing_by_the_hook_not_the_allowlist(fake_sdk, work):
    """`Write` has to be in the allowlist for the writer to use it at all, so
    the parent's restraint is the hook's job."""
    fake_sdk()
    options = roles.options_for(work)
    assert "Write" in options.allowed_tools
    assert call(
        roles.scope_hook(Path(options.cwd), roleplan.plan(None, "research")),
        agent=None,
        path=f"{options.cwd}/sections/s1.md",
    )


def test_the_research_plugin_loads_but_its_orchestrator_skill_does_not(fake_sdk, work):
    """The parent cannot invoke what it was never given.

    `plugins=` is what makes the agent markdown visible, because `cwd` is the
    work directory and not this folder. `skills=` would hand the parent the
    loop as a runnable action, and a second orchestrator is exactly the failure
    Python owning the phases is meant to prevent.
    """
    fake_sdk()
    options = roles.options_for(work)
    assert options.plugins[0] == {"type": "local", "path": str(roles.PLUGIN)}
    assert "research-loop" not in options.skills
    assert all(not name.endswith(":research-loop") for name in options.skills)
    assert options.setting_sources == []


def test_folder_local_image_plugins_are_loaded_after_setup(fake_sdk, work, monkeypatch, tmp_path):
    diagrams = tmp_path / ".cache" / "imagen-diagrams"
    images = tmp_path / ".cache" / "image-gen"
    for plugin in (diagrams, images):
        manifest = plugin / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}\n")
    monkeypatch.setattr(roles, "IMAGEN_DIAGRAMS_PLUGIN", diagrams)
    monkeypatch.setattr(roles, "IMAGE_GEN_PLUGIN", images)
    fake_sdk()

    plugins = roles.options_for(work).plugins

    assert plugins == [
        {"type": "local", "path": str(roles.PLUGIN)},
        {"type": "local", "path": str(diagrams)},
        {"type": "local", "path": str(images)},
    ]
    assert roles.options_for(work).skills == [
        "imagen-diagrams:imagen-diagrams",
        "image-gen:image-gen",
    ]
    assert all(not plugin["path"].startswith(str(Path.home() / ".claude")) for plugin in plugins)


def test_the_parent_prompt_does_not_forbid_a_ghost(fake_sdk, work):
    """A sentence banning something the model was never given teaches the
    reader the wrong lesson about where the fence is."""
    fake_sdk()
    assert "skill" not in roles.options_for(work).system_prompt.lower()


def test_the_folder_declares_its_own_search_boundary(fake_sdk, work, monkeypatch):
    """`.mcp.json` is routinely gitignored, so a clone would silently lose it."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    fake_sdk()
    options = roles.options_for(work)
    assert set(options.mcp_servers) == {"context7", "perplexity", "corpus"}
    assert options.mcp_servers["context7"]["url"].startswith("https://mcp.context7.com")
    assert options.mcp_servers["perplexity"]["env"]["PERPLEXITY_API_KEY"] == "test-key"
    assert options.mcp_servers["perplexity"]["args"] == ["-yq", "@perplexity-ai/mcp-server"]
    # Only these. A broken server in the machine's own config cannot leak in.
    assert options.strict_mcp_config is True


def test_perplexity_is_left_out_when_its_key_is_not_set(fake_sdk, work, monkeypatch):
    """A server with an empty key answers every question with an auth error."""
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.setattr(roles, "DOTENV_PATHS", ())
    fake_sdk()
    assert set(roles.options_for(work).mcp_servers) == {"context7", "corpus"}


def test_a_nearby_dotenv_supplies_the_perplexity_key(fake_sdk, work, monkeypatch, tmp_path):
    near = tmp_path / "near.env"
    far = tmp_path / "far.env"
    near.write_text("PERPLEXITY_API_KEY=near-key\n")
    far.write_text("PERPLEXITY_API_KEY=far-key\n")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.setattr(roles, "DOTENV_PATHS", (near, far))
    fake_sdk()

    options = roles.options_for(work)

    assert options.mcp_servers["perplexity"]["env"]["PERPLEXITY_API_KEY"] == "near-key"


def test_the_exported_perplexity_key_beats_every_dotenv(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("PERPLEXITY_API_KEY=dotenv-key\n")
    monkeypatch.setattr(roles, "DOTENV_PATHS", (dotenv,))
    monkeypatch.setenv("PERPLEXITY_API_KEY", "exported-key")

    assert roles.environment_value("PERPLEXITY_API_KEY") == "exported-key"


def test_the_search_tools_the_roles_hold_match_the_servers_declared(fake_sdk, work, monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    fake_sdk()
    options = roles.options_for(work)
    named = {
        tool.split("__")[1]
        for agent in options.agents.values()
        for tool in agent.tools
        if tool.startswith("mcp__")
    }
    assert named == set(options.mcp_servers)


def test_the_builtin_agents_are_disabled(fake_sdk, work):
    """`general-purpose` ships with filesystem tools. That is the hole."""
    fake_sdk()
    assert roles.options_for(work).env["CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS"] == "1"


def test_cwd_is_the_work_directory_not_the_plugin(fake_sdk, work):
    fake_sdk()
    options = roles.options_for(work)
    assert options.cwd == str(Path(work).resolve())
    assert options.cwd != str(roles.PLUGIN)


def test_max_turns_uses_the_sdk_field_name(fake_sdk, work):
    """`max_turns=` on an AgentDefinition raises TypeError on the real SDK."""
    fake_sdk()
    for agent in roles.options_for(work).agents.values():
        assert agent.maxTurns > 0


def test_every_role_gets_its_prompt_from_the_plugin(fake_sdk, work):
    """A one-line `You are the researcher.` is how a port drifts, silently."""
    fake_sdk()
    agents = roles.options_for(work).agents
    assert set(agents) == {
        "research-outliner",
        "research-outline-judge",
        "research-outline-editor",
        "research-researcher",
        "research-verifier",
        "research-section-judge",
        "research-ledger",
        "research-diagrammer",
        "research-chartist",
        "research-writer",
        "research-judge",
    }
    for name, agent in agents.items():
        assert len(agent.prompt) > 400, name
        assert agent.description, name


def test_a_reader_carries_the_write_tools_as_a_deny_list(fake_sdk, work):
    """The tool list is the allow side. This is the deny side, so a widened
    list still fails closed."""
    fake_sdk()
    agents = roles.options_for(work).agents
    for reader in (
        "research-judge",
        "research-outliner",
        "research-outline-judge",
        "research-diagrammer",
        "research-chartist",
        "research-section-judge",
        "research-ledger",
    ):
        assert agents[reader].disallowedTools == roles.NO_WRITE, reader
    assert agents["research-writer"].disallowedTools == []


def test_the_hook_is_registered_on_every_write_tool(fake_sdk, work):
    fake_sdk()
    hooks = roles.options_for(work).hooks["PreToolUse"]
    assert sorted(h.matcher for h in hooks) == sorted(roles.WRITE_TOOL_NAMES)


def test_the_cost_ceiling_reaches_the_runtime(fake_sdk, work):
    fake_sdk()
    assert roles.options_for(work, max_usd=2.5).max_budget_usd == 2.5


def test_an_agent_file_that_widens_its_tools_is_refused(fake_sdk, work, monkeypatch):
    """Drift in a tool list is how a reader quietly becomes a writer."""
    fake_sdk()
    real = roles.agent_files

    def widened():
        files = real()
        files["research-judge"]["tools"] = [*files["research-judge"]["tools"], "Write"]
        return files

    monkeypatch.setattr(roles, "agent_files", widened)
    with pytest.raises(ValueError, match="role table"):
        roles.options_for(work)


def test_a_missing_agent_file_is_refused(fake_sdk, work, monkeypatch):
    fake_sdk()
    monkeypatch.setattr(roles, "agent_files", dict)
    with pytest.raises(FileNotFoundError, match="research-outliner"):
        roles.options_for(work)
