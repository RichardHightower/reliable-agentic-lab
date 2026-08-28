"""The checkpoint. A nine stage run must survive being killed."""

from __future__ import annotations

import contextlib
import json

import state as pstate

ORDER = ["plan", "search", "verify", "write"]


def test_resume_point_is_the_first_incomplete_stage(tmp_path):
    """Not current_stage + 1. A crashed stage is not a finished stage."""
    st = pstate.PaperState.load_or_create(tmp_path)
    st.mark_complete("plan")
    st.mark_failed("search", "boom")
    assert st.current_stage == "search"
    assert st.first_incomplete(ORDER) == "search"


def test_every_stage_done_returns_none(tmp_path):
    st = pstate.PaperState.load_or_create(tmp_path)
    for name in ORDER:
        st.mark_complete(name)
    assert st.first_incomplete(ORDER) is None


def test_skipped_counts_as_done(tmp_path):
    st = pstate.PaperState.load_or_create(tmp_path)
    st.mark_complete("plan")
    st.mark_skipped("search", "nothing to search")
    assert st.first_incomplete(ORDER) == "verify"


def test_cost_survives_a_reload(tmp_path):
    st = pstate.PaperState.load_or_create(tmp_path, slug="s", topic="t")
    st.mark_complete("plan", cost_usd=0.25)
    st.spend(0.5, calls=2)
    st.save()

    again = pstate.PaperState.load_or_create(tmp_path)
    assert again.total_cost_usd == 0.75
    assert again.total_calls == 2
    assert again.is_complete("plan")
    assert again.topic == "t"


def test_attempts_count_retries(tmp_path):
    st = pstate.PaperState.load_or_create(tmp_path)
    st.mark_in_progress("write")
    st.mark_in_progress("write")
    st.mark_in_progress("write")
    assert st.attempts("write") == 3
    assert st.total_retries == 2


def test_save_is_atomic(tmp_path, monkeypatch):
    """A crash mid-save must leave the previous checkpoint readable."""
    st = pstate.PaperState.load_or_create(tmp_path)
    st.mark_complete("plan")
    st.save()
    good = json.loads((tmp_path / pstate.STATE_FILE).read_text())

    def explode(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(pstate.os, "replace", explode)
    st.mark_complete("search")
    with contextlib.suppress(OSError):
        st.save()

    assert json.loads((tmp_path / pstate.STATE_FILE).read_text()) == good
    assert not list(tmp_path.glob("*.tmp.*")), "the temp file must not linger"


def test_artifacts_are_recorded(tmp_path):
    st = pstate.PaperState.load_or_create(tmp_path)
    st.record("paper", tmp_path / "whitepaper.md")
    st.save()
    again = pstate.PaperState.load_or_create(tmp_path)
    assert again.artifacts["paper"].endswith("whitepaper.md")
