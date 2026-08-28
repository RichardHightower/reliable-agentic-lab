"""The poll loop, driven by a fake Backend and a fake gh.

Nothing here installs the SDK, sets a key, or reaches GitHub. The point of
putting the orchestrator in Python rather than in a skill is that its decisions
become facts a test can pin down, so this file pins them down: which tickets the
loop claims, when it keeps a draft, when it escalates, and what it records so the
next poll does not redo this one's work.

`FakeBackend` answers as the judge or the doer depending on the prompt, the same
way the real backend routes to a subagent by name.
"""

from __future__ import annotations

import json
from pathlib import Path

import enhancer
import pytest
from adapter import DoerResult
from enhancer import Enhancer, EnhancerError, Gh, Outcome, State, parse_judge

FEATURE = ["problem", "proposal", "value", "criteria"]

DRAFT = """\
---
id: T001
state: draft
loop: enhancer
---

# Sales tasks need due dates

Users keep asking when a task is due.
"""


# -- the fakes --------------------------------------------------------------


class FakeGh:
    """Records every call, so a test can assert what reached GitHub."""

    def __init__(self, issue: int = 7, comments: list[tuple[str, str]] | None = None):
        self.issue = issue
        self.comments = comments or []
        self.existing: int | None = issue
        self.posted: list[str] = []
        self.added: list[str] = []
        self.bodies: list[str] = []
        self.created: list[tuple[str, str]] = []
        self.closed: set[int] = set()
        self.open_issues: list[dict] = []

    def list_open(self):
        return list(self.open_issues)

    def find_issue(self, ticket_id):
        return self.existing

    def is_closed(self, issue):
        return issue in self.closed

    def create_issue(self, title, body):
        self.created.append((title, body))
        return self.issue

    def latest_comment(self, issue):
        return self.comments[-1] if self.comments else None

    def comment(self, issue, body):
        self.posted.append(body)

    def add_label(self, issue, label):
        self.added.append(label)

    def labels(self, issue):
        return list(self.added)

    def set_body(self, issue, body):
        self.bodies.append(body)


class FakeBackend:
    """Answers as the judge or the doer, chosen the way the real one routes.

    `judgments` is consumed one per judge call, so a test can say "the ticket is
    missing three fields, and the draft is missing one".
    """

    name = "fake"

    def __init__(
        self,
        judgments: list,
        draft: str | None = None,
        ok: bool = True,
        usd: float = 0.0,
        stop_reason: str | None = None,
        doer_stop_reason: str | None = None,
        raw_output: str = "",
    ):
        self.judgments = list(judgments)
        self.draft = draft
        self.ok = ok
        self.usd = usd
        self.stop_reason = stop_reason
        self.doer_stop_reason = doer_stop_reason
        self.raw_output = raw_output
        self.prompts: list[str] = []
        self.allows: list[list[str]] = []
        self.extras: list[dict] = []

    def run(self, *, repo: Path, prompt: str, allow: list[str], **extra) -> DoerResult:
        self.prompts.append(prompt)
        self.allows.append(list(allow))
        self.extras.append(dict(extra))
        if not self.ok:
            return DoerResult(
                ok=False, output="backend exploded", usd=self.usd, stop_reason=self.stop_reason
            )
        if "judge" in prompt:
            verdict = self.judgments.pop(0)
            structured = None if isinstance(verdict, str) else verdict
            return DoerResult(
                output=verdict if isinstance(verdict, str) else json.dumps(verdict),
                structured=structured,
                usd=self.usd,
                stop_reason=self.stop_reason,
                raw_output=self.raw_output,
            )
        return DoerResult(
            output=self.draft or "",
            wrote=[],
            usd=self.usd,
            stop_reason=self.doer_stop_reason or self.stop_reason,
            raw_output=self.raw_output,
        )


def judged(kind: str = "feature", present: list[str] | None = None) -> dict:
    return {"kind": kind, "present_fields": present or []}


@pytest.fixture
def target(tmp_path) -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "T001.md").write_text(DRAFT, encoding="utf-8")
    return tmp_path


def engine(target, backend, gh, budget: int = 3) -> Enhancer:
    return Enhancer(repo=target, backend=backend, gh=gh, budget=budget)


# -- parse_judge ------------------------------------------------------------


def test_a_bare_json_object_parses():
    assert parse_judge('{"kind": "bug", "present_fields": ["title"]}')["kind"] == "bug"


