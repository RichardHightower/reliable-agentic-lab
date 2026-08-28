"""The two deterministic checks the enhancer's exits depend on.

The Judge decides which fields have real content, a judgment call. These two
scripts decide what that adds up to, a fact. A stop condition trusted to a
model's own judgment is a stop condition a model can talk itself past, so both
scripts get their arithmetic checked here rather than described in prose.
"""

from __future__ import annotations

import io
import json

import check_fields
import check_stop
import pytest

# -- check_fields ----------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(check_fields.REQUIRED))
def test_a_kind_with_every_required_field_is_ready(kind):
    result = check_fields.check(kind, check_fields.REQUIRED[kind])
    assert result["ready"] is True
    assert result["missing_fields"] == []


def test_a_missing_field_blocks_ready():
    result = check_fields.check("feature", ["problem", "proposal"])
    assert result["ready"] is False
    assert result["missing_fields"] == ["value", "criteria"]


def test_missing_fields_keep_the_rubric_order():
    """A caller diffing two rounds compares these lists, so the order matters."""
    assert check_fields.check("ui", ["proposal"])["missing_fields"] == [
        "problem",
        "value",
        "criteria",
        "wireframe",
    ]


def test_a_field_the_model_invents_is_dropped_rather_than_trusted():
    """An invented field is not evidence of readiness."""
    result = check_fields.check("bug", [*check_fields.REQUIRED["bug"], "made_up"])
    assert "made_up" not in result["present_fields"]
    assert result["ready"] is True


def test_an_invented_field_cannot_stand_in_for_a_real_one():
    result = check_fields.check("feature", ["problem", "proposal", "value", "made_up"])
    assert result["ready"] is False
    assert result["missing_fields"] == ["criteria"]


def test_an_empty_field_list_is_never_ready():
    assert check_fields.check("feature", [])["ready"] is False


def test_an_unknown_kind_is_rejected():
    """Failing loudly beats inventing a rubric for a kind nobody defined."""
    with pytest.raises(ValueError, match="unknown ticket kind"):
        check_fields.check("epic", [])


def test_a_ui_ticket_needs_more_than_a_feature_ticket():
    assert set(check_fields.REQUIRED["feature"]) < set(check_fields.REQUIRED["ui"])


def test_check_fields_reads_its_payload_from_the_command_line(monkeypatch, capsys):
    payload = json.dumps({"kind": "feature", "present_fields": ["problem"]})
    monkeypatch.setattr("sys.argv", ["check_fields.py", payload])
    check_fields.main()
    assert json.loads(capsys.readouterr().out)["ready"] is False


def test_check_fields_reads_its_payload_from_stdin(monkeypatch, capsys):
    payload = json.dumps({"kind": "bug", "present_fields": check_fields.REQUIRED["bug"]})
    monkeypatch.setattr("sys.argv", ["check_fields.py"])
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    check_fields.main()
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_check_fields_treats_an_absent_field_list_as_empty(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check_fields.py", json.dumps({"kind": "feature"})])
    check_fields.main()
    assert json.loads(capsys.readouterr().out)["missing_fields"] == check_fields.REQUIRED["feature"]


def test_the_check_fields_demo_still_passes(capsys):
    check_fields.demo()
    assert "all demo assertions passed" in capsys.readouterr().out


# -- check_stop ------------------------------------------------------------


def test_the_first_round_does_not_stop():
    assert check_stop.check(0, 3, ["value"], None) == {"stop": False, "reason": None}


def test_a_changed_signature_inside_budget_does_not_stop():
    assert check_stop.check(1, 3, ["value"], ["other"]) == {"stop": False, "reason": None}


def test_the_same_signature_two_rounds_running_stops():
    """A loop that keeps finding the same gap is not converging, it is stuck."""
    result = check_stop.check(1, 3, ["value"], ["value"])
    assert result == {"stop": True, "reason": "same signature two rounds running"}


def test_a_spent_budget_stops_even_when_the_signature_changed():
    """Round 2 is the third round. `round + 1 == budget` spends it."""
    assert check_stop.check(2, 3, ["value"], ["other"]) == {"stop": True, "reason": "budget spent"}


def test_a_repeated_signature_is_reported_before_a_spent_budget():
    """Both exits fire here. The stall is the more useful reason to report."""
    assert check_stop.check(2, 3, ["value"], ["value"])["reason"] == (
        "same signature two rounds running"
    )


def test_an_empty_signature_repeated_still_stops():
    """Two clean rounds in a row is a stall, not a reason to keep spending."""
    assert check_stop.check(0, 5, [], [])["stop"] is True


def test_a_first_round_with_no_previous_signature_never_compares():
    """`None` means "there was no previous round", which is not a match."""
    assert check_stop.check(0, 5, [], None)["stop"] is False


def test_a_budget_of_one_stops_on_the_first_round():
    assert check_stop.check(0, 1, ["value"], None) == {"stop": True, "reason": "budget spent"}


def test_check_stop_reads_its_payload_from_the_command_line(monkeypatch, capsys):
    payload = json.dumps({"round": 2, "budget": 3, "signature": ["value"]})
    monkeypatch.setattr("sys.argv", ["check_stop.py", payload])
    check_stop.main()
    assert json.loads(capsys.readouterr().out) == {"stop": True, "reason": "budget spent"}


def test_check_stop_reads_its_payload_from_stdin(monkeypatch, capsys):
    payload = json.dumps(
        {"round": 1, "budget": 3, "signature": ["value"], "previous_signature": ["value"]}
    )
    monkeypatch.setattr("sys.argv", ["check_stop.py"])
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    check_stop.main()
    assert json.loads(capsys.readouterr().out)["stop"] is True


def test_the_check_stop_demo_still_passes(capsys):
    check_stop.demo()
    assert "all demo assertions passed" in capsys.readouterr().out


def test_cost_budget_stops():
    assert check_stop.check(0, 3, ["value"], None, usd=2.0, max_usd=2.0) == {
        "stop": True,
        "reason": "cost budget spent",
    }


def test_max_turns_stops():
    assert check_stop.check(0, 3, ["value"], None, turns=12, max_turns=12) == {
        "stop": True,
        "reason": "max turns",
    }


def test_a_stall_is_reported_before_cost():
    assert check_stop.check(1, 3, ["value"], ["value"], usd=9.0, max_usd=1.0)["reason"] == (
        "same signature two rounds running"
    )
