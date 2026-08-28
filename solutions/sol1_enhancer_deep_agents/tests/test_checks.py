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


def _stop(**kwargs):
    defaults = dict(done=False, turns=0, max_turns=3, spent_usd=0.0, max_usd=2.0)
    defaults.update(kwargs)
    return check_stop.check(**defaults)


def test_the_first_round_does_not_stop():
    assert _stop(turns=0) == {"stop": False, "reason": None}


def test_a_changed_round_inside_the_caps_does_not_stop():
    assert _stop(turns=1, spent_usd=0.4) == {"stop": False, "reason": None}


def test_done_stops_even_when_the_caps_are_spent():
    """The rubric is green. Cost and turns do not override that."""
    assert _stop(done=True, turns=2, spent_usd=9.0) == {"stop": True, "reason": "done"}


def test_cost_stops_before_max_turns():
    """Both caps can fire. Dollars are the more useful reason to report."""
    assert _stop(turns=2, spent_usd=2.0, max_usd=2.0) == {"stop": True, "reason": "cost"}


def test_max_turns_stops_when_cost_is_still_under():
    """Round 2 is the third round. `turns + 1 == max_turns` spends it."""
    assert _stop(turns=2, spent_usd=0.1) == {"stop": True, "reason": "max turns"}


def test_a_turn_cap_of_one_stops_on_the_first_round():
    assert _stop(turns=0, max_turns=1) == {"stop": True, "reason": "max turns"}


def test_hitting_the_dollar_cap_exactly_stops():
    assert _stop(spent_usd=2.0, max_usd=2.0)["reason"] == "cost"


def test_check_stop_reads_its_payload_from_the_command_line(monkeypatch, capsys):
    payload = json.dumps({"done": False, "turns": 2, "max_turns": 3, "spent_usd": 0.1, "max_usd": 2.0})
    monkeypatch.setattr("sys.argv", ["check_stop.py", payload])
    check_stop.main()
    assert json.loads(capsys.readouterr().out) == {"stop": True, "reason": "max turns"}


def test_check_stop_reads_its_payload_from_stdin(monkeypatch, capsys):
    payload = json.dumps(
        {"done": False, "turns": 0, "max_turns": 3, "spent_usd": 2.0, "max_usd": 2.0}
    )
    monkeypatch.setattr("sys.argv", ["check_stop.py"])
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    check_stop.main()
    assert json.loads(capsys.readouterr().out) == {"stop": True, "reason": "cost"}


def test_the_check_stop_demo_still_passes(capsys):
    check_stop.demo()
    assert "all demo assertions passed" in capsys.readouterr().out
