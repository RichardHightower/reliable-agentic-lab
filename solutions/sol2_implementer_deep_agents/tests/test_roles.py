"""Judge has no write tool. Code implementer cannot write tests.

The last block checks the third fencing layer: the harness itself. A tool list
per subagent is worth nothing while the default general-purpose subagent is
still there holding the built-in filesystem tools.
"""

from __future__ import annotations

import inspect

import conftest
import gates
import implementer
import pytest
import roleplan
import roles
from contract import Contract


def _by_name(subagents):
    return {agent["name"]: agent for agent in subagents}


def test_the_fixture_taskfile_validates(target_repo):
    """#496. `conftest.py`'s `target_repo` fixture used to write its
    Taskfile.yml in flow style (`setup: {cmds: [echo setup]}`), which the
    hand-rolled YAML subset parser (`contract.py`'s `missing_tasks`) never
    reads: its regex only matches a task name on its own line, block style.
    `Contract(target_repo).validate()` raised "missing required tasks:
    setup, test, e2e, lint, format-check" on the fixture meant to prove a
    valid target repo. Block style, matching the Agent SDK port's fixture,
    fixes it; this test is what keeps it fixed."""
    assert Contract(target_repo).missing_tasks() == []
    Contract(target_repo).validate()


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


def test_no_implementer_role_holds_bash(contract):
    """A shell is a wider hole than any of the three write tools it would
    replace. `subagents_for` never reads `role.tools` to build a runtime tool
    list, so this pins the declared table the SPEC and `task table` show."""
    cast = roleplan.plan(contract, "implementer")
    assert [name for name, role in cast.items() if "Bash" in role.tools] == []


def test_a_reader_override_that_grants_a_write_tool_raises(monkeypatch):
    monkeypatch.setitem(roleplan.OVERRIDES, ("implementer", "judge"), {"tools": ("Read", "Write")})
    with pytest.raises(ValueError) as exc_info:
        roleplan.plan(None, "implementer")
    assert "judge" in str(exc_info.value)


def test_the_judge_tools_are_the_read_set(contract):
    judge = roleplan.plan(contract, "implementer")["judge"]
    assert judge.tools == ("Read", "Glob", "Grep")


def test_the_table_still_says_the_judge_writes_no(contract):
    """`roleplan.table` is what `task table` prints."""
    line = next(
        line
        for line in roleplan.table(roleplan.plan(contract, "implementer")).splitlines()
        if line.startswith("judge")
    )
    assert line.split()[1] == "no"


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
    assert "/tests/**" in rules[0]["paths"]
    assert rules[1]["mode"] == "allow"
    assert rules[-1] == roles.DENY_EVERY_WRITE


def test_permissions_are_rooted_for_current_deep_agents_sdk(contract):
    for role in roleplan.plan(contract).values():
        for rule in roles.permission_rules(role):
            assert all(path.startswith("/") for path in rule["paths"])


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


def test_build_agent_roots_the_backend_at_cwd_not_the_clone(
    contract, fake_langchain, fake_deepagents
):
    """#543. `implementer.run` executes every phase in
    `<repo>.worktrees/<ticket>`, never `contract.repo` (the `--repo` clone).
    `FilesystemBackend(root_dir=...)` used to root the live session at the
    clone regardless, so a doer's writes landed where the red gate never
    looks. `cwd=` is what a caller building a live session for that worktree
    passes instead."""
    worktree = contract.repo.parent / f"{contract.repo.name}.worktrees" / "T001"

    roles.build_agent(contract, subagent_names=frozenset({"planner"}), cwd=worktree)

    assert fake_deepagents["backend"].default.root_dir == str(worktree.resolve())
    assert fake_deepagents["backend"].default.root_dir != str(contract.repo.resolve())


# -- Layer 3, checked again against the real deepagents package -------------
#
# `fake_deepagents` above proves `build_agent` calls the SDK the way this
# folder believes it does. That proof is only as good as the fake's field
# names. The two tests below close that gap: the first proves the fake
# declares real fields, the second re-runs the layer-3 fence against the
# real classes instead of the fake's stand-ins. Both skip, not fail, when
# `deepagents` is not installed -- `task test-setup` installs pytest only,
# and `.github/workflows/tests.yml:45` runs that CI leg, so CI never reaches
# either test's body. The fake-path tests above are what CI enforces, and a
# skip here is never mistaken for them having passed: this file also carries
# `test_build_agent_fences_the_harness`, which runs and asserts for real in
# every environment, `deepagents` installed or not.


@pytest.fixture
def _deepagents_installed():
    """Import the real `deepagents` package before any fixture in this file
    replaces `sys.modules["langchain"]`.

    `deepagents` imports `langchain.agents` at import time. `fake_langchain`
    swaps in a bare stand-in package with no `agents` submodule, so
    importing `deepagents` for the first time after that swap raises
    ImportError and this reports a skip that is not really about `deepagents`
    being absent. Requesting this fixture ahead of `fake_langchain` in a
    test's parameter list imports and caches the real module first, so the
    later swap cannot touch it.
    """
    return pytest.importorskip("deepagents")


