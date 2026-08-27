"""Write scope is the point. It is structural, not a rule in a prompt.

`WriteScope._matches` runs four independent strategies and swallows a
`ValueError` from one of them. Each strategy gets a case here, because a glob
that quietly stops matching is a scope that quietly widens.

Two things here stay uncovered on purpose.

`write_scope.build()` hardcodes the implementer's five roles. The enhancer never
calls it and `loop.py` never imports it. This module is a byte copy of
`loops/roles.py`, so changing `build()` to look like an enhancer cast would make
the copy drift from the original.

`_matches` line 41, `if pattern == "**"`, is unreachable. `fnmatch(rel, "**")`
on the line above returns True for every string, including one with a slash, so
the branch never runs. It is harmless and it belongs to the original module, so
it stays as written rather than being deleted from a copy.
"""

from __future__ import annotations

import pytest
from write_scope import Doer, Judge, Orchestrator, Role, ScopeViolation, WriteScope

# -- WriteScope.permits ----------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["tests/a.py", "tests/nested/b.py", "tests/deeply/nested/c.py", "tests"],
)
def test_a_double_star_suffix_matches_at_every_depth(path):
    """`tests/**` must catch `tests/a.py`, not only `tests/a/b.py`.

    fnmatch alone treats `**` as a single `*`, so the prefix branch is what
    makes a one-level path match. Losing it lets a doer write `tests/a.py`.
    """
    assert WriteScope(allow=["tests/**"]).permits(path) is True


def test_a_double_star_suffix_does_not_match_a_sibling_prefix():
    """`tests/**` must not swallow `tests_helper.py`."""
    assert WriteScope(allow=["tests/**"]).permits("tests_helper.py") is False


def test_a_bare_double_star_matches_everything():
    scope = WriteScope(allow=["**"])
    assert scope.permits("a.py") is True
    assert scope.permits("deep/nested/path.py") is True


def test_a_plain_glob_matches_one_segment():
    scope = WriteScope(allow=["*.md"])
    assert scope.permits("README.md") is True
    assert scope.permits("app/models.py") is False


def test_a_bare_glob_reaches_every_directory():
    """fnmatch's `*` crosses a `/`, so `*.py` is not one segment here."""
    assert WriteScope(allow=["*.py"]).permits("app/models.py") is True


def test_a_bare_filename_matches_that_name_at_any_depth():
    """`PurePosixPath.match` anchors at the right, so `steps.jsonl` is not one path.

    `contract.DEFAULTS` gives the planner `write_allow: ["steps.jsonl"]`, which
    reads like one file at the repo root and is not. Recorded here because a
    scope that quietly widens is worth knowing about before a role uses it.
    """
    scope = WriteScope(allow=["steps.jsonl"])
    assert scope.permits("steps.jsonl") is True
    assert scope.permits("work/nested/steps.jsonl") is True
    assert scope.permits("work/other.jsonl") is False


def test_an_empty_allow_list_permits_nothing():
    """The safe way to be wrong. A role with no declared scope writes nothing."""
    assert WriteScope().permits("anything.py") is False


def test_deny_beats_allow():
    scope = WriteScope(allow=["app/**", "src/**"], deny=["tests/**"])
    assert scope.permits("app/models.py") is True
    assert scope.permits("tests/test_models.py") is False


def test_deny_beats_allow_even_when_both_match():
    """An overlapping allow rule must not rescue a denied path."""
    scope = WriteScope(allow=["**"], deny=["tests/**"])
    assert scope.permits("tests/test_models.py") is False


def test_a_path_is_normalized_before_it_is_matched():
    """`./app/models.py` and `app/models.py` are the same file."""
    assert WriteScope(allow=["app/**"]).permits("./app/models.py") is True


def test_a_malformed_pattern_does_not_crash_the_check():
    """`PurePosixPath.match` raises on an empty pattern. Failing closed is right."""
    assert WriteScope(allow=[""]).permits("app/models.py") is False


# -- WriteScope.check ------------------------------------------------------


