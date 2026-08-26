from __future__ import annotations

from pathlib import Path

LOOPS_ROOT = Path(__file__).resolve().parent
SOLUTIONS_ROOT = LOOPS_ROOT.parent
REPO_ROOT = SOLUTIONS_ROOT.parent
TICKETS_ROOT = SOLUTIONS_ROOT / "tickets"
CRM_ROOT = SOLUTIONS_ROOT / "crm"
STARTER_CRM = SOLUTIONS_ROOT / "m1-implementer" / "starter_crm"
FIXTURES = SOLUTIONS_ROOT / "m2-harness" / "fixtures" / "t001-pass"
GRADER = SOLUTIONS_ROOT / "m2-harness" / "graders" / "test_due_date_contract.py"
READY_T001 = TICKETS_ROOT / "T001-due-dates.ready.md"
DRAFT_T001 = TICKETS_ROOT / "T001-due-dates.md"
DEFAULT_WORK = LOOPS_ROOT / "work"