def test_a_fenced_json_object_parses():
    """The agent is told to reply with JSON only. Models fence it anyway."""
    text = 'Here is the verdict:\n```json\n{"kind": "ui", "present_fields": []}\n```\n'
    assert parse_judge(text)["kind"] == "ui"


def test_an_unfenced_object_with_prose_around_it_parses():
    assert parse_judge('Sure. {"kind": "feature", "present_fields": []} Done.')["kind"] == "feature"


def test_a_nested_object_is_read_to_its_matching_brace():
    """`rfind` on the last brace would swallow a trailing one and break the parse."""
    verdict = parse_judge('{"kind": "bug", "present_fields": [], "notes": {"a": 1}}')
    assert verdict["notes"] == {"a": 1}


def test_an_absent_field_list_defaults_to_empty_rather_than_raising():
    assert parse_judge('{"kind": "feature"}')["present_fields"] == []


def test_a_reply_with_no_object_at_all_fails_loudly():
    """Treating an unreadable verdict as an empty list marks every ticket unready."""
    with pytest.raises(EnhancerError, match="no JSON object"):
        parse_judge("I could not read the ticket.")


def test_a_broken_object_fails_loudly():
    with pytest.raises(EnhancerError, match="did not parse"):
        parse_judge('{"kind": "bug",}')


def test_an_object_with_no_kind_fails_loudly():
    with pytest.raises(EnhancerError, match="no `kind`"):
        parse_judge('{"present_fields": ["title"]}')


# -- discovery --------------------------------------------------------------


def test_open_tickets_finds_a_draft_this_loop_owns(target):
    assert [t.id for t in enhancer.open_tickets(target)] == ["T001"]


def test_open_tickets_skips_a_ticket_belonging_to_another_loop(target):
    (target / "tickets" / "T002.md").write_text(
        "---\nid: T002\nstate: draft\nloop: implementer\n---\n\n# Other\n", encoding="utf-8"
    )
    assert [t.id for t in enhancer.open_tickets(target)] == ["T001"]


def test_open_tickets_skips_a_ready_file(target):
    """A `.ready.md` file is the answer, not the question."""
    (target / "tickets" / "T003.ready.md").write_text(
        DRAFT.replace("T001", "T003"), encoding="utf-8"
    )
    assert [t.id for t in enhancer.open_tickets(target)] == ["T001"]


def test_open_tickets_skips_a_leftover_candidate(target):
    """A candidate carries the real ticket's front matter.

    A run that dies mid-draft leaves one behind. A glob that does not exclude it
    hands the next poll a second copy of a ticket no judge ever accepted.
    """
    (target / "tickets" / f"T001{enhancer.CANDIDATE_SUFFIX}").write_text(DRAFT, encoding="utf-8")
    assert [t.id for t in enhancer.open_tickets(target)] == ["T001"]


def test_open_tickets_skips_a_ticket_already_marked_ready(target):
    (target / "tickets" / "T001.md").write_text(DRAFT.replace("state: draft", "state: ready"))
    assert enhancer.open_tickets(target) == []


def test_a_repo_with_no_tickets_directory_is_rejected(tmp_path):
    with pytest.raises(EnhancerError, match="no tickets/ directory"):
        enhancer.open_tickets(tmp_path)


# -- front matter -----------------------------------------------------------


def test_strip_front_matter_removes_the_block():
    """GitHub renders a raw `---` block as a stray rule above the ticket."""
    assert enhancer.strip_front_matter(DRAFT).startswith("# Sales tasks")
    assert "loop: enhancer" not in enhancer.strip_front_matter(DRAFT)


def test_strip_front_matter_leaves_a_body_that_has_none():
    assert enhancer.strip_front_matter("# Just a title\n") == "# Just a title"


def test_set_front_matter_replaces_a_key_in_place(target):
    path = target / "tickets" / "T001.md"
    enhancer.set_front_matter(path, state="ready", loop="implementer")
    text = path.read_text(encoding="utf-8")
    assert "state: ready" in text
    assert "loop: implementer" in text
    assert "state: draft" not in text


def test_set_front_matter_adds_a_key_that_was_not_there(target):
    path = target / "tickets" / "T001.md"
    enhancer.set_front_matter(path, github_issue="42")
    assert "github_issue: 42" in path.read_text(encoding="utf-8")


def test_set_front_matter_keeps_the_body(target):
    path = target / "tickets" / "T001.md"
    enhancer.set_front_matter(path, state="ready")
    assert "# Sales tasks need due dates" in path.read_text(encoding="utf-8")


