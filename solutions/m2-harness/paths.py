from __future__ import annotations

from pathlib import Path

M2_ROOT = Path(__file__).resolve().parent
SOLUTIONS_ROOT = M2_ROOT.parent
REPO_ROOT = SOLUTIONS_ROOT.parent
CRM_ROOT = SOLUTIONS_ROOT / "crm"
TICKETS_ROOT = SOLUTIONS_ROOT / "tickets"
TRACE_DIR = M2_ROOT / "traces"
FIXTURES = M2_ROOT / "fixtures" / "t001-pass"
GRADER = M2_ROOT / "graders" / "test_due_date_contract.py"
DEFAULT_TICKET = TICKETS_ROOT / "T001-due-dates.ready.md"
