from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import loop


def test_clean_report_passes(tmp_path: Path):
    payload = loop.run(work_dir=tmp_path)
    assert payload["passed"] is True
    assert payload["gate"] == "pass"
    assert payload["research_backend"] == "fixture"
    assert (tmp_path / "report.md").exists()


def test_dirty_report_retries_then_passes(tmp_path: Path):
    payload = loop.run(dirty=True, work_dir=tmp_path)
    assert payload["passed"] is True
    fact_steps = payload["fact"]["steps"]
    assert fact_steps[0]["passed"] is False
    assert any(step["passed"] for step in fact_steps)


def test_budget_can_stop_the_loop(tmp_path: Path):
    payload = loop.run(dirty=True, max_loops=1, max_budget=2.0, work_dir=tmp_path)
    # research + draft already cost 2, first check may escalate on budget
    assert payload["passed"] is False or payload["cost"] <= 8.0
