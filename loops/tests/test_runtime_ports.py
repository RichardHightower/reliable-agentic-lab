"""The three runtimes must enforce the same role table.

None of these tests needs the Claude Agent SDK or Deep Agents installed. They
check the translation, not the call. A port that drifts from `.loop.yml` is a
port that teaches the wrong lesson, and it drifts silently.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from loops.contract import Contract
from loops.roles import build
from solutions import roleplan
from solutions.agent_sdk import roles as sdk_roles

TARGET = Path(__file__).resolve().parents[2] / "work" / "northwind-field-crm"

pytestmark = pytest.mark.skipif(
    not TARGET.exists(), reason="run `task setup` to clone the target repo"
)


@pytest.fixture
def contract() -> Contract:
    return Contract(TARGET)


def test_the_judge_holds_no_write_tool(contract):
    """The one rule that must survive every port."""
    assert roleplan.plan(contract)["judge"].can_write is False


def test_the_orchestrator_holds_no_write_tool(contract):
    assert roleplan.plan(contract)["orchestrator"].can_write is False


def test_the_two_doers_have_disjoint_scopes(contract):
    roles = roleplan.plan(contract)
    tests = set(roles["test_implementer"].allow)
    code = set(roles["code_implementer"].allow)
    assert tests & code == set(), "a shared path is a shared way to fake green"
    assert "tests/**" in roles["code_implementer"].deny


def test_the_plan_matches_the_in_process_roles(contract):
    """The table and `loops/roles.py` read the same `.loop.yml`."""
    planned = roleplan.plan(contract)
    live = build(contract)
    for name in ("planner", "test_implementer", "code_implementer"):
        assert tuple(live[name].scope.allow) == planned[name].allow
        assert tuple(live[name].scope.deny) == planned[name].deny


def _hook_result(contract, role_name: str, relative: str) -> dict:
    role = roleplan.plan(contract)[role_name]
    check = sdk_roles.scope_hook(Path(contract.repo), role)
    return asyncio.run(
        check(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(Path(contract.repo) / relative)},
            },
            "tool-use-id",
            None,
        )
    )


def test_the_sdk_hook_denies_a_write_outside_scope(contract):
    result = _hook_result(contract, "code_implementer", "tests/test_anything.py")
    # The full shape matters. A typo anywhere in it fails open.
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "outside that scope" in output["permissionDecisionReason"]


def test_the_sdk_hook_allows_a_write_inside_scope(contract):
    assert _hook_result(contract, "code_implementer", "app/models.py") == {}


def test_the_sdk_hook_ignores_a_read(contract):
    role = roleplan.plan(contract)["code_implementer"]
    check = sdk_roles.scope_hook(Path(contract.repo), role)
    result = asyncio.run(
        check({"tool_name": "Read", "tool_input": {"file_path": "tests/x.py"}}, "id", None)
    )
    assert result == {}


def test_a_path_outside_the_repo_is_denied(contract):
    """Fail closed. A path that matches no allow rule is out of scope, and a
    path outside the repo matches no allow rule for any role."""
    role = roleplan.plan(contract)["code_implementer"]
    check = sdk_roles.scope_hook(Path(contract.repo), role)
    result = asyncio.run(
        check({"tool_name": "Write", "tool_input": {"file_path": "/etc/hosts"}}, "id", None)
    )
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "outside the target repo" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_role_table_renders(contract):
    text = roleplan.table(roleplan.plan(contract))
    assert "code_implementer" in text
    assert "denied: tests/**" in text
