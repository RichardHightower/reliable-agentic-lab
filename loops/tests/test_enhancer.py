"""Checks for the enhancer and its ticket-quality judge."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from loops import criteria, doers, gates
from loops.enhancer import run
from loops.ticket import parse

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_crm() -> Path | None:
    for path in (
        Path(os.environ["LOOP_TEST_REPO"]) if os.environ.get("LOOP_TEST_REPO") else None,
        REPO_ROOT / "work" / "northwind-field-crm",
        REPO_ROOT.parent / "northwind-field-crm",
    ):
        if path and (path / ".loop.yml").is_file():
            return path
    return None


CRM = _find_crm()
has_crm = pytest.mark.skipif(CRM is None, reason="no target repo; run `task setup`")


def test_a_thin_ticket_is_not_ready():
    ticket = parse("# Add due dates\n\nPlease add due dates.\n")
    verdict = criteria.judge(ticket)
    assert verdict.ready is False
    assert verdict.missing


def test_a_crash_report_is_read_as_a_bug():
    ticket = parse("# Saving a task crashes\n\nIt fails with an error every time.\n")
    assert criteria.classify(ticket.title, ticket.body) == criteria.BUG


def test_a_ticket_touching_a_form_is_read_as_a_user_interface_ticket():
    ticket = parse("# Add a field\n\nAdd a date input to the task form page.\n")
    assert criteria.classify(ticket.title, ticket.body) == criteria.UI


def test_a_user_interface_ticket_needs_a_wireframe():
    ticket = parse(
        "# Add a due date to the form\n\n"
        "Reps cannot see the due date on the task form page, so they miss follow-ups.\n"
        "Add a date input because a rep who cannot see it works the wrong task first.\n\n"
        "## Acceptance criteria\n\n- (AC-1) one\n- (AC-2) two\n"
    )
    verdict = criteria.judge(ticket)
    assert any("wireframe" in item for item in verdict.missing)


def test_the_suggestion_offers_a_wireframe_the_reader_can_copy():
    ticket = parse("# Add a date to the form page\n\nAdd it.\n")
    text = criteria.suggestion(ticket, criteria.judge(ticket))
    assert "New sales task" in text


def test_one_criterion_is_not_enough():
    """Two or more, so 'acceptance criteria' cannot be satisfied by a single line."""
    ticket = parse(
        "# A real title here\n\nA problem, and we should add it because it matters.\n\n"
        "## Acceptance criteria\n\n- (AC-1) only one\n"
    )
    assert any("acceptance criteria" in m for m in criteria.judge(ticket).missing)


@has_crm
def test_the_enhancer_stops_when_the_human_does_not_act():
    """Two identical rounds means another round changes nothing."""
    subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
    subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
    trace = run(repo=CRM, ticket_id="T001", incorporate=False, write_trace=False)
    assert trace["gate"] == gates.ESCALATE
    assert "same rows failed twice" in trace["reason"]


@has_crm
def test_the_enhancer_reaches_ready_when_the_human_acts():
    subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
    subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
    try:
        trace = run(repo=CRM, ticket_id="T001", incorporate=True, write_trace=False)
        assert trace["gate"] == gates.PASS, trace["reason"]
        assert trace["ready"] is True
    finally:
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
        subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)


class _CopyReadyBackend(doers.Backend):
    """A stand-in runtime port: same fixture-copy trick as --incorporate,
    but reached through the doer plug point instead of a hardcoded branch."""

    name = "fake-port"

    def __init__(self, repo: Path, ticket_id: str, folder: str = "tickets"):
        self._ready = sorted((repo / folder).glob(f"{ticket_id}*.ready.md"))[0]

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> doers.DoerResult:
        target = repo / "tickets" / self._ready.name.replace(".ready.md", ".md")
        target.write_text(self._ready.read_text(encoding="utf-8"), encoding="utf-8")
        return doers.DoerResult(wrote=[str(target)])


@has_crm
def test_the_enhancer_reaches_ready_through_the_doer_plug_point():
    """#2: a real Backend, not just --incorporate's canned copy, can drive
    the enhancer to ready. Proves the new plug point actually plugs in."""
    subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
    subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
    try:
        trace = run(
            repo=CRM,
            ticket_id="T001",
            doer=_CopyReadyBackend(CRM, "T001"),
            write_trace=False,
        )
        assert trace["gate"] == gates.PASS, trace["reason"]
        assert trace["ready"] is True
    finally:
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=CRM, check=False)
        subprocess.run(["git", "clean", "-qfd"], cwd=CRM, check=False)
