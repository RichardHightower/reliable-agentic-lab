"""Checks for the final judge.

A model judge is only safe if its output cannot slip through unread. Every
malformed reply here must land on FAIL.
"""

from __future__ import annotations

from loops.final_judge import build_prompt, extract_json, parse_verdict


def test_a_clean_pass_parses():
    verdict = parse_verdict('{"done": true, "summary": "Due dates work end to end.", "issues": []}')
    assert verdict.done is True
    assert verdict.parsed is True


def test_a_clean_fail_parses_and_keeps_its_issues():
    verdict = parse_verdict(
        '{"done": false, "summary": "The filter is missing.",'
        ' "issues": [{"severity": "major", "description": "no overdue filter"}]}'
    )
    assert verdict.done is False
    assert len(verdict.blocking_issues) == 1
    assert "overdue" in verdict.report()


def test_json_fenced_in_markdown_still_parses():
    verdict = parse_verdict(
        'Here is my verdict:\n```json\n{"done": true, "summary": "fine", "issues": []}\n```\nThanks.'
    )
    assert verdict.done is True


def test_json_with_prose_on_both_sides_parses():
    verdict = parse_verdict('I looked carefully. {"done": true, "summary": "ok"} Let me know.')
    assert verdict.done is True


def test_a_brace_inside_a_string_does_not_confuse_the_scanner():
    verdict = parse_verdict('{"done": true, "summary": "it prints {not json} to stdout"}')
    assert verdict.done is True
    assert "{not json}" in verdict.summary


# --- every way a judge can fail to decide ---------------------------------


def test_unparseable_output_is_a_fail_not_a_pass():
    verdict = parse_verdict("I think it looks good to me!")
    assert verdict.done is False
    assert verdict.parsed is False


def test_empty_output_is_a_fail():
    assert parse_verdict("").done is False


def test_a_missing_done_field_is_a_fail():
    assert parse_verdict('{"summary": "looks fine"}').done is False


def test_a_non_boolean_done_is_a_fail():
    verdict = parse_verdict('{"done": "yes", "summary": "fine"}')
    assert verdict.done is False
    assert verdict.parsed is False


def test_pass_while_listing_a_blocking_issue_is_rejected():
    """A judge that says done and names a major problem has not decided."""
    verdict = parse_verdict(
        '{"done": true, "summary": "mostly",'
        ' "issues": [{"severity": "critical", "description": "the API is missing"}]}'
    )
    assert verdict.done is False
    assert verdict.parsed is False


def test_fail_with_no_issues_is_rejected():
    verdict = parse_verdict('{"done": false, "summary": "no"}')
    assert verdict.done is False
    assert verdict.parsed is False


def test_an_unknown_severity_is_rejected():
    verdict = parse_verdict(
        '{"done": false, "issues": [{"severity": "catastrophic", "description": "x"}]}'
    )
    assert verdict.parsed is False


def test_a_pass_may_carry_minor_issues():
    verdict = parse_verdict(
        '{"done": true, "summary": "good",'
        ' "issues": [{"severity": "minor", "description": "a nit about naming"}]}'
    )
    assert verdict.done is True
    assert verdict.blocking_issues == []


def test_extract_json_returns_none_when_there_is_none():
    assert extract_json("no braces at all") is None


def test_the_prompt_truncates_a_huge_diff():
    prompt = build_prompt(ticket="T001", steps="{}", diff="x" * 50000, diff_limit=100)
    assert "diff truncated at 100 characters" in prompt
    assert len(prompt) < 2000


def test_the_prompt_carries_the_ticket_the_steps_and_the_diff():
    prompt = build_prompt(ticket="TICKET-BODY", steps="STEPS-BODY", diff="DIFF-BODY")
    assert "TICKET-BODY" in prompt
    assert "STEPS-BODY" in prompt
    assert "DIFF-BODY" in prompt
