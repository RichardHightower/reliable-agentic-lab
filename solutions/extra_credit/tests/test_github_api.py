"""The shared GitHub helpers. Every assignment reads them."""

from __future__ import annotations

from solutions.extra_credit import github_api as gh


def test_attempt_count():
    assert gh.attempt_count(["ready", "agent-attempts-2"]) == 2
    assert gh.attempt_count([]) == 0
