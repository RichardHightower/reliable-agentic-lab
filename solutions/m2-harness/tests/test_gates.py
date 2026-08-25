from loops.implementer.gates import ESCALATE, PASS, RETRY, decide


def test_pass_when_grader_is_green():
    result = decide(
        passed=True,
        iteration=1,
        failed_node_ids=[],
        previous_failed_node_ids=None,
        budget=3,
    )
    assert result["gate"] == PASS


def test_retry_on_first_failure():
    result = decide(
        passed=False,
        iteration=1,
        failed_node_ids=["test_model_has_optional_due_date"],
        previous_failed_node_ids=None,
        budget=3,
    )
    assert result["gate"] == RETRY


def test_escalate_on_repeat_failure():
    failed = ["test_filter_overdue"]
    result = decide(
        passed=False,
        iteration=2,
        failed_node_ids=failed,
        previous_failed_node_ids=failed,
        budget=3,
    )
    assert result["gate"] == ESCALATE
    assert result["repeat_failure"] is True


def test_escalate_when_budget_spent():
    result = decide(
        passed=False,
        iteration=3,
        failed_node_ids=["test_task_form_exposes_due_date_field"],
        previous_failed_node_ids=["test_model_has_optional_due_date"],
        budget=3,
    )
    assert result["gate"] == ESCALATE
