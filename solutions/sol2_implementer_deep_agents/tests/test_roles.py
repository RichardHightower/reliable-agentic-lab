"""Judge has no write tool. Code implementer cannot write tests."""

from __future__ import annotations

import sys
import types

import roles
import gates
import implementer


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


def test_build_agent_passes_run_tests(contract, monkeypatch, fake_langchain):
    seen = {}

    def create_deep_agent(model, tools, subagents):
        seen["tools"] = tools
        seen["subagents"] = subagents
        return "agent"

    module = types.ModuleType("deepagents")
    module.create_deep_agent = create_deep_agent
    monkeypatch.setitem(sys.modules, "deepagents", module)
    assert roles.build_agent(contract) == "agent"
    assert seen["tools"][0].__name__ == "run_tests"
    assert "judge" in _by_name(seen["subagents"])
