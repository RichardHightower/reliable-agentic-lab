from __future__ import annotations

from pathlib import Path


def load_ready_ticket(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    ticket_id = "T001"
    criteria: list[str] = []
    in_criteria = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("id:"):
            ticket_id = line.split(":", 1)[1].strip()
        if line.lower().startswith("## success criteria"):
            in_criteria = True
            continue
        if in_criteria and line.startswith("## "):
            break
        if in_criteria and line.startswith("- "):
            criteria.append(line[2:].strip())
    if not criteria:
        raise ValueError(f"no success criteria in {path}")
    return {"ticket_id": ticket_id, "criteria": criteria, "path": str(path), "text": text}


def tool_scope() -> dict:
    return {
        "orchestrator": ["run_loop", "hold_budget", "read_summaries"],
        "maker": ["read_crm", "write_crm", "run_grader"],
        "checker": ["read_diff", "read_pytest", "read_ticket"],
        "forbidden": ["edit_graders", "change_ticket_state", "merge_pr", "deploy"],
    }