def test_check_raises_on_an_out_of_scope_path():
    with pytest.raises(ScopeViolation, match="outside this role's scope"):
        WriteScope(allow=["app/**"]).check("tests/test_models.py")


def test_check_names_the_scope_in_the_message():
    """The reason has to say what the role may write, or nobody can act on it."""
    with pytest.raises(ScopeViolation) as excinfo:
        WriteScope(allow=["app/**"], deny=["tests/**"]).check("tests/x.py")
    assert "app/**" in str(excinfo.value)
    assert "tests/**" in str(excinfo.value)


def test_check_says_nothing_when_a_role_has_no_scope_at_all():
    with pytest.raises(ScopeViolation, match="allow=nothing"):
        WriteScope().check("a.py")


def test_check_returns_none_for_a_path_in_scope():
    assert WriteScope(allow=["app/**"]).check("app/models.py") is None


# -- the roles -------------------------------------------------------------


def test_a_judge_has_no_write_method(tmp_path):
    """Not because it was told not to. Because there is no path to call."""
    judge = Judge(name="judge", repo=tmp_path)
    assert not hasattr(judge, "write"), "adding write() ends the separation"


def test_a_judge_can_read(tmp_path):
    (tmp_path / "report.md").write_text("green", encoding="utf-8")
    assert Judge(name="judge", repo=tmp_path).read("report.md") == "green"


def test_a_doer_writes_inside_its_scope_and_makes_the_parent_directory(tmp_path):
    doer = Doer(name="doer", repo=tmp_path, scope=WriteScope(allow=["tickets/**"]))
    written = doer.write("tickets/nested/T001.md", "body")
    assert written.read_text(encoding="utf-8") == "body"
    assert doer.read("tickets/nested/T001.md") == "body"


def test_a_doer_refuses_a_write_outside_its_scope(tmp_path):
    doer = Doer(name="doer", repo=tmp_path, scope=WriteScope(allow=["tickets/**"]))
    with pytest.raises(ScopeViolation):
        doer.write("app/models.py", "body")
    assert not (tmp_path / "app").exists(), "a refused write must not leave a directory behind"


def test_violations_returns_only_the_disallowed_paths(tmp_path):
    doer = Doer(name="doer", repo=tmp_path, scope=WriteScope(allow=["app/**"], deny=["tests/**"]))
    changed = ["app/models.py", "tests/test_models.py", "README.md"]
    assert doer.violations(changed) == ["tests/test_models.py", "README.md"]


def test_a_role_summarizes_itself_by_class_and_name(tmp_path):
    assert Role(name="doer", repo=tmp_path).summary() == "role:doer"
    assert Judge(name="judge", repo=tmp_path).summary() == "judge:judge"


# -- the orchestrator's budget ---------------------------------------------


def test_the_orchestrator_counts_iterations(tmp_path):
    boss = Orchestrator(name="orchestrator", repo=tmp_path, budget_iterations=2)
    assert boss.start_iteration() == 1
    assert boss.iterations_left == 1
    assert boss.exhausted is False
    assert boss.start_iteration() == 2
    assert boss.iterations_left == 0
    assert boss.exhausted is True


def test_the_orchestrator_counts_dollars(tmp_path):
    boss = Orchestrator(name="orchestrator", repo=tmp_path, budget_usd=2.0)
    boss.spend(1.5)
    assert boss.usd_left == pytest.approx(0.5)
    assert boss.exhausted is False
    boss.spend(0.5)
    assert boss.usd_left == 0.0
    assert boss.exhausted is True


def test_an_overspend_clamps_at_zero_rather_than_going_negative(tmp_path):
    """A negative budget reads as "still has room" to anything doing `> 0`."""
    boss = Orchestrator(name="orchestrator", repo=tmp_path, budget_usd=1.0)
    boss.spend(5.0)
    assert boss.usd_left == 0.0
    assert boss.exhausted is True


def test_an_orchestrator_has_no_write_method(tmp_path):
    assert not hasattr(Orchestrator(name="orchestrator", repo=tmp_path), "write")
