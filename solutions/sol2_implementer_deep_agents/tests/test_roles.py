"""Judge has no write tool. Code implementer cannot write tests.

The last block checks the third fencing layer: the harness itself. A tool list
per subagent is worth nothing while the default general-purpose subagent is
still there holding the built-in filesystem tools.
"""

from __future__ import annotations

import gates
import implementer
import roleplan
import roles


def _by_name(subagents):
    return {agent["name"]: agent for agent in subagents}


def test_cast_names(contract, fake_langchain):
    names = set(_by_name(roles.subagents_for(contract)))
    assert names == {"planner", "test-implementer", "code-implementer", "judge"}


def test_judge_is_read_only(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract))["judge"]
    assert [t.__name__ for t in judge["tools"]] == ["read_file"]


def test_code_implementer_refuses_tests(contract, target_repo, fake_langchain):
    coder = _by_name(roles.subagents_for(contract))["code-implementer"]
    write = coder["tools"][1]
    answer = write("tests/test_due.py", "def test_x(): pass")
    assert answer.startswith("REFUSED")
    assert not (target_repo / "tests" / "test_due.py").exists()


def test_test_implementer_writes_tests(contract, target_repo, fake_langchain):
    tester = _by_name(roles.subagents_for(contract))["test-implementer"]
    write = tester["tools"][1]
    assert write("tests/test_due.py", "ok") == "wrote tests/test_due.py"
    assert (target_repo / "tests" / "test_due.py").read_text() == "ok"


def test_red_gate_needs_new_failing_ids():
    assert implementer._new_test_ids({"old"}, {"old", "new"}) == {"new"}
    assert implementer._new_test_ids({"old"}, {"old"}) == set()


def test_same_signature_escalates():
    d = gates.decide(
        passed=False,
        iteration=2,
        budget=3,
        signature=("coverage_floor",),
        previous_signature=("coverage_floor",),
    )
    assert d.gate == gates.ESCALATE
    assert d.repeat_failure


def test_build_agent_passes_run_tests(contract, fake_langchain, fake_deepagents):
    assert roles.build_agent(contract) == "agent"
    assert fake_deepagents["tools"][0].__name__ == "run_tests"
    assert "judge" in _by_name(fake_deepagents["subagents"])


def test_permissions_deny_a_reader_everything(contract):
    rules = roles.permission_rules(roleplan.plan(contract)["judge"])
    assert rules == [roles.DENY_EVERY_WRITE]


def test_permissions_put_deny_before_allow(contract):
    """First match wins, so a role's deny list must come first or its allow
    list silently wins on an overlap."""
    rules = roles.permission_rules(roleplan.plan(contract)["code_implementer"])
    assert rules[0]["mode"] == "deny"
    assert "tests/**" in rules[0]["paths"]
    assert rules[1]["mode"] == "allow"
    assert rules[-1] == roles.DENY_EVERY_WRITE


def test_build_agent_fences_the_harness(contract, fake_langchain, fake_deepagents):
    """Layer three. Without this, the default general-purpose subagent walks
    around every tool list above it."""
    roles.build_agent(contract)

    profile = fake_deepagents["harness_profile"]
    assert profile.general_purpose_subagent.enabled is False
    assert "write_file" in profile.excluded_tools
    assert "execute" in profile.excluded_tools

    assert fake_deepagents["backend"].virtual_mode is True

    orchestrator = fake_deepagents["permissions"]
    assert [rule.mode for rule in orchestrator] == ["deny"]


def test_build_agent_passes_every_subagent_permission(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract)
    for spec in fake_deepagents["subagents"]:
        assert spec["permissions"], spec["name"]
        assert spec["permissions"][-1].mode == "deny"
