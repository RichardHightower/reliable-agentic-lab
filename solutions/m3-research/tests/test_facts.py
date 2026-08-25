from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from fact_checker import check_facts


def notes():
    return json.loads((HERE / "fixtures" / "research.json").read_text(encoding="utf-8"))


def test_good_report_is_grounded():
    report = (HERE / "writer.py").read_text(encoding="utf-8")
    # use the GOOD_REPORT constant by importing writer
    import writer

    verdict = check_facts(writer.GOOD_REPORT, notes())
    assert verdict["passed"] is True


def test_contradiction_is_critical():
    verdict = check_facts("- Due dates must be required in local time.", notes())
    assert verdict["passed"] is False
    assert "contradiction" in verdict["failed_ids"]