def test_set_front_matter_adds_a_block_to_a_file_that_has_none(tmp_path):
    """A draft that dropped its front matter costs one rewritten header, not the ticket."""
    path = tmp_path / "plain.md"
    path.write_text("# No front matter\n", encoding="utf-8")
    enhancer.set_front_matter(path, id="T001", state="draft")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nid: T001\nstate: draft\n---\n")
    assert "# No front matter" in text


# -- state ------------------------------------------------------------------


def test_a_ticket_with_no_state_file_is_on_its_first_poll(target):
    assert State.load(target, "T001").first_poll is True


def test_state_round_trips(target):
    State(github_issue=7, last_comment_id="12", round=2, previous_signature=["value"]).save(
        target, "T001"
    )
    loaded = State.load(target, "T001")
    assert (loaded.github_issue, loaded.last_comment_id, loaded.round) == (7, "12", 2)
    assert loaded.previous_signature == ["value"]
    assert loaded.first_poll is False


def test_clearing_state_removes_the_file(target):
    state = State(github_issue=7)
    state.save(target, "T001")
    state.clear(target, "T001")
    assert not State.path(target, "T001").exists()


def test_clearing_state_twice_is_not_an_error(target):
    State().clear(target, "T001")


# -- the first poll ---------------------------------------------------------


def test_a_poll_without_an_issue_does_not_create_one(target):
    """Creating tickets is task create-test-tickets. The loop only polls."""
    gh = FakeGh()
    gh.existing = None
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    [outcome] = engine(target, backend, gh).poll()
    assert gh.created == []
    assert outcome.status == "blocked"
    assert "create-test-tickets" in outcome.detail


def test_the_first_touch_adds_the_enhanced_label(target):
    gh = FakeGh()
    engine(target, FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT), gh).poll()
    assert gh.added[0] == "enhanced"


def test_a_poll_logs_progress_by_default(target, capsys):
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    engine(target, backend, FakeGh()).poll()
    output = capsys.readouterr().out
    assert "[enhancer] starting poll" in output
    assert "[enhancer] T001: running judge" in output
    assert "[enhancer] T001: running doer" in output


def test_the_first_poll_runs_a_round_with_no_comment(target):
    """A fresh ticket always gets one round, so the human has something to react to."""
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    [outcome] = (
        engine(target, FakeGh(), backend).poll()
        if False
        else engine(target, backend, FakeGh()).poll()
    )
    assert outcome.status == "waiting"
    assert "There is no comment yet" in backend.prompts[1]
    assert "read tickets/T001.md" in backend.prompts[1]
    assert "under app/" in backend.prompts[1]
    assert "<current-ticket path=\"tickets/T001.md\">" in backend.prompts[1]
    assert "T001-due-dates.ready.md" in backend.prompts[1]
    assert "Do not add a wireframe" in backend.prompts[1]


def test_a_ui_ticket_is_told_to_include_a_wireframe(target):
    backend = FakeBackend([judged(kind="ui"), judged(kind="ui", present=["problem"])], draft=DRAFT)
    engine(target, backend, FakeGh()).poll()
    assert "Include a concrete UI wireframe" in backend.prompts[1]


def test_raw_doer_events_are_written_before_the_candidate_is_judged(target):
    backend = FakeBackend(
        [judged(), judged(present=FEATURE)], draft=DRAFT, raw_output="raw SDK events"
    )
    engine(target, backend, FakeGh()).poll()
    assert (target / ".harness" / "last-doer-T001.md").read_text(encoding="utf-8") == "raw SDK events"


def test_a_stopped_doer_writes_its_diagnostic_before_escalating(target):
    backend = FakeBackend(
        [judged()], doer_stop_reason="query timeout", raw_output="partial SDK events"
    )
    gh = FakeGh()
    [outcome] = engine(target, backend, gh).poll()
    assert outcome.status == "escalated"
    assert "needs-human" in gh.added
    assert (target / ".harness" / "last-doer-T001.md").read_text(encoding="utf-8") == "partial SDK events"


def test_a_draft_with_literal_escaped_layout_blocks_only_that_ticket(target):
    (target / "tickets" / "T002.md").write_text(DRAFT.replace("T001", "T002"), encoding="utf-8")
    backend = FakeBackend(
        [judged(), judged(present=FEATURE)], draft="---\n\\n30\\tbroken wireframe"
    )
    gh = FakeGh()
    # The shared fake normally exposes one label list. This case needs the
    # second ticket's distinct issue to remain unblocked after T001 escalates.
    gh.labels = lambda issue: []
    outcomes = engine(target, backend, gh).poll()
    assert [(outcome.ticket_id, outcome.status) for outcome in outcomes] == [
        ("T001", "escalated"),
        ("T002", "waiting"),
    ]
    assert "literal escaped layout" in outcomes[0].detail
    assert "needs-human" in gh.added
    assert gh.bodies == []


