"""The Deep Agents port. All three fencing layers, with no SDK installed."""

from __future__ import annotations

import roleplan
import roles

LOOP = "fixer"


def _by_name(subagents):
    return {agent["name"]: agent for agent in subagents}


def _tool_names(spec):
    return [tool.__name__ for tool in spec["tools"]]


# -- layer one. The cast and its tool lists --------------------------------


def test_the_cast_is_exactly_the_fixer_roles(contract):
    """Three roles, by value. A port that grows a fourth has stopped being the
    loop it claims to be, and it grows one silently."""
    assert tuple(roleplan.plan(contract, LOOP)) == ("orchestrator", "code_implementer", "judge")


def test_the_orchestrator_gets_no_subagent(contract, fake_langchain):
    assert set(_by_name(roles.subagents_for(contract, loop=LOOP))) == {
        "code-implementer",
        "judge",
    }


def test_the_judge_holds_only_the_reader(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop=LOOP))["judge"]
    assert _tool_names(judge) == ["read_file"]


def test_the_orchestrator_holds_no_write_tool(contract):
    """It delegates and counts. It never edits, in any runtime."""
    orchestrator = roleplan.plan(contract, LOOP)["orchestrator"]
    assert orchestrator.can_write is False
    assert orchestrator.tools == ("Task",)


def test_the_judge_holds_no_write_path(contract):
    judge = roleplan.plan(contract, LOOP)["judge"]
    assert judge.can_write is False
    assert judge.allow == ()


def test_the_code_implementer_holds_a_reader_and_a_write_tool(contract, fake_langchain):
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    assert _tool_names(coder) == ["read_file", "write"]


def test_each_subagent_carries_its_purpose(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop=LOOP))["judge"]
    assert judge["description"] == roleplan.PURPOSE["judge"]
    assert "judge" in judge["system_prompt"]


# -- layer two. The path check inside the write tool -----------------------


def test_the_write_tool_writes_inside_the_scope(contract, target_repo, fake_langchain):
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    write = coder["tools"][1]

    assert write("app/due.py", "code") == "wrote app/due.py"
    assert (target_repo / "app" / "due.py").read_text(encoding="utf-8") == "code"


def test_the_write_tool_refuses_the_tests(contract, target_repo, fake_langchain):
    """The first thing a fixer under pressure reaches for is the failing test."""
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    write = coder["tools"][1]

    answer = write("tests/test_due.py", "def test_due(): pass")

    assert answer.startswith("REFUSED")
    assert "app/**" in answer
    assert "tests/test_due.py" in answer
    assert not (target_repo / "tests" / "test_due.py").exists()


def test_the_write_tool_refuses_a_path_outside_the_repo(contract, target_repo, fake_langchain):
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    assert coder["tools"][1]("../escape.py", "x").startswith("REFUSED")
    assert not (target_repo.parent / "escape.py").exists()


def test_the_refusal_is_a_sentence_not_an_exception(contract, fake_langchain):
    """An unformatted traceback in an agent's context starts a retry loop. A
    short sentence that names the scope changes the next action."""
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    answer = coder["tools"][1]("tests/test_due.py", "x")
    assert isinstance(answer, str)
    assert answer.endswith("is outside that scope.")


def test_the_reader_reports_a_missing_file_instead_of_raising(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop=LOOP))["judge"]
    assert judge["tools"][0]("nope.py") == "no such file: nope.py"


def test_the_reader_returns_the_file(contract, target_repo, fake_langchain):
    (target_repo / "app" / "due.py").write_text("hello", encoding="utf-8")
    judge = _by_name(roles.subagents_for(contract, loop=LOOP))["judge"]
    assert judge["tools"][0]("app/due.py") == "hello"


# -- layer three. The declarative permissions ------------------------------


