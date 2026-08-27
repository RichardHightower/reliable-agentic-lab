"""Write scope is structural. These are the cases the harness depends on."""

from __future__ import annotations

import pytest
from write_scope import Judge, ScopeViolation, WriteScope


def test_allow_matches_a_direct_child():
    assert WriteScope(allow=["tickets/**"]).permits("tickets/a.md") is True


def test_allow_matches_any_depth():
    assert WriteScope(allow=["tickets/**"]).permits("tickets/deep/nested/a.md") is True


def test_a_path_outside_the_allow_list_is_refused():
    assert WriteScope(allow=["tickets/**"]).permits("app/x.py") is False


def test_an_empty_allow_list_permits_nothing():
    assert WriteScope().permits("anything.md") is False


def test_deny_beats_allow():
    scope = WriteScope(allow=["app/**", "tests/**"], deny=["tests/**"])
    assert scope.permits("app/x.py") is True
    assert scope.permits("tests/test_x.py") is False


def test_deny_everything_refuses_everything():
    assert WriteScope(allow=["**"], deny=["**"]).permits("app/x.py") is False


def test_check_raises_and_names_the_scope():
    with pytest.raises(ScopeViolation) as caught:
        WriteScope(allow=["tickets/**"]).check("app/x.py")
    assert "app/x.py" in str(caught.value)
    assert "tickets/**" in str(caught.value)


def test_check_is_silent_inside_the_scope():
    assert WriteScope(allow=["tickets/**"]).check("tickets/a.md") is None


def test_judge_has_no_write_method(tmp_path):
    """No `write` on the judge is why it cannot grade its own homework."""
    judge = Judge(name="judge", repo=tmp_path)
    assert not hasattr(judge, "write")
