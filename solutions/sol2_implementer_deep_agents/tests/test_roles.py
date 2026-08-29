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

    assert fake_deepagents["backend"].default.virtual_mode is True

    orchestrator = fake_deepagents["permissions"]
    assert [rule.mode for rule in orchestrator] == ["deny"]


def test_build_agent_passes_every_subagent_permission(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract)
    for spec in fake_deepagents["subagents"]:
        assert spec["permissions"], spec["name"]
        assert spec["permissions"][-1].mode == "deny"


# -- what the judge may say -------------------------------------------------


def test_the_judge_carries_a_response_format(contract, fake_langchain):
    """Without it the parent receives the subagent's last message text as-is.
    With it the parent always gets valid JSON matching this schema."""
    import roles  # noqa: PLC0415

    judge = next(s for s in roles.subagents_for(contract, "implementer") if s["name"] == "judge")
    assert judge["response_format"] is roles.JUDGE_RESPONSE


def test_only_the_judge_carries_one(contract, fake_langchain):
    import roles  # noqa: PLC0415

    for spec in roles.subagents_for(contract, "implementer"):
        if spec["name"] != "judge":
            assert "response_format" not in spec, spec["name"]


def test_the_judge_cannot_name_a_gate():
    """`done` is the verdict and belongs here. A gate is not a verdict, it is
    the decision Python makes from one, and a stop condition a model can phrase
    its way past is not a stop condition."""
    import roles  # noqa: PLC0415

    properties = roles.JUDGE_RESPONSE["properties"]
    assert set(properties) == {"done", "why"}
    for banned in ("gate", "pass", "retry", "escalate", "rubric", "score", "ready"):
        assert banned not in properties


def test_the_schema_refuses_extra_properties():
    """`additionalProperties: False` is what stops the judge adding `gate`
    anyway."""
    import roles  # noqa: PLC0415

    assert roles.JUDGE_RESPONSE["additionalProperties"] is False
    assert roles.JUDGE_RESPONSE["required"] == ["done", "why"]


def test_the_description_tells_the_judge_what_not_to_decide():
    import roles  # noqa: PLC0415

    text = roles.JUDGE_RESPONSE["description"].lower()
    assert "do not name a gate" in text
    assert "pass, retry, or escalate" in text


# -- skills and memory ------------------------------------------------------


def test_each_role_with_a_skill_directory_gets_the_mount(contract, fake_langchain):
    specs = {s["name"]: s for s in roles.subagents_for(contract)}
    assert specs["planner"]["skills"] == ["/skills/planner/"]
    assert specs["test-implementer"]["skills"] == ["/skills/test_implementer/"]
    assert specs["code-implementer"]["skills"] == ["/skills/code_implementer/"]
    assert specs["judge"]["skills"] == ["/skills/judge/"]


def test_the_mount_path_follows_the_directory_not_the_subagent_name(contract, fake_langchain):
    """The directory is `code_implementer`. The subagent is `code-implementer`.
    Mounting the subagent's name would point at a directory that is not there."""
    spec = next(s for s in roles.subagents_for(contract) if s["name"] == "code-implementer")
    assert "_" in spec["skills"][0]
    assert (roles.SKILLS_DIR / "code_implementer").is_dir()


def test_the_skill_body_is_not_also_pasted_into_the_prompt(contract, fake_langchain):
    """Mount or inline, not both.

    Deep Agents loads a skill in two levels: metadata in the system prompt at
    startup, instructions only when the skill is invoked. Pasting the body into
    `system_prompt` as well makes it always resident, which is the cost the
    mount exists to avoid.
    """
    body = (roles.SKILLS_DIR / "judge" / "SKILL.md").read_text(encoding="utf-8")
    distinctive = "You read the ticket, the plan, the diff"
    assert distinctive in body

    spec = next(s for s in roles.subagents_for(contract) if s["name"] == "judge")
    assert distinctive not in spec["system_prompt"]
    assert spec["skills"] == ["/skills/judge/"]


def test_build_agent_mounts_skills_and_memory(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract)
    assert fake_deepagents["skills"] == ["/skills/"]
    assert fake_deepagents["memory"] == ["/memory/AGENTS.md"]

    routes = fake_deepagents["backend"].routes
    assert set(routes) == {"/skills/", "/memory/"}
    assert all(route.virtual_mode for route in routes.values())


def test_memory_routes_at_a_subdirectory_not_the_solution_folder(
    contract, fake_langchain, fake_deepagents
):
    """Routing `/memory/` at the folder itself would put roles.py,
    write_scope.py, and tests/ inside the agent's reach, in the one folder whose
    lesson is that the coder may not write tests/**."""
    roles.build_agent(contract)

    from pathlib import Path  # noqa: PLC0415

    root = Path(fake_deepagents["backend"].routes["/memory/"].root_dir)
    assert root.name == "memory"
    assert not (root / "roles.py").exists()
    assert not (root / "tests").exists()
    assert (root / "AGENTS.md").exists()
