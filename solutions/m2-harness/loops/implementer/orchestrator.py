from __future__ import annotations

from pathlib import Path
import sys

M2_ROOT = Path(__file__).resolve().parents[2]
if str(M2_ROOT) not in sys.path:
    sys.path.insert(0, str(M2_ROOT))

from loops.implementer import checker, gates, grader, maker, rubric, trace
from loops.implementer.schema import Score
from paths import DEFAULT_TICKET, REPO_ROOT


def run_loop(
    *,
    ticket_path: Path = DEFAULT_TICKET,
    maker_mode: str = "none",
    budget: int = gates.DEFAULT_BUDGET,
    root: Path = REPO_ROOT,
) -> dict:
    ready = rubric.load_ready_ticket(ticket_path)
    trace_id = trace.new_trace_id()
    previous_failed: list[str] | None = None
    steps: list[dict] = []
    last_score = Score(ticket_id=ready["ticket_id"], iteration=0, passed=False)

    for iteration in range(1, budget + 1):
        grade = grader.run_hidden_grader(cwd=root)
        checked = checker.check(grader=grade, previous_failed=previous_failed)
        decision = gates.decide(
            passed=checked["passed"],
            iteration=iteration,
            failed_node_ids=checked["failed_node_ids"],
            previous_failed_node_ids=previous_failed,
            budget=budget,
        )
        last_score = Score(
            ticket_id=ready["ticket_id"],
            iteration=iteration,
            passed=checked["passed"],
            failed_node_ids=checked["failed_node_ids"],
            repeat_failure=decision["repeat_failure"],
            gate=decision["gate"],
            trace_id=trace_id,
            pytest_exit_code=grade["exit_code"],
        )
        maker_result = None
        if decision["gate"] == gates.RETRY:
            maker_result = maker.run(maker_mode)
        step = {
            "iteration": iteration,
            "checker_summary": checked["summary"],
            "maker": maker_result,
            "score": last_score.to_dict(),
        }
        steps.append(step)
        if decision["gate"] != gates.RETRY:
            break
        previous_failed = list(checked["failed_node_ids"])

    payload = {
        "trace_id": trace_id,
        "ticket_id": ready["ticket_id"],
        "criteria_count": len(ready["criteria"]),
        "tool_scope": rubric.tool_scope(),
        "maker_mode": maker_mode,
        "budget": budget,
        "steps": steps,
        "score": last_score.to_dict(),
    }
    trace.write_trace(payload)
    return payload
