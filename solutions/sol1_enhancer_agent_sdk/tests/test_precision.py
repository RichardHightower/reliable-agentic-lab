"""SDK precision on top of the Claude Code plugin files.

These tests need the fake SDK fixture from this folder's conftest. Copy this
file into `solutions/sol1_enhancer_agent_sdk/tests/` after applying APPLY.md.
"""

from __future__ import annotations

from pathlib import Path

import load_agents
import roles
from load_agents import PLUGIN, parse_agent_md


def test_plugin_agents_are_the_claude_code_files():
    doer = parse_agent_md(PLUGIN / "agents" / "enhancer-doer.md")
    judge = parse_agent_md(PLUGIN / "agents" / "enhancer-judge.md")
    assert doer["tools"] == ["Read", "Grep", "Glob"]
    assert judge["tools"] == ["Read", "Grep", "Glob"]
    assert "You draft a better ticket" in doer["prompt"]
    assert "You grade one ticket" in judge["prompt"]
    assert "Write" not in doer["tools"]
    assert "Bash" not in judge["tools"]


def test_the_loop_skill_lives_in_the_plugin():
    skill = PLUGIN / "skills" / "enhancer-loop" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert "name: enhancer-loop" in text
    assert "enhancer-judge" in text
    assert "enhancer-doer" in text
    assert (PLUGIN / "skills" / "enhancer-loop" / "scripts" / "check_fields.py").exists()


def test_options_load_plugin_agents_not_one_liners(contract, fake_sdk):
    options = roles.options_for(contract, loop="enhancer")
    assert set(options.agents) == {"enhancer-doer", "enhancer-judge"}
    doer = options.agents["enhancer-doer"]
    judge = options.agents["enhancer-judge"]
    assert "You draft a better ticket" in doer.prompt
    assert "You grade one ticket" in judge.prompt
    assert doer.tools == ["Read", "Grep", "Glob"]
    assert judge.tools == ["Read", "Grep", "Glob"]
    assert doer.maxTurns == 12
    assert judge.background is False
    assert judge.model == "haiku"
    assert "Bash" in (doer.disallowedTools or [])
    assert "Write" in (judge.disallowedTools or [])


def test_the_parent_can_only_spawn_a_subagent(contract, fake_sdk):
    """allowed_tools auto-approves. Combined with dontAsk, everything else is denied.

    The old port put the union of every role's tools on the parent, including
    Write and Bash. The parent then could skip the subagent and write itself.
    """
    options = roles.options_for(contract, loop="enhancer")
    assert options.allowed_tools == ["Agent"]
    assert "Write" in options.disallowed_tools
    assert "Bash" in options.disallowed_tools
    assert options.permission_mode == "dontAsk"


def test_the_plugin_is_loaded_from_this_folder_not_the_target_repo(contract, fake_sdk):
    """cwd is the CRM. Skills live next to this runtime. plugins= is how they meet."""
    options = roles.options_for(contract, loop="enhancer")
    assert options.plugins == [{"type": "local", "path": str(PLUGIN)}]
    assert options.skills == ["ticket-enhancer:enhancer-loop"]
    assert options.cwd == str(contract.repo)
    assert options.cwd != str(PLUGIN)


def test_builtin_general_purpose_is_disabled(contract, fake_sdk):
    options = roles.options_for(contract, loop="enhancer")
    assert options.env["CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS"] == "1"


def test_parent_prompt_forbids_running_the_skill(contract, fake_sdk):
    """Python is the harness. The skill file is for identity, not for the model to run."""
    options = roles.options_for(contract, loop="enhancer")
    assert "Do not invoke the enhancer-loop skill" in options.system_prompt
    assert "Python already owns the loop" in options.system_prompt


def test_max_turns_uses_the_sdk_field_name(contract, fake_sdk):
    """`max_turns=` TypeErrors on real AgentDefinition. Tests hid that."""
    doer = roles.options_for(contract, loop="enhancer").agents["enhancer-doer"]
    assert not hasattr(doer, "max_turns") or getattr(doer, "max_turns", 0) in (0, 12)
    assert doer.maxTurns == 12
