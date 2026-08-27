"""Extra credit 3. The groomer, on GitHub Actions and locally."""

from __future__ import annotations

import pytest

from solutions.extra_credit import TARGET
from solutions.extra_credit import github_api as gh
from solutions.extra_credit.fake_github import FakeGitHub
from solutions.extra_credit.s_ext_3_groom_ticket import groom_ticket

# The local run drives the real engine against the cloned target repo.
# The GitHub paths use a fake client and need nothing.
needs_target = pytest.mark.skipif(
    not TARGET.exists(), reason="run `task setup` to clone the target repo"
)

READY_BODY = (
    "## Problem\n\nSales reps cannot record when a task is due.\n\n"
    "## Proposal\n\nAdd an optional due date to a sales task.\n\n"
    "## Value\n\nWorth doing because nobody can see what is overdue.\n\n"
    "## Acceptance criteria\n\n"
    "- (AC-1) A sales task has a due_date column that accepts null.\n"
    "- (AC-2) The API returns the due date on read.\n"
)


@pytest.fixture
def restored_ticket():
    """Put the target's ticket back after `--incorporate` rewrites it.

    The clone in `work/` is shared with the labs, and Module 1 starts from the
    draft. A test that leaves it groomed breaks the demo for whoever runs next.
    """
    path = TARGET / "tickets" / "T001.md"
    before = path.read_bytes()
    try:
        yield path
    finally:
        path.write_bytes(before)


@needs_target
def test_local_groom_with_incorporate(tmp_path, monkeypatch, restored_ticket):
    monkeypatch.setattr(groom_ticket, "WORK", tmp_path)
    payload = groom_ticket.run_local("T001", incorporate=True, budget=2)
    assert payload["ready"] is True
    assert payload["mode"] == "local"
    assert (tmp_path / "last-groom.json").exists()


def test_github_groom_comments_when_thin():
    fake = FakeGitHub({"title": "Due dates", "body": "please add them", "labels": []})
    payload = groom_ticket.run_github(7, budget=3, client=fake)
    assert payload["exit"] == "commented"
    assert payload["ready"] is False
    assert fake.comments
    assert gh.IN_PROGRESS in fake.added
    assert gh.IN_PROGRESS in fake.removed


def test_github_groom_labels_ready():
    fake = FakeGitHub({"title": "Due dates", "body": READY_BODY, "labels": []})
    payload = groom_ticket.run_github(8, budget=3, client=fake)
    assert payload["exit"] == "ready label"
    assert "ready" in fake.added


def test_github_groom_skips_in_progress():
    fake = FakeGitHub({"title": "x", "body": "y", "labels": [{"name": gh.IN_PROGRESS}]})
    payload = groom_ticket.run_github(9, budget=3, client=fake)
    assert payload["exit"] == "skipped concurrent run"
    assert fake.comments == []


def test_github_groom_stops_at_budget():
    fake = FakeGitHub({"title": "x", "body": "y", "labels": [{"name": "agent-attempts-3"}]})
    payload = groom_ticket.run_github(10, budget=3, client=fake)
    assert payload["exit"] == "budget"
    assert "Max attempts" in fake.comments[0]
