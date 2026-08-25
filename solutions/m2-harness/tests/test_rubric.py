from pathlib import Path

from loops.implementer.rubric import load_ready_ticket, tool_scope


def test_ready_ticket_loads_criteria(tmp_path: Path):
    ticket = tmp_path / "ready.md"
    ticket.write_text(
        "---\nid: T001\n---\n\n# Due dates\n\n## Success criteria\n\n- optional due_date\n- overdue filter\n\n## Out of scope\n\n- calendars\n",
        encoding="utf-8",
    )
    loaded = load_ready_ticket(ticket)
    assert loaded["ticket_id"] == "T001"
    assert loaded["criteria"] == ["optional due_date", "overdue filter"]


def test_maker_cannot_change_tickets():
    assert "change_ticket_state" in tool_scope()["forbidden"]
    assert "write_crm" in tool_scope()["maker"]
    assert "write_crm" not in tool_scope()["checker"]
