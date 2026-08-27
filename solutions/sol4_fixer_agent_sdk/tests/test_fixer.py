from __future__ import annotations

import subprocess
import types
from pathlib import Path
from types import SimpleNamespace

import fixer
import gates
import loop
import roles

ROOT = Path(__file__).resolve().parents[1]


def test_failure_summary_names_tests():
    run = SimpleNamespace(
        junit=SimpleNamespace(failed_ids={"tests.test_x::test_y"}),
        output="ValueError: boom",
    )
    text = loop.summarize_failure(run)
    assert "test_y" in text
    assert "ValueError" in text


def test_same_failing_ids_escalate():
    d = gates.decide(
        passed=False,
        iteration=2,
        budget=3,
        signature=("a",),
        previous_signature=("a",),
    )
    assert d.gate == gates.ESCALATE


def test_hook_denies_test_write(contract, target_repo):
    coder = [r for r in roles.plan(contract, "fixer").values() if r.name == "code_implementer"][0]
    hook = roles.scope_hook(target_repo, coder)

    async def go():
        return await hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target_repo / "tests" / "test_x.py")},
            },
            "1",
            None,
        )

    import asyncio

    out = asyncio.run(go())
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_app_write(contract, target_repo):
    coder = [r for r in roles.plan(contract, "fixer").values() if r.name == "code_implementer"][0]
    hook = roles.scope_hook(target_repo, coder)

    async def go():
        return await hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target_repo / "app" / "main.py")},
            },
            "1",
            None,
        )

    import asyncio

    out = asyncio.run(go())
    assert out == {}


def test_options_use_accept_edits(contract, monkeypatch):
    seen = {}

    class AgentDefinition:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class HookMatcher:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    mod = types.ModuleType("claude_agent_sdk")
    mod.AgentDefinition = AgentDefinition
    mod.HookMatcher = HookMatcher
    mod.ClaudeAgentOptions = ClaudeAgentOptions
    monkeypatch.setitem(__import__("sys").modules, "claude_agent_sdk", mod)
    roles.options_for(contract, loop="fixer")
    assert seen["permission_mode"] == "acceptEdits"
    assert "Write" in seen["allowed_tools"] or "Edit" in seen["allowed_tools"]


def test_no_loops_import():
    hit = subprocess.run(
        ["grep", "-rn", r"^from loops\|^import loops\|^from solutions import", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [ln for ln in (hit.stdout or "").splitlines() if "/tests/" not in ln]
    assert lines == []


def test_table_only():
    proc = subprocess.run(
        ["python3", "loop.py", "--table-only", "--repo", "/tmp/no-such-crm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "judge" in proc.stdout