def test_strip_reply_keeps_an_embedded_wireframe_fence():
    import turns

    ticket = "# Notes\n\n## Wireframe\n\n```\n+-----+\n| UI |\n+-----+\n```\n\n## Acceptance criteria\n\n- (AC-1) works\n"
    assert turns.strip_reply(ticket) == ticket.strip()


def test_strip_reply_unwraps_only_a_whole_markdown_reply():
    import turns

    assert turns.strip_reply("```markdown\n# Ticket\n```") == "# Ticket"


def test_the_first_poll_leaves_no_comment_id_behind(target):
    """A finished enhance round asks for LGTM. That is not a GitHub comment id."""
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    engine(target, backend, FakeGh()).poll()
    assert State.load(target, "T001").last_comment_id == "asked-lgtm"


# -- keeping or discarding a draft ------------------------------------------


def test_a_strictly_better_draft_replaces_the_ticket(target):
    better = DRAFT.replace("# Sales", "# Better sales")
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=better)
    gh = FakeGh()
    engine(target, backend, gh).poll()
    assert "# Better sales" in (target / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert gh.bodies, "the issue body has to show the ticket a reviewer is judging"


def test_a_draft_that_is_not_better_leaves_the_ticket_alone(target):
    """ "Not worse" is not good enough. A trade looks like motion and is not."""
    backend = FakeBackend(
        [judged(present=["problem"]), judged(present=["proposal"])],
        draft=DRAFT.replace("# Sales", "# Traded"),
    )
    gh = FakeGh()
    engine(target, backend, gh).poll()
    assert "# Traded" not in (target / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert "did not clear the rubric" in gh.posted[0]
    assert gh.bodies == [], "an unaccepted draft must not reach the issue body"


def test_an_accepted_draft_keeps_the_front_matter_the_loop_owns(target):
    """The doer is told to keep it. A model that forgets must not cost the issue number."""
    stripped = "# Better\n\nBody with no front matter at all.\n"
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=stripped)
    engine(target, backend, FakeGh(issue=7)).poll()
    text = (target / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert "github_issue: 7" in text
    assert "loop: enhancer" in text
    assert "state: draft" in text


def test_the_candidate_file_is_always_cleaned_up(target):
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    engine(target, backend, FakeGh()).poll()
    assert not (target / "tickets" / f"T001{enhancer.CANDIDATE_SUFFIX}").exists()


def test_the_candidate_is_cleaned_up_even_when_judging_it_fails(target):
    backend = FakeBackend([judged(), "not json at all"], draft=DRAFT)
    with pytest.raises(EnhancerError):
        engine(target, backend, FakeGh()).poll()
    assert not (target / "tickets" / f"T001{enhancer.CANDIDATE_SUFFIX}").exists()


def test_the_doer_is_scoped_to_tickets_and_the_judge_to_nothing(target):
    """The hook reads this allow list. A doer handed `**` is an unscoped doer."""
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    engine(target, backend, FakeGh()).poll()
    judge_allow, doer_allow = backend.allows[0], backend.allows[1]
    assert judge_allow == [], "the judge holds no write tool, so it gets no scope"
    assert doer_allow == [], "the doer holds no write tool; Python writes the candidate"


def test_a_doer_that_writes_nothing_is_an_error_not_a_silent_pass(target):
    backend = FakeBackend([judged()], draft=None)
    with pytest.raises(EnhancerError, match="wrote no candidate"):
        engine(target, backend, FakeGh()).poll()


def test_a_failed_backend_stops_the_ticket(target):
    with pytest.raises(EnhancerError, match="the judge failed"):
        engine(target, FakeBackend([], ok=False), FakeGh()).poll()


# -- LGTM and the ready exit ------------------------------------------------


def test_lgtm_on_a_green_rubric_releases_the_ticket(target):
    State(github_issue=7, last_comment_id="1").save(target, "T001")
    gh = FakeGh(comments=[("2", "LGTM")])
    engine(target, FakeBackend([judged(present=FEATURE)]), gh).poll()
    text = (target / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert "state: ready" in text
    assert "loop: implementer" in text, "a ticket left at loop: enhancer is never picked up next"
    assert "ready" in gh.added
    assert not State.path(target, "T001").exists()


def test_lgtm_on_a_red_rubric_is_never_consumed(target):
    """A human's LGTM can only confirm a ticket the rubric already accepts."""
    State(github_issue=7, last_comment_id="1").save(target, "T001")
    gh = FakeGh(comments=[("2", "LGTM")])
    backend = FakeBackend([judged(present=["problem"]), judged(present=["problem"])], draft=DRAFT)
    [outcome] = engine(target, backend, gh).poll()
    assert outcome.status == "waiting"
    assert "state: draft" in (target / "tickets" / "T001.md").read_text(encoding="utf-8")
    assert "ready" not in gh.added


def test_a_green_rubric_with_no_lgtm_asks_for_one(target):
    gh = FakeGh()
    [outcome] = engine(target, FakeBackend([judged(present=FEATURE)]), gh).poll()
    assert outcome.status == "waiting"
    assert "LGTM" in gh.posted[0]
    assert "enhanced" in gh.added
    assert State.load(target, "T001").last_comment_id == "asked-lgtm"


def test_a_second_poll_on_a_green_ticket_does_not_ask_again(target):
    State(github_issue=7, last_comment_id="asked-lgtm").save(target, "T001")
    gh = FakeGh()
    gh.added.append("enhanced")
    [outcome] = engine(target, FakeBackend([judged(present=FEATURE)]), gh).poll()
    assert outcome.status == "waiting"
    assert gh.posted == []


# -- which ticket, and which issue (#104, #105) -----------------------------


def test_naming_a_ready_ticket_with_ticket_skips_it(target):
    """`--ticket` chooses which ticket to look at. It is not a state override.

    Discovery already refuses a ready ticket. Without the same rule on this
    path, `--ticket T001` re-runs a finished ticket as a fresh draft, and the
    re-run opens a second issue for it. That is how #104 was found live.
    """
    (target / "tickets" / "T001.md").write_text(
        DRAFT.replace("state: draft", "state: ready").replace("loop: enhancer", "loop: implementer")
    )
    gh = FakeGh()
    [outcome] = engine(target, FakeBackend([]), gh).poll("T001")
    assert outcome.status == "skipped"
    assert "ready" in outcome.detail and "implementer" in outcome.detail
    assert gh.created == [], "a finished ticket must not open an issue"
    assert gh.posted == [], "and must not draw a comment"


def test_the_frontmatter_issue_is_used_after_the_state_file_is_deleted(target):
    """Frontmatter outlives the state file, which the LGTM pass deletes.

    With no state file and no frontmatter fallback, the loop drops to a search.
    A search that misses hands it to `create_issue`, which is the duplicate.
    """
    (target / "tickets" / "T001.md").write_text(
        DRAFT.replace("loop: enhancer", "loop: enhancer\ngithub_issue: 8")
    )
    gh = FakeGh(comments=[("2", "looks good to me")])
    gh.existing = None  # the search finds nothing, as it did on the live run
    [outcome] = engine(target, FakeBackend([judged(present=FEATURE)]), gh).poll("T001")
    assert gh.created == [], "issue 8 is on the ticket, so nothing should be created"
    assert outcome.status == "waiting"


def test_a_closed_issue_stops_the_ticket_rather_than_creating_a_second_one(target):
    """Closing an issue is not how you reset a ticket, so say so and stop.

    #105: the search used `--state open`, so a closed issue was invisible and
    the next poll created a duplicate. Issue 10 duplicated issue 8.
    """
    State(github_issue=8, last_comment_id="1").save(target, "T001")
    gh = FakeGh()
    gh.closed = {8}
    [outcome] = engine(target, FakeBackend([]), gh).poll("T001")
    assert outcome.status == "blocked"
    assert "8 is closed" in outcome.detail
    assert gh.created == [], "never a second issue for a title that already has one"
    assert gh.posted == [], "and never a comment on a closed issue"


# -- no new comment ---------------------------------------------------------


def test_a_not_ready_ticket_is_enhanced_without_a_comment(target):
    """Comments do not trigger edits. Missing work does."""
    State(github_issue=7, round=1).save(target, "T001")
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    gh = FakeGh(comments=[])
    [outcome] = engine(target, backend, gh).poll()
    assert outcome.status == "waiting"
    assert backend.prompts, "a red ticket must still be enhanced"
    assert "There is no comment yet" in backend.prompts[1]


def test_a_human_comment_does_not_trigger_an_edit(target):
    State(github_issue=7, round=1).save(target, "T001")
    backend = FakeBackend([judged(present=FEATURE)])
    gh = FakeGh(comments=[("9", "please add more criteria")])
    [outcome] = engine(target, backend, gh).poll()
    assert outcome.status == "waiting"
    assert outcome.detail == "ready, waiting for LGTM"
    assert len(backend.prompts) == 1, "green ticket: judge only, no doer"


def test_a_ticket_already_escalated_waits_for_a_human(target):
    State(github_issue=7, last_comment_id="1", round=1).save(target, "T001")
    gh = FakeGh(comments=[("2", "any update?")])
    gh.added.append("needs-human")
    [outcome] = engine(target, FakeBackend([]), gh).poll()
    assert outcome.status == "escalated"


# -- the exits --------------------------------------------------------------


def test_the_same_gaps_two_rounds_running_escalates(target):
    """A loop that keeps finding the same gap is not converging, it is stuck."""
    State(github_issue=7, last_comment_id="1", round=1, previous_signature=sorted(FEATURE)).save(
        target, "T001"
    )
    gh = FakeGh(comments=[("2", "still here")])
    backend = FakeBackend([judged(), judged()], draft=DRAFT)
    [outcome] = engine(target, backend, gh).poll()
    assert outcome.status == "escalated"
    assert outcome.detail == "same signature two rounds running"
    assert "needs-human" in gh.added


def test_a_spent_budget_escalates(target):
    State(github_issue=7, last_comment_id="1", round=2, previous_signature=["problem"]).save(
        target, "T001"
    )
    gh = FakeGh(comments=[("3", "again")])
    backend = FakeBackend([judged(), judged()], draft=DRAFT)
    [outcome] = engine(target, backend, gh, budget=3).poll()
    assert outcome.status == "escalated"
    assert outcome.detail == "budget spent"


def test_a_round_that_makes_progress_records_it_for_the_next_poll(target):
    State(github_issue=7, round=0, previous_signature=None).save(target, "T001")
    gh = FakeGh()
    backend = FakeBackend([judged(), judged(present=["problem"])], draft=DRAFT)
    engine(target, backend, gh).poll()
    saved = State.load(target, "T001")
    assert saved.round == 1
    assert saved.previous_signature == ["criteria", "proposal", "value"]
    assert "enhanced" in gh.added


def test_the_doer_does_not_see_a_human_comment(target):
    """A comment is not an instruction. The doer investigates the app."""
    State(github_issue=7, round=1).save(target, "T001")
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    engine(target, backend, FakeGh(comments=[("2", "due dates are optional")]))._one(
        enhancer.open_tickets(target)[0], None
    )
    assert "due dates are optional" not in backend.prompts[1]
    assert "There is no comment yet" in backend.prompts[1]


# -- selecting one ticket ---------------------------------------------------


def test_naming_a_ticket_acts_on_only_that_one(target):
    (target / "tickets" / "T900.md").write_text(DRAFT.replace("T001", "T900"), encoding="utf-8")
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    outcomes = engine(target, backend, FakeGh()).poll("T001")
    assert [o.ticket_id for o in outcomes] == ["T001"]


def test_naming_a_ticket_that_is_not_there_is_an_error(target):
    with pytest.raises(EnhancerError, match="no ticket T404"):
        engine(target, FakeBackend([]), FakeGh()).poll("T404")


def test_a_simulated_comment_needs_a_named_ticket(target):
    """It replaces one issue's newest comment. Over a whole poll it means nothing."""
    with pytest.raises(EnhancerError, match="needs --ticket"):
        engine(target, FakeBackend([]), FakeGh()).poll(simulate_comment="hi")


def test_a_simulated_lgtm_on_a_green_ticket_releases_it(target):
    backend = FakeBackend([judged(present=FEATURE)])
    gh = FakeGh(comments=[("99", "a real comment nobody should read")])
    [outcome] = engine(target, backend, gh).poll("T001", simulate_comment="LGTM")
    assert outcome.status == "passed"
    assert "ready" in gh.added


def test_a_simulated_non_lgtm_does_not_drive_the_doer(target):
    backend = FakeBackend([judged(), judged(present=FEATURE)], draft=DRAFT)
    gh = FakeGh()
    engine(target, backend, gh).poll("T001", simulate_comment="make it optional")
    assert "make it optional" not in "".join(backend.prompts)


# -- the report -------------------------------------------------------------


def test_an_outcome_prints_as_one_aligned_line():
    assert str(Outcome("T001", "passed", "why")).split() == ["T001", "passed", "why"]


def test_a_poll_over_an_empty_tickets_directory_reports_nothing(tmp_path):
    (tmp_path / "tickets").mkdir()
    assert engine(tmp_path, FakeBackend([]), FakeGh()).poll() == []


def test_a_github_ui_issue_with_no_local_file_is_picked_up(tmp_path):
    """A human filing an issue in the GitHub UI is enough. No seed file required."""
    (tmp_path / "tickets").mkdir()
    gh = FakeGh(issue=31)
    gh.existing = 31
    gh.open_issues = [
        {
            "number": 31,
            "title": "Customers cannot filter by region",
            "body": "Need a filter on the customer list.",
            "labels": [],
        }
    ]
    better = (
        "---\nid: T31\nstate: draft\nloop: enhancer\n---\n\n"
        "# Customers cannot filter by region\n\nNeed a filter.\n"
    )
    backend = FakeBackend([judged(), judged(present=["problem"])], draft=better)
    [outcome] = engine(tmp_path, backend, gh).poll()
    text = (tmp_path / "tickets" / "T31.md").read_text(encoding="utf-8")
    assert "id: T31" in text
    assert "github_issue: 31" in text
    assert outcome.status == "waiting"
    assert gh.added[0] == "enhanced"


def test_a_github_ui_issue_keeps_a_bracket_id_from_its_title(tmp_path):
    (tmp_path / "tickets").mkdir()
    gh = FakeGh(issue=40)
    gh.existing = 40
    gh.open_issues = [
        {
            "number": 40,
            "title": "[T903] Export invoices as PDF",
            "body": "Reps want a PDF.",
            "labels": [],
        }
    ]
    backend = FakeBackend([judged(), judged(present=["problem"])], draft=DRAFT.replace("T001", "T903"))
    engine(tmp_path, backend, gh).poll()
    assert (tmp_path / "tickets" / "T903.md").exists()
    assert not (tmp_path / "tickets" / "T40.md").exists()


def test_a_ready_github_issue_is_not_ingested_as_a_new_draft(tmp_path):
    (tmp_path / "tickets").mkdir()
    gh = FakeGh()
    gh.open_issues = [
        {"number": 9, "title": "Done work", "body": "shipped", "labels": ["ready", "enhanced"]}
    ]
    assert engine(tmp_path, FakeBackend([]), gh).poll() == []
    assert list((tmp_path / "tickets").glob("*.md")) == []


def test_a_retired_github_issue_is_not_ingested(tmp_path):
    (tmp_path / "tickets").mkdir()
    gh = FakeGh()
    gh.open_issues = [
        {
            "number": 8,
            "title": "[retired-T900-1] Search crashes on an empty query",
            "body": "old",
            "labels": [],
        }
    ]
    assert engine(tmp_path, FakeBackend([]), gh).poll() == []


# -- the gh wrapper ---------------------------------------------------------


def test_the_gh_wrapper_names_the_repo_on_every_call(monkeypatch):
    """A `gh` call with no `--repo` acts on whatever the cwd happens to be."""
    seen = []

    class _Proc:
        returncode = 0
        stdout = '[{"number": 12}]'
        stderr = ""

    monkeypatch.setattr(
        enhancer.subprocess, "run", lambda argv, **kw: (seen.append(argv), _Proc())[1]
    )
    assert Gh("me", "crm").find_issue("T001") == 12
    assert "--repo" in seen[0]
    assert "me/crm" in seen[0]


def test_the_gh_wrapper_reports_a_failure_rather_than_swallowing_it(monkeypatch):
    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "not authenticated"

    monkeypatch.setattr(enhancer.subprocess, "run", lambda argv, **kw: _Proc())
    with pytest.raises(EnhancerError, match="not authenticated"):
        Gh("me", "crm").find_issue("T001")


def test_an_empty_issue_search_finds_nothing(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "[]"
        stderr = ""

    monkeypatch.setattr(enhancer.subprocess, "run", lambda argv, **kw: _Proc())
    assert Gh("me", "crm").find_issue("T001") is None


# -- the rest of the gh wrapper --------------------------------------------


@pytest.fixture
def gh_calls(monkeypatch):
    """Record every `gh` argv and hand back a canned stdout per call."""
    calls: list[list[str]] = []
    replies: list[str] = []

    class _Proc:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _Proc(replies.pop(0) if replies else "")

    monkeypatch.setattr(enhancer.subprocess, "run", fake_run)
    return calls, replies


def test_creating_an_issue_returns_the_number_from_its_url(gh_calls):
    calls, replies = gh_calls
    replies.extend(["", "", "", "https://github.com/me/crm/issues/31"])
    assert Gh("me", "crm").create_issue("[T001] Title", "Body") == 31
    assert [call[1] for call in calls[:3]] == ["label", "label", "label"]
    assert "--label" not in calls[3]


def test_a_label_that_already_exists_does_not_stop_the_create(monkeypatch):
    """`gh label create` fails on a label that is already there. That is fine."""
    seen = []

    class _Proc:
        def __init__(self, argv):
            self.returncode = 1 if argv[1] == "label" else 0
            self.stdout = "https://github.com/me/crm/issues/9"
            self.stderr = "already exists"

    monkeypatch.setattr(
        enhancer.subprocess, "run", lambda argv, **kw: (seen.append(argv), _Proc(argv))[1]
    )
    assert Gh("me", "crm").create_issue("t", "b") == 9


def test_the_newest_comment_comes_back_as_an_id_and_a_body(gh_calls):
    _, replies = gh_calls
    replies.append('{"id": 4242, "body": "make it optional"}')
    assert Gh("me", "crm").latest_comment(7) == ("4242", "make it optional")


def test_an_issue_with_no_comments_comes_back_as_none(gh_calls):
    assert Gh("me", "crm").latest_comment(7) is None


def test_labels_come_back_as_plain_names(gh_calls):
    _, replies = gh_calls
    replies.append('{"labels": [{"name": "enhanced"}, {"name": "needs-human"}]}')
    assert Gh("me", "crm").labels(7) == ["enhanced", "needs-human"]


def test_an_issue_with_no_labels_comes_back_empty(gh_calls):
    assert Gh("me", "crm").labels(7) == []


def test_commenting_and_labeling_and_setting_a_body_all_name_the_repo(gh_calls):
    calls, _ = gh_calls
    api = Gh("me", "crm")
    api.comment(7, "hello")
    api.add_label(7, "ready")
    api.set_body(7, "new body")
    for call in calls:
        assert "me/crm" in call, f"{call} would act on whatever the cwd happens to be"


# -- cost, max turns, complete ----------------------------------------------


def test_cost_budget_stops_a_ticket_that_is_not_ready(target):
    gh = FakeGh()
    backend = FakeBackend([judged()], usd=2.0)
    [outcome] = Enhancer(repo=target, backend=backend, gh=gh, max_usd=2.0).poll()
    assert outcome.status == "escalated"
    assert outcome.detail == "cost budget spent"
    assert "needs-human" in gh.added


def test_each_ticket_gets_a_fresh_cost_budget(target):
    (target / "tickets" / "T002.md").write_text(DRAFT.replace("T001", "T002"), encoding="utf-8")
    backend = FakeBackend([judged(present=FEATURE), judged(present=FEATURE)], usd=0.5)
    outcomes = Enhancer(repo=target, backend=backend, gh=FakeGh(), max_usd=1.0).poll()
    assert [outcome.ticket_id for outcome in outcomes] == ["T001", "T002"]
    assert [extra["max_budget_usd"] for extra in backend.extras] == [1.0, 1.0]


def test_cost_budget_does_not_block_a_completed_ticket(target):
    """Completing wins. A green ticket with LGTM is done even if this poll cost money."""
    gh = FakeGh()
    backend = FakeBackend([judged(present=FEATURE)], usd=5.0)
    [outcome] = Enhancer(
        repo=target, backend=backend, gh=gh, max_usd=1.0
    ).poll("T001", simulate_comment="LGTM")
    assert outcome.status == "passed"


def test_max_turns_stops_before_the_doer_runs(target):
    backend = FakeBackend([judged(), judged(present=["problem", "proposal", "value", "criteria"])], draft=DRAFT)
    [outcome] = Enhancer(
        repo=target, backend=backend, gh=FakeGh(), max_turns=1
    ).poll()
    assert outcome.status == "escalated"
    assert outcome.detail == "max turns"
    assert len(backend.prompts) == 1, "the doer must not run after max turns"


def test_a_sdk_max_turns_result_escalates(target):
    backend = FakeBackend([judged()], ok=False, stop_reason="max turns")
    [outcome] = engine(target, backend, FakeGh()).poll()
    assert outcome.status == "escalated"
    assert outcome.detail == "max turns"
