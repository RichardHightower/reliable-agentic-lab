from __future__ import annotations

from pathlib import Path


GOOD_REPORT = """# Due dates on sales tasks

This report answers whether a customer relationship management (CRM) app should store an optional due date on sales tasks.

## Finding

Yes. Store `sales_tasks.due_date` as an optional UTC date. Accept ISO 8601. Keep existing rows valid with null.

## Why it is testable

A ready ticket can grade the model, the API, and the list filters. Overdue means status is open and the date is before today UTC.

## Tool boundary

Research ran in a sub-agent over Model Context Protocol (MCP). The orchestrator only received a summary. The checker has no write tools.

## Recommendation

Ship the field. Filter `due_before` and `overdue`. Do not invent reminders or calendars.
"""


DIRTY_REPORT = """# Due dates

CRM should always require a due date---and store it in local time. MCP is used later. This is a long rambling sentence that keeps adding clauses so that the style checker will fail it for packing more than one idea into a single sentence without any respect for the rubric.
"""


def draft(notes: dict, work_dir: Path, *, dirty: bool = False) -> Path:
    text = DIRTY_REPORT if dirty else GOOD_REPORT
    path = work_dir / "report.md"
    path.write_text(text, encoding="utf-8")
    return path


def repair_facts(report_path: Path, issues: list[dict]) -> Path:
    report_path.write_text(GOOD_REPORT, encoding="utf-8")
    return report_path


def repair_style(report_path: Path, issues: list[dict]) -> Path:
    from style_enforcer import strip_emdashes

    text = strip_emdashes(report_path.read_text(encoding="utf-8"))
    if any(i.get("id", "").startswith("expand:") or i.get("id") == "sentence-length" for i in issues):
        text = GOOD_REPORT
    report_path.write_text(text, encoding="utf-8")
    return report_path
