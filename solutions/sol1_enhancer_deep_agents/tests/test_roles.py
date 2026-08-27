"""The Deep Agents port. One tool list per subagent, scope inside the tool."""

from __future__ import annotations

import sys
import types

import roles


def _by_name(subagents):
    return {agent["name"]: agent for agent in subagents}


def test_the_orchestrator_gets_no_subagent(contract, fake_langchain):
    assert set(_by_name(roles.subagents_for(contract, loop="enhancer"))) == {"doer", "judge"}


def test_the_judge_holds_only_the_reader(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert [tool.__name__ for tool in judge["tools"]] == ["read_file"]


def test_the_doer_holds_a_reader_and_a_write_tool(contract, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    assert [tool.__name__ for tool in doer["tools"]] == ["read_file", "write"]


def test_each_subagent_carries_its_purpose(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert judge["description"] == judge["system_prompt"].split(". ", 1)[1]
    assert "judge" in judge["system_prompt"]


def test_the_write_tool_writes_inside_the_scope(contract, target_repo, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    write = doer["tools"][1]

    assert write("tickets/7.md", "body") == "wrote tickets/7.md"
    assert (target_repo / "tickets" / "7.md").read_text(encoding="utf-8") == "body"


def test_the_write_tool_refuses_outside_the_scope(contract, target_repo, fake_langchain):
    doer = _by_name(roles.subagents_for(contract, loop="enhancer"))["doer"]
    write = doer["tools"][1]

    answer = write("app/x.py", "print()")

    assert answer.startswith("REFUSED")
    assert "tickets/**" in answer
    assert not (target_repo / "app" / "x.py").exists()


def test_the_reader_reports_a_missing_file_instead_of_raising(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert judge["tools"][0]("nope.md") == "no such file: nope.md"


def test_the_reader_returns_the_file(contract, target_repo, fake_langchain):
    (target_repo / "tickets" / "1.md").write_text("hello", encoding="utf-8")
    judge = _by_name(roles.subagents_for(contract, loop="enhancer"))["judge"]
    assert judge["tools"][0]("tickets/1.md") == "hello"


def test_build_agent_hands_the_subagents_to_deepagents(contract, monkeypatch, fake_langchain):
    seen = {}

    def create_deep_agent(model, subagents):
        seen["model"] = model
        seen["subagents"] = subagents
        return "agent"

    module = types.ModuleType("deepagents")
    module.create_deep_agent = create_deep_agent
    monkeypatch.setitem(sys.modules, "deepagents", module)

    assert roles.build_agent(contract, loop="enhancer") == "agent"
    assert seen["model"] == "anthropic:claude-sonnet-5"
    assert set(_by_name(seen["subagents"])) == {"doer", "judge"}
