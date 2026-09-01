"""Layer two: the installed runtime applies this folder's configuration.

The rest of the suite fakes `langchain.tools` so the scope logic runs with
nothing installed. Those tests prove what this folder owns. They cannot prove
that Deep Agents honors the harness profile, the permission rules, or the write
tool once a real `@tool` has wrapped it, because no Deep Agents is running when
they pass.

These tests need `deepagents` and `langchain` installed. They still call no
model and spend nothing: every assertion is about configuration the library
builds before a request goes out. Skipped when the runtime is absent, so the
default `task test` stays key-free and clone-free.

Run them with the pinned versions in SPEC.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import roleplan  # noqa: E402
import roles  # noqa: E402

deepagents = pytest.importorskip("deepagents", reason="layer two needs the real runtime")
pytest.importorskip("langchain", reason="layer two needs the real runtime")

pytestmark = pytest.mark.integration


@pytest.fixture
def real_write_tool(target_repo, contract):
    """The doer's write tool, wrapped by the real LangChain `@tool`.

    The `fake_langchain` fixture returns the function unchanged. A real `@tool`
    returns a `BaseTool` and validates arguments before the body runs, so the
    scope check reached here through a different path than the unit tests use.
    """
    doer = roleplan.plan(contract, "enhancer")["doer"]
    return roles.scoped_write_tool(Path(contract.repo), doer)


def _call(tool, **kwargs) -> str:
    """Invoke whatever `@tool` produced, BaseTool or plain function."""
    if hasattr(tool, "invoke"):
        return tool.invoke(kwargs)
    return tool(**kwargs)


def test_the_real_tool_decorator_produces_a_structured_tool(real_write_tool):
    """A `BaseTool`, not a bare function. The unit tests cannot see this."""
    assert hasattr(real_write_tool, "invoke")
    assert real_write_tool.name == "write_doer"


def test_the_scope_check_survives_the_real_tool_wrapper(real_write_tool, target_repo):
    """The refusal has to come from the body, through the real argument path."""
    (target_repo / "app").mkdir(parents=True, exist_ok=True)
    (target_repo / "app" / "models.py").write_text("real code", encoding="utf-8")

    answer = _call(real_write_tool, path="app/models.py", content="print()")

    assert answer.startswith("REFUSED")
    assert (target_repo / "app" / "models.py").read_text(encoding="utf-8") == "real code"


def test_the_traversal_is_refused_under_the_real_wrapper(real_write_tool, target_repo):
    """`tickets/../app/x.py` matches `tickets/**` as text and lands in `app/`."""
    (target_repo / "app").mkdir(parents=True, exist_ok=True)
    (target_repo / "app" / "models.py").write_text("real code", encoding="utf-8")

    answer = _call(real_write_tool, path="tickets/../app/models.py", content="print()")

    assert answer.startswith("REFUSED")
    assert (target_repo / "app" / "models.py").read_text(encoding="utf-8") == "real code"


def test_a_turn_narrows_the_row_under_the_real_wrapper(real_write_tool, target_repo):
    """The row allows `tickets/**`. One turn allows one candidate."""
    (target_repo / "tickets").mkdir(parents=True, exist_ok=True)
    (target_repo / "tickets" / "T001.md").write_text("REAL TICKET", encoding="utf-8")

    with roles.write_allow(["tickets/T001.enhancer-candidate.md"]):
        allowed = _call(real_write_tool, path="tickets/T001.enhancer-candidate.md", content="draft")
        refused = _call(real_write_tool, path="tickets/T001.md", content="clobbered")

    assert allowed == "wrote tickets/T001.enhancer-candidate.md"
    assert refused.startswith("REFUSED")
    assert (target_repo / "tickets" / "T001.md").read_text(encoding="utf-8") == "REAL TICKET"


def test_the_permission_rules_become_real_filesystem_permissions(contract):
    """The unit tests read plain dicts. The runtime needs real objects.

    A dict that no longer matches `FilesystemPermission`'s fields is an API
    change this folder has to notice, and layer one cannot see it.
    """
    from deepagents import FilesystemPermission

    for spec in roles.subagents_for(contract, loop="enhancer"):
        built = [FilesystemPermission(**rule) for rule in spec["permissions"]]
        assert built, f"{spec['name']} carries no permission rule"
        assert built[-1].mode == "deny", f"{spec['name']} does not end in a deny"


def test_the_harness_profile_registers_under_this_model_key(contract):
    """Fence three is a registration. A key the library does not resolve is no fence.

    `build_agent` registers the profile as a side effect, so this asserts the
    thing the article claims: the parent's built-in write tools are excluded and
    the default general-purpose subagent is off, for THIS model string.
    """
    from deepagents.profiles.harness.harness_profiles import _get_harness_profile

    roles.build_agent(contract)
    profile = _get_harness_profile(roles.DEFAULT_MODEL)

    assert profile is not None, f"no harness profile resolves for {roles.DEFAULT_MODEL}"
    assert roles.ORCHESTRATOR_EXCLUDED_TOOLS <= set(profile.excluded_tools)
    assert profile.general_purpose_subagent is not None
    assert profile.general_purpose_subagent.enabled is False


def test_the_agent_builds_against_the_pinned_runtime(contract):
    """API drift is the failure this layer exists to catch.

    Building touches `CompositeBackend`, `FilesystemBackend(virtual_mode=...)`,
    `HarnessProfile`, `GeneralPurposeSubagentProfile`, `register_harness_profile`,
    and `create_deep_agent`. A renamed argument in any of them fails here and
    nowhere in layer one.
    """
    agent = roles.build_agent(contract)

    assert hasattr(agent, "invoke")
    assert "tools" in agent.nodes