def _declared_fields(cls, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Field names `cls.__init__` declares, read off the fake itself.

    `FilesystemPermission`'s fake takes `**kwargs` and declares no names of
    its own, so `fallback` supplies the field set every call site in
    `roles.py` and in `conftest.fake_deepagents` actually uses.
    """
    names = tuple(
        name
        for name, param in inspect.signature(cls.__init__).parameters.items()
        if name != "self" and param.kind is not inspect.Parameter.VAR_KEYWORD
    )
    return names or fallback


def test_the_fake_declares_the_fields_the_real_types_accept():
    """The fake is only a fence if its field names are the SDK's field
    names. Take each field list straight off `conftest`'s fake classes and
    construct the matching real `deepagents` type with exactly that field
    set, so a renamed real field breaks this test instead of leaving a fake
    that quietly no longer matches the SDK.
    """
    real = pytest.importorskip("deepagents")
    real_backends = pytest.importorskip("deepagents.backends")

    assert _declared_fields(conftest.GeneralPurposeSubagentProfile) == ("enabled",)
    disabled = real.GeneralPurposeSubagentProfile(enabled=False)

    assert _declared_fields(conftest.HarnessProfile) == (
        "excluded_tools",
        "general_purpose_subagent",
    )
    real.HarnessProfile(excluded_tools=frozenset({"write_file", "execute"}), general_purpose_subagent=disabled)

    assert _declared_fields(conftest.FilesystemPermission, ("operations", "paths", "mode")) == (
        "operations",
        "paths",
        "mode",
    )
    real.FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")

    assert _declared_fields(conftest.FilesystemBackend) == ("root_dir", "virtual_mode")
    backend = real_backends.FilesystemBackend(root_dir="/tmp", virtual_mode=True)

    assert _declared_fields(conftest.CompositeBackend) == ("default", "routes")
    real_backends.CompositeBackend(default=backend, routes={})


def _patch_create_deep_agent(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Record what `build_agent` hands the real `create_deep_agent` and
    `register_harness_profile`, without calling either -- `create_deep_agent`
    wants a model and a key, and `register_harness_profile` writes a
    process-wide registry. Every object landing in the returned dict --
    `FilesystemPermission`, `GeneralPurposeSubagentProfile`, `HarnessProfile`,
    `FilesystemBackend`, `CompositeBackend` -- is still the real deepagents
    class; only these two entry points are stand-ins.
    """
    import deepagents  # noqa: PLC0415  (the real package; only reached when installed)

    seen: dict = {}

    def create_deep_agent(**kwargs):
        seen.update(kwargs)
        return "agent"

    def register_harness_profile(model, profile):
        seen["harness_model"] = model
        seen["harness_profile"] = profile

    monkeypatch.setattr(deepagents, "create_deep_agent", create_deep_agent)
    monkeypatch.setattr(deepagents, "register_harness_profile", register_harness_profile)
    return seen


def test_the_real_types_keep_the_fence(_deepagents_installed, contract, fake_langchain, monkeypatch):
    """`test_build_agent_fences_the_harness`, re-run against the installed
    `deepagents` classes instead of `conftest`'s stand-ins: general-purpose
    off, `write_file` and `execute` excluded on the parent, the judge holds
    only `read_file`, and a role's deny rule still precedes its allow rule.

    `_deepagents_installed` sits ahead of `fake_langchain` in this parameter
    list on purpose: `deepagents` must be imported for real before
    `fake_langchain` replaces `sys.modules["langchain"]`, or the import
    fails and this test reports a skip that proves nothing.
    """
    seen = _patch_create_deep_agent(monkeypatch)

    roles.build_agent(contract)

    profile = seen["harness_profile"]
    assert profile.general_purpose_subagent.enabled is False
    assert "write_file" in profile.excluded_tools
    assert "execute" in profile.excluded_tools

    assert seen["backend"].default.virtual_mode is True

    orchestrator = seen["permissions"]
    assert [rule.mode for rule in orchestrator] == ["deny"]

    judge = next(spec for spec in seen["subagents"] if spec["name"] == "judge")
    assert [t.__name__ for t in judge["tools"]] == ["read_file"]

    code_implementer = next(spec for spec in seen["subagents"] if spec["name"] == "code-implementer")
    assert code_implementer["permissions"][0].mode == "deny"
    assert code_implementer["permissions"][1].mode == "allow"


def test_build_agent_passes_every_subagent_permission(contract, fake_langchain, fake_deepagents):
    roles.build_agent(contract)
    for spec in fake_deepagents["subagents"]:
        assert spec["permissions"], spec["name"]
        assert spec["permissions"][-1].mode == "deny"


def test_build_agent_can_restrict_the_phase_cast(contract, fake_langchain, fake_deepagents):
    roles.build_agent(
        contract,
        subagent_names=frozenset({"test-implementer"}),
    )
    assert [spec["name"] for spec in fake_deepagents["subagents"]] == ["test-implementer"]


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
