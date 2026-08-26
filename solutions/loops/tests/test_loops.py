from __future__ import annotations

from pathlib import Path

from solutions.loops import criteria, enhancer, fixer, implementer
from solutions.loops.store import LocalBoard


def test_classify_due_date_as_feature():
    kind = criteria.classify({"title": "Customers need to know when tasks are due", "body": "Add due dates."})
    assert kind == "feature"


def test_classify_search_bug():
    kind = criteria.classify({"title": "Customer search misses real names", "body": "query returns nothing"})
    assert kind == "bug"


def test_draft_ticket_is_not_ready():
    verdict = criteria.evaluate(
        {
            "title": "Customers need to know when tasks are due",
            "body": "Sales people keep missing follow-ups. Add due dates to tasks.",
        }
    )
    assert verdict["ready"] is False


def test_ready_contract_is_ready():
    body = "## Success criteria\n\n- a\n- b\n- c\n- d\n"
    verdict = criteria.evaluate({"title": "Due dates", "body": body})
    assert verdict["ready"] is True


def test_enhancer_comments_without_incorporate(tmp_path: Path):
    payload = enhancer.run(ticket_id="T001", incorporate=False, budget=1, work_dir=tmp_path)
    assert payload["ready"] is False
    assert payload["comment_count"] >= 1
    issue = LocalBoard(tmp_path).get_issue("T001")
    assert "ready" not in issue["labels"]


def test_enhancer_marks_ready_after_incorporate(tmp_path: Path):
    payload = enhancer.run(ticket_id="T001", incorporate=True, budget=3, work_dir=tmp_path)
    assert payload["ready"] is True
    assert payload["gate"] == "pass"
    issue = LocalBoard(tmp_path).get_issue("T001")
    assert "ready" in issue["labels"]
    assert "## Success criteria" in issue["body"]


def test_implementer_opens_pr_with_reference_maker(tmp_path: Path):
    payload = implementer.run(ticket_id="T001", maker="reference", budget=3, work_dir=tmp_path)
    assert payload["passed"] is True
    assert payload["pr"] == "PR-T001"
    assert payload["files"]


def test_implementer_fails_without_maker(tmp_path: Path):
    payload = implementer.run(ticket_id="T001", maker="none", budget=1, work_dir=tmp_path)
    assert payload["passed"] is False
    assert payload["pr"] is None


def test_fixer_restores_green_pr(tmp_path: Path):
    payload = fixer.run(issue_id="T001", maker="reference", budget=3, work_dir=tmp_path)
    assert payload["passed"] is True
    pr = LocalBoard(tmp_path).get_pr("PR-T001")
    assert pr["passing"] is True


def test_fixer_abandons_when_maker_is_none(tmp_path: Path):
    payload = fixer.run(issue_id="T001", maker="none", budget=2, work_dir=tmp_path)
    assert payload["passed"] is False
    pr = LocalBoard(tmp_path).get_pr("PR-T001")
    assert pr["passing"] is False
    assert pr["comments"]
