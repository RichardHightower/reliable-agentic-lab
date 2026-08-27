"""Reading a ticket and its acceptance criteria.

The enhancer grooms a draft. Loading the answer instead of the question makes
the enhancer look like it works when it has done nothing, so `load()`'s
preference order gets a direct check in both directions.
"""

from __future__ import annotations

import pytest
import ticket as ticket_mod
from ticket import Criterion, Ticket, load, parse

DRAFT = """\
---
id: T001
state: draft
kind: feature
---
# Export contacts to CSV

A rep wants the contact list as a file.

## Success criteria

- The export includes every contact the rep can see.
- (AC-7) The file opens in Excel without a warning.
"""


@pytest.fixture
def repo(tmp_path):
    """A tickets/ directory holding the draft above, and nothing else.

    Local rather than in conftest.py. `load()` cares about the files in
    tickets/, not about the contract, so this fixture stays as small as the
    thing under test.
    """
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "T001.md").write_text(DRAFT, encoding="utf-8")
    return tmp_path


# -- frontmatter -----------------------------------------------------------


def test_frontmatter_supplies_the_id_and_the_state():
    parsed = parse(DRAFT)
    assert parsed.id == "T001"
    assert parsed.state == "draft"


def test_frontmatter_is_stripped_from_the_body():
    assert "kind: feature" not in parse(DRAFT).body
    assert parse(DRAFT).body.startswith("# Export contacts to CSV")


def test_the_ticket_id_argument_fills_in_when_frontmatter_is_silent():
    assert parse("# A title\n", ticket_id="T042").id == "T042"


def test_a_ticket_with_no_frontmatter_and_no_criteria_is_a_draft():
    assert parse("# A title\n").state == "draft"


def test_a_ticket_with_criteria_and_no_frontmatter_reads_as_ready():
    """Criteria are the contract. A ticket that has them is groomed."""
    parsed = parse("# A title\n\n## Acceptance criteria\n\n- It works.\n")
    assert parsed.state == "ready"
    assert parsed.ready is True


def test_a_declared_state_beats_the_inference():
    parsed = parse(DRAFT)
    assert parsed.state == "draft"
    assert parsed.ready is True, "criteria alone make a ticket usable"


def test_a_draft_with_no_criteria_is_not_ready():
    assert parse("# A title\n").ready is False


# -- title and criteria ----------------------------------------------------


def test_the_title_comes_from_the_first_heading():
    assert parse(DRAFT).title == "Export contacts to CSV"


def test_a_ticket_with_no_heading_has_an_empty_title():
    assert parse("just prose\n").title == ""


def test_criteria_are_numbered_from_one():
    assert parse("# T\n\n## Success criteria\n\n- first\n- second\n").criterion_ids == [
        "AC-1",
        "AC-2",
    ]


def test_an_explicit_id_in_the_ticket_wins():
    """When the ticket writes its own ids, a step can point at one and stay valid."""
    criteria = parse(DRAFT).criteria
    assert criteria[0] == Criterion("AC-1", "The export includes every contact the rep can see.")
    assert criteria[1] == Criterion("AC-7", "The file opens in Excel without a warning.")


def test_an_acceptance_criteria_heading_works_too():
    assert parse("# T\n\n## Acceptance criteria\n\n- one\n").criterion_ids == ["AC-1"]


def test_the_heading_match_ignores_case():
    assert parse("# T\n\n## SUCCESS CRITERIA\n\n- one\n").criterion_ids == ["AC-1"]


def test_bullets_under_another_heading_are_not_criteria():
    """Collecting every bullet in the file turns notes into a contract."""
    parsed = parse("# T\n\n## Notes\n\n- not a criterion\n\n## Success criteria\n\n- real\n")
    assert [c.text for c in parsed.criteria] == ["real"]


def test_a_star_bullet_counts_as_a_bullet():
    assert parse("# T\n\n## Success criteria\n\n* starred\n").criterion_ids == ["AC-1"]


def test_for_prompt_restates_the_criteria_with_their_ids():
    text = parse(DRAFT).for_prompt()
    assert text.startswith("# T001: Export contacts to CSV")
    assert "- (AC-7) The file opens in Excel without a warning." in text


def test_for_prompt_omits_the_criteria_section_when_there_are_none():
    assert "Acceptance criteria" not in parse("# T\n", ticket_id="T1").for_prompt()


# -- load ------------------------------------------------------------------


def test_load_prefers_the_ready_file_by_default(repo):
    """The implementer wants the ready contract."""
    (repo / "tickets" / "T001.ready.md").write_text(
        "# Ready version\n\n## Success criteria\n\n- done\n", encoding="utf-8"
    )
    assert load(repo, "T001").title == "Ready version"


def test_load_prefers_the_draft_when_the_enhancer_asks(repo):
    """The enhancer wants the draft it is grooming, not the answer."""
    (repo / "tickets" / "T001.ready.md").write_text("# Ready version\n", encoding="utf-8")
    assert load(repo, "T001", prefer_ready=False).title == "Export contacts to CSV"


def test_load_records_the_path_it_read(repo):
    assert load(repo, "T001").path == repo / "tickets" / "T001.md"


def test_load_rejects_a_missing_tickets_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="no tickets/ directory"):
        load(tmp_path, "T001")


def test_load_rejects_a_ticket_id_that_is_not_there(repo):
    with pytest.raises(FileNotFoundError, match="no ticket T999"):
        load(repo, "T999")


def test_load_reads_a_custom_folder(tmp_path):
    (tmp_path / "issues").mkdir()
    (tmp_path / "issues" / "T001.md").write_text("# From issues\n", encoding="utf-8")
    assert load(tmp_path, "T001", folder="issues").title == "From issues"


def test_a_ticket_defaults_to_a_draft_with_no_criteria():
    assert Ticket(id="T001").state == "draft"
    assert Ticket(id="T001").criterion_ids == []


def test_the_front_matter_pattern_only_matches_at_the_start():
    """A `---` divider halfway down a body is a rule, not frontmatter."""
    assert ticket_mod.FRONT_MATTER.match("# T\n\n---\nid: nope\n---\n") is None
