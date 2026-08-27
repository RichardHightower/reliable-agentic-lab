"""The three runtimes must enforce the same role table.

None of these tests needs the Claude Agent SDK or Deep Agents installed. They
check the translation, not the call. A port that drifts from `.loop.yml` is a
port that teaches the wrong lesson, and it drifts silently.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
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


# --- every loop, not only the implementer ---------------------------------
#
# The four loops run four different casts. A port that only ever sees the
# implementer's five roles will look correct and be wrong the first time
# somebody points it at the fixer.

ROOT = Path(__file__).resolve().parents[2]
SOLUTIONS = ROOT / "solutions"
LOOP_KEYS = tuple(roleplan.LOOPS)


@pytest.mark.parametrize("loop", LOOP_KEYS)
def test_the_judge_holds_no_write_tool_in_every_loop(contract, loop):
    assert roleplan.plan(contract, loop)["judge"].can_write is False


@pytest.mark.parametrize("loop", LOOP_KEYS)
def test_the_orchestrator_holds_no_write_tool_in_every_loop(contract, loop):
    assert roleplan.plan(contract, loop)["orchestrator"].can_write is False


@pytest.mark.parametrize("loop", LOOP_KEYS)
def test_every_writing_role_declares_a_scope(contract, loop):
    """A role holding Edit with an empty allow list can write nothing at all.

    That is the shape of a port that looks scoped and silently does nothing, so
    it is worth failing on rather than discovering during a demo.
    """
    for role in roleplan.plan(contract, loop).values():
        if role.can_write:
            assert role.allow, f"{loop}/{role.name} can write but may write nothing"


@pytest.mark.parametrize("loop", LOOP_KEYS)
def test_the_sdk_hook_denies_an_out_of_scope_write_in_every_loop(contract, loop):
    for role in roleplan.plan(contract, loop).values():
        if not role.can_write:
            continue
        check = sdk_roles.scope_hook(Path(contract.repo), role)
        result = asyncio.run(
            check(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": str(Path(contract.repo) / "etc/nope.txt")},
                },
                "id",
                None,
            )
        )
        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", f"{loop}/{role.name} let an out-of-scope write through"


def test_an_unknown_loop_is_rejected(contract):
    with pytest.raises(ValueError, match="unknown loop"):
        roleplan.plan(contract, "not-a-loop")


def test_the_research_cast_needs_no_contract():
    """Research runs against a question. There is no repo and no `.loop.yml`."""
    roles = roleplan.plan(None, "research")
    assert roles["judge"].can_write is False
    assert roles["writer"].can_write is True


def _load_port(folder: str, stub_file: str):
    """Import one generated port the way it imports itself, from its folder."""
    path = SOLUTIONS / folder / stub_file
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(f"port_{folder}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(path.parent))


PORTS = [
    (f"sol{n}_{slug}_{runtime}", stub, loop)
    for n, slug, stub, loop in (
        (1, "enhancer", "loop.py", "enhancer"),
        (2, "implementer", "harness.py", "implementer"),
        (3, "research", "loop.py", "research"),
        (4, "fixer", "loop.py", "fixer"),
    )
    for runtime in ("agent_sdk", "deep_agents")
]


@pytest.mark.parametrize("folder,stub_file,loop", PORTS)
def test_every_port_reads_the_shared_table(contract, folder, stub_file, loop):
    """The port names a loop, and its cast is the table's cast. Nothing local."""
    module = _load_port(folder, stub_file)
    assert loop == module.LOOP
    target = contract if loop != "research" else None
    assert module.cast(target) == roleplan.plan(target, loop)
