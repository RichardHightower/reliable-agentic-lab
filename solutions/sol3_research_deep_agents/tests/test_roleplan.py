"""The cast, by value. A runtime that disagrees with this table is wrong."""

from __future__ import annotations

import roleplan

READS_ONLY = (
    "orchestrator",
    "researcher",
    "reviewer",
    "outline_judge",
    "section_judge",
    "ledger",
)
WRITES = ("planner", "verifier", "diagrammer", "writer")


def test_paper_cast_is_ten_roles():
    roles = roleplan.plan(None, "paper")
    assert list(roles) == [
        "orchestrator",
        "planner",
        "outline_judge",
        "researcher",
        "verifier",
        "section_judge",
        "ledger",
        "diagrammer",
        "writer",
        "reviewer",
    ]


def test_readers_hold_no_write_path():
    """If any of these prints yes in the table, the translation is wrong."""
    roles = roleplan.plan(None, "paper")
    for name in READS_ONLY:
        assert roles[name].can_write is False, name


def test_writers_can_write():
    roles = roleplan.plan(None, "paper")
    for name in WRITES:
        assert roles[name].can_write is True, name


def test_scopes_are_disjoint_where_it_matters():
    """The writer cannot forge evidence and the verifier cannot edit the paper."""
    roles = roleplan.plan(None, "paper")
    assert "evidence/**" in roles["writer"].deny
    assert "paper/**" in roles["verifier"].deny
    assert "paper/**" in roles["diagrammer"].deny
    assert "evidence/**" in roles["diagrammer"].deny


def test_diagrammer_writes_source_not_figures():
    """A role that could write a rendered figure could write one the source
    does not support."""
    allow = roleplan.plan(None, "paper")["diagrammer"].allow
    assert allow == ("diagrams/*.mmd", "diagrams/*.puml")
    assert not any(pattern.endswith((".png", ".svg")) for pattern in allow)


def test_lab_three_cast_is_untouched():
    """Growing this folder must not move the Saturday answer."""
    roles = roleplan.plan(None, "research")
    assert list(roles) == ["orchestrator", "researcher", "writer", "judge"]
    assert roles["judge"].can_write is False
    assert roles["orchestrator"].can_write is False


def test_table_prints_the_writes_column():
    table = roleplan.table(roleplan.plan(None, "paper"))
    assert "reviewer          no" in table
    assert "planner           yes" in table
