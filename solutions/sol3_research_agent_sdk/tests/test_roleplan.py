"""The role table. The separation is the tool list, not a rule in a prompt."""

from __future__ import annotations

import pytest
import roleplan


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_the_judge_writes_nothing_in_every_loop(loop):
    judge = roleplan.plan(None, loop)["judge"]
    assert not judge.can_write
    assert judge.allow == ()


@pytest.mark.parametrize("loop", sorted(roleplan.LOOPS))
def test_the_orchestrator_only_spawns(loop):
    orchestrator = roleplan.plan(None, loop)["orchestrator"]
    assert orchestrator.tools == ("Task",)
    assert not orchestrator.can_write


def test_the_research_cast_is_twelve_roles():
    assert roleplan.LOOPS["research"] == (
        "orchestrator",
        "outliner",
        "outline_judge",
        "outline_editor",
        "researcher",
        "verifier",
        "section_judge",
        "ledger",
        "diagrammer",
        "chartist",
        "writer",
        "judge",
    )


def test_the_research_cast_needs_no_contract():
    """A research run answers a topic, not a repo. There is no `.loop.yml`."""
    assert set(roleplan.plan(None, "research")) == set(roleplan.LOOPS["research"])


@pytest.mark.parametrize(
    "name",
    [
        "outliner",
        "outline_judge",
        "researcher",
        "verifier",
        "section_judge",
        "ledger",
        "diagrammer",
        "chartist",
        "judge",
    ],
)
def test_a_searcher_cannot_write(name):
    """A role that can search and write can edit the evidence to fit the paper."""
    role = roleplan.plan(None, "research")[name]
    assert not role.can_write
    for tool in roleplan.WRITE_TOOLS:
        assert tool not in role.tools


def test_no_role_in_this_cast_holds_a_shell():
    """A research tool that hands a model a shell has widened its blast radius
    from "a wrong paper" to "anything this machine can run"."""
    roles = roleplan.plan(None, "research")
    assert [name for name, role in roles.items() if "Bash" in role.tools] == []


def test_the_verifier_reaches_the_corpus_and_both_live_servers():
    tools = roleplan.plan(None, "research")["verifier"].tools
    assert "mcp__corpus__corpus_search" in tools
    assert "mcp__perplexity__perplexity_search" in tools
    assert "mcp__perplexity__perplexity_ask" in tools
    assert "mcp__context7__query-docs" in tools


def test_exactly_one_role_writes():
    """Everything else comes back as schema-checked structured output that
    Python writes. One writer is what keeps the PreToolUse hook load-bearing
    without giving four roles a way to edit the run."""
    roles = roleplan.plan(None, "research")
    writers = {name: role.allow for name, role in roles.items() if role.can_write}
    assert writers == {"writer": ("sections/**",)}


def test_the_writer_cannot_reach_the_assembled_paper():
    """Assembly is deterministic, in Python, and not the writer's to redo."""
    from write_scope import WriteScope  # noqa: PLC0415

    writer = roleplan.plan(None, "research")["writer"]
    scope = WriteScope(allow=list(writer.allow), deny=list(writer.deny))
    assert scope.permits("sections/s1.md")
    assert not scope.permits("paper.md")
    assert not scope.permits("claims.json")


def test_the_research_outliner_does_not_inherit_the_implementer_planner():
    """One table, two jobs. The research outliner writes nothing."""
    research = roleplan.plan(None, "research")["outliner"]
    implementer = roleplan.plan(None, "implementer")["planner"]
    assert implementer.can_write and not research.can_write
    assert "Bash" in implementer.tools and "Bash" not in research.tools
    assert "planner" not in roleplan.plan(None, "research")


def test_an_override_that_widens_a_reader_is_refused(monkeypatch):
    monkeypatch.setitem(
        roleplan.OVERRIDES, ("research", "judge"), {"tools": ("Read", "Write"), "deny": ()}
    )
    with pytest.raises(ValueError, match="reader"):
        roleplan.plan(None, "research")


def test_an_override_that_sets_allow_without_deny_is_refused(monkeypatch):
    """Deny beats allow, so a lone allow produces a role that can write nothing."""
    monkeypatch.setitem(roleplan.OVERRIDES, ("research", "writer"), {"allow": ("x.md",)})
    with pytest.raises(ValueError, match=r"[Dd]eny"):
        roleplan.plan(None, "research")


def test_an_unknown_loop_is_refused():
    with pytest.raises(ValueError, match="unknown loop"):
        roleplan.plan(None, "nope")


def test_the_outliner_and_outline_judge_name_their_models():
    roles = roleplan.plan(None, "research")
    assert roles["outliner"].model == "claude-sonnet-5"
    assert roles["outline_judge"].model == "claude-opus-5"
    assert roles["outline_judge"].effort == "high"
    assert roles["writer"].model == "claude-opus-5"


def test_the_table_names_the_scope():
    table = roleplan.table(roleplan.plan(None, "research"))
    assert "writer" in table and "sections/**" in table
    assert "judge             no" in table
    assert "diagrammer        no" in table
    assert "chartist          no" in table
    assert "outliner          no" in table
    assert "outline_judge     no" in table
    writers = [line for line in table.splitlines() if line.split()[1:2] == ["yes"]]
    assert len(writers) == 1 and writers[0].startswith("writer")
