"""The role table is the contract every runtime reads. Check it here."""

from __future__ import annotations

import pytest
import roleplan
from contract import Contract


def test_enhancer_cast_is_three_roles_in_order(contract):
    assert list(roleplan.plan(contract, "enhancer")) == ["orchestrator", "doer", "judge"]


def test_judge_holds_no_write_tool(contract):
    judge = roleplan.plan(contract, "enhancer")["judge"]
    assert judge.can_write is False
    assert not set(judge.tools) & set(roleplan.WRITE_TOOLS)


def test_orchestrator_holds_no_write_tool(contract):
    orchestrator = roleplan.plan(contract, "enhancer")["orchestrator"]
    assert orchestrator.can_write is False


def test_doer_scope_falls_back_when_loop_yml_is_silent(contract):
    doer = roleplan.plan(contract, "enhancer")["doer"]
    assert doer.can_write is True
    assert doer.allow == ("tickets/**",)
    assert doer.deny == ()


def test_declared_doer_overrides_the_fallback(target_repo):
    (target_repo / ".loop.yml").write_text(
        'version: 1\nroles:\n  doer:\n    write_allow: ["issues/**"]\n    write_deny: ["issues/secret.md"]\n',
        encoding="utf-8",
    )
    doer = roleplan.plan(Contract(target_repo), "enhancer")["doer"]
    assert doer.allow == ("issues/**",)
    assert doer.deny == ("issues/secret.md",)


def test_table_prints_no_for_the_judge_and_yes_for_the_doer(contract):
    rows = {
        line.split()[0]: line.split()[1]
        for line in roleplan.table(roleplan.plan(contract, "enhancer")).splitlines()[1:]
    }
    assert rows == {"orchestrator": "no", "doer": "yes", "judge": "no"}


def test_table_names_the_scope(contract):
    text = roleplan.table(roleplan.plan(contract, "enhancer"))
    assert "tickets/**" in text
    assert "nothing" in text


def test_plan_works_without_a_contract():
    doer = roleplan.plan(None, "enhancer")["doer"]
    assert doer.allow == ("tickets/**",)


def test_unknown_loop_raises(contract):
    with pytest.raises(ValueError, match="unknown loop"):
        roleplan.plan(contract, "nope")