def test_the_judge_denies_every_write(contract, fake_langchain):
    judge = _by_name(roles.subagents_for(contract, loop=LOOP))["judge"]
    assert judge["permissions"] == [
        {"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}
    ]


def test_permissions_put_the_deny_list_first(contract, fake_langchain):
    """First match wins. Put the allow list first and an overlapping deny
    pattern never fires, which is how `tests/**` becomes writable again."""
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    rules = coder["permissions"]

    assert [rule["mode"] for rule in rules] == ["deny", "allow", "deny"]
    assert rules[0]["paths"] == ["tests/**", "/tests/**"]
    assert rules[1]["paths"] == ["app/**", "/app/**"]
    assert rules[-1] == {"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}


def test_permissions_carry_both_spellings_of_a_path(contract, fake_langchain):
    """The virtual filesystem asks for `/app/x.py`. The role table writes
    `app/x.py`. A rule with one spelling matches half the requests."""
    coder = _by_name(roles.subagents_for(contract, loop=LOOP))["code-implementer"]
    allow = coder["permissions"][1]["paths"]
    assert "app/**" in allow and "/app/**" in allow


def test_a_role_with_no_deny_list_still_ends_in_a_deny():
    role = roleplan.RolePlan(
        name="code_implementer",
        purpose="x",
        tools=("Read", "Write"),
        allow=("app/**",),
    )
    rules = roles.permission_rules(role)
    assert [rule["mode"] for rule in rules] == ["allow", "deny"]


# -- the harness fence, as `create_deep_agent` receives it ------------------


def test_build_agent_disables_the_general_purpose_subagent(
    contract, fake_langchain, fake_deepagents
):
    """The default general-purpose subagent ships with the harness filesystem
    tools. Leaving it enabled is how a carefully scoped agent writes anywhere,
    and every tool list above it stops meaning anything."""
    roles.build_agent(contract, loop=LOOP)

    profile = fake_deepagents["harness_profile"]
    assert profile.general_purpose_subagent.enabled is False


def test_build_agent_hides_the_built_in_write_tools(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract, loop=LOOP)

    excluded = fake_deepagents["harness_profile"].excluded_tools
    assert {"write_file", "edit_file", "delete", "execute"} <= set(excluded)
    assert fake_deepagents["harness_model"] == roles.DEFAULT_MODEL


def test_build_agent_mounts_the_repo_as_a_virtual_filesystem(
    contract, fake_langchain, fake_deepagents
):
    """Virtual mode fences the built-in filesystem tools.

    It does not fence `read_file` or the scoped write tool, which this folder
    wrote. Those carry their own containment check, pinned in test_adapter.py.
    """
    roles.build_agent(contract, loop=LOOP)

    backend = fake_deepagents["backend"]
    assert backend.virtual_mode is True
    assert backend.root_dir == str(contract.repo.resolve())


def test_build_agent_denies_the_orchestrator_every_write(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract, loop=LOOP)

    rules = fake_deepagents["permissions"]
    assert [rule.mode for rule in rules] == ["deny"]
    assert rules[0].paths == ["/**", "**"]


def test_build_agent_gives_every_subagent_permissions_ending_in_a_deny(
    contract, fake_langchain, fake_deepagents
):
    assert roles.build_agent(contract, loop=LOOP) == "agent"

    subagents = fake_deepagents["subagents"]
    assert set(_by_name(subagents)) == {"code-implementer", "judge"}
    for spec in subagents:
        assert spec["permissions"], spec["name"]
        assert spec["permissions"][-1].mode == "deny", spec["name"]
        assert spec["permissions"][-1].paths == ["/**", "**"], spec["name"]


def test_build_agent_tells_the_orchestrator_not_to_write(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract, loop=LOOP)
    assert "write nothing" in fake_deepagents["system_prompt"].lower()


def test_a_role_the_target_repo_never_scoped_gets_no_allow_rule():
    """The role table falls back to "writes nothing" for an undeclared role.
    An allow rule with an empty path list would read like a grant."""
    role = roleplan.RolePlan(
        name="code_implementer",
        purpose="x",
        tools=("Read", "Write"),
        deny=("**",),
    )
    rules = roles.permission_rules(role)
    assert [rule["mode"] for rule in rules] == ["deny", "deny"]
