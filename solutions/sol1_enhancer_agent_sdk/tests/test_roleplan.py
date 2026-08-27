"""The role table this port reads. Nothing here needs an SDK.

If the table and a runtime ever disagree, the runtime is wrong. These checks are
what make that statement testable inside this folder, without the target CRM
repo cloned and without `loops/` on the path.
"""

from __future__ import annotations

import pytest
import roleplan


def test_the_enhancer_cast_is_orchestrator_doer_judge(contract):
    """A port that invents a fourth role is a port that drifts from the loop."""
    assert list(roleplan.plan(contract, "enhancer")) == ["orchestrator", "doer", "judge"]


def test_the_judge_holds_no_write_tool(contract):
    """The one rule that must survive every port."""
    judge = roleplan.plan(contract, "enhancer")["judge"]
    assert judge.can_write is False, "a judge that can write can grade its own homework"
    assert not set(judge.tools) & set(roleplan.WRITE_TOOLS)


def test_the_orchestrator_holds_no_write_tool(contract):
    assert roleplan.plan(contract, "enhancer")["orchestrator"].can_write is False


def test_the_doer_can_write_and_declares_a_scope(contract):
    doer = roleplan.plan(contract, "enhancer")["doer"]
    assert doer.can_write is True
    assert doer.allow, "a role holding Edit with an empty allow list writes nothing at all"


def test_the_doer_falls_back_to_tickets_when_loop_yml_is_silent(contract):
    """The fixture `.loop.yml` declares the implementer's roles, never `doer`.

    A target repo has never heard of the enhancer's cast, so the fallback is
    what fires in practice.
    """
    assert "doer" not in contract.config["roles"]
    assert roleplan.plan(contract, "enhancer")["doer"].allow == ("tickets/**",)


def test_a_declared_scope_beats_the_fallback(contract):
    """`.loop.yml` wins when it does mention the role."""
    contract.config["roles"]["doer"] = {
        "write_allow": ["docs/**"],
        "write_deny": ["docs/secret/**"],
    }
    doer = roleplan.plan(contract, "enhancer")["doer"]
    assert doer.allow == ("docs/**",)
    assert doer.deny == ("docs/secret/**",)


def test_a_role_declared_empty_is_not_the_same_as_never_mentioned(contract):
    """Declaring `write_allow: []` means "writes nothing", not "use the fallback"."""
    contract.config["roles"]["doer"] = {"write_allow": [], "write_deny": []}
    assert roleplan.plan(contract, "enhancer")["doer"].allow == ()


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_the_judge_holds_no_write_tool_in_every_loop(contract, loop):
    assert roleplan.plan(contract, loop)["judge"].can_write is False


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_every_writing_role_declares_a_scope(contract, loop):
    """A role holding Edit with an empty allow list looks scoped and does nothing."""
    for role in roleplan.plan(contract, loop).values():
        if role.can_write:
            assert role.allow, f"{loop}/{role.name} can write but may write nothing"


def test_an_unknown_loop_is_rejected(contract):
    with pytest.raises(ValueError, match="unknown loop"):
        roleplan.plan(contract, "not-a-loop")


def test_the_research_cast_needs_no_contract():
    """Research runs against a question. There is no repo and no `.loop.yml`."""
    roles = roleplan.plan(None, "research")
    assert roles["judge"].can_write is False
    assert roles["writer"].can_write is True
    assert roles["writer"].allow == ("brief.md", "work/research/**")


def test_the_table_prints_no_in_the_judges_writes_column(contract):
    text = roleplan.table(roleplan.plan(contract, "enhancer"))
    lines = {line.split()[0]: line for line in text.splitlines()[1:]}
    assert lines["judge"].split()[1] == "no"
    assert lines["doer"].split()[1] == "yes"


def test_the_table_shows_a_denied_suffix(contract):
    text = roleplan.table(roleplan.plan(contract, "implementer"))
    assert "denied: tests/**" in text


def test_the_table_says_nothing_for_a_role_with_no_allow_list(contract):
    assert "nothing" in roleplan.table(roleplan.plan(contract, "enhancer"))
