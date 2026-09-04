"""Outline schema, validator, judge loop, approval stamp, coverage row."""

from __future__ import annotations

import json
from pathlib import Path

import load_agents
import outline as outlines
import paper
import pytest


def sample_section(sid="s1", heading="The problem", **over):
    section = {
        "id": sid,
        "heading": heading,
        "objective": "State it.",
        "abstract": "Two sentences about the problem. A third names the stake.",
        "key_questions": ["what is the problem", "why existing approaches fail"],
        "claims_to_support": ["The problem is structural."],
        "required_evidence": ["a primary specification"],
        "word_target": 400,
        "figures": [],
        "depends_on": [],
    }
    section.update(over)
    return section


def sample_outline(**over):
    drafted = {
        "title": "On a topic",
        "audience": "engineers",
        "thesis": "A thesis.",
        "word_target_total": 400,
        "sections": [sample_section()],
    }
    drafted.update(over)
    return drafted


def test_the_outline_schema_is_closed_and_non_recursive():
    schema = load_agents.OUTLINE_SCHEMA["schema"]
    assert schema["additionalProperties"] is False
    dumped = json.dumps(schema)
    assert "$ref" not in dumped
    required = set(schema["required"])
    assert required == {"title", "audience", "thesis", "word_target_total", "sections"}
    section = schema["properties"]["sections"]["items"]
    assert section["additionalProperties"] is False
    assert "sections" not in section["properties"]
    assert "corpus_refs" in section["properties"]
    figure = section["properties"]["figures"]["items"]
    assert set(figure["properties"]["kind"]["enum"]) == {"diagram", "chart"}


def test_the_verdict_schema_is_closed():
    schema = load_agents.OUTLINE_VERDICT_SCHEMA["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "passed",
        "score",
        "blocking_issues",
        "actionable_changes",
    }


def test_a_valid_outline_has_no_errors():
    assert outlines.validate(sample_outline()) == []


def test_duplicate_ids_fail():
    drafted = sample_outline(
        word_target_total=800,
        sections=[
            sample_section("s1", word_target=400),
            sample_section("s1", heading="Other", word_target=400),
        ],
    )
    errors = outlines.validate(drafted)
    assert any("duplicated" in item for item in errors)


def test_depends_on_a_later_section_fails():
    drafted = sample_outline(
        word_target_total=800,
        sections=[
            sample_section("s1", depends_on=["s2"], word_target=400),
            sample_section("s2", heading="Later", word_target=400),
        ],
    )
    errors = outlines.validate(drafted)
    assert any("not an earlier section" in item for item in errors)


def test_depends_on_unknown_id_fails():
    drafted = sample_outline(sections=[sample_section(depends_on=["nope"])])
    errors = outlines.validate(drafted)
    assert any("unknown id" in item for item in errors)


def test_a_depends_on_cycle_fails():
    drafted = sample_outline(
        word_target_total=800,
        sections=[
            sample_section("a", word_target=400, depends_on=[]),
            sample_section("b", heading="B", word_target=400, depends_on=["a"]),
        ],
    )
    assert outlines.validate(drafted) == []
    cycle = outlines._cycle(["a", "b"], {"a": ["b"], "b": ["a"]})
    assert cycle is not None


def test_word_targets_off_by_more_than_ten_percent_fail():
    drafted = sample_outline(word_target_total=1000, sections=[sample_section(word_target=400)])
    errors = outlines.validate(drafted)
    assert any("ten percent" in item for item in errors)


def test_word_targets_within_ten_percent_pass():
    drafted = sample_outline(word_target_total=420, sections=[sample_section(word_target=400)])
    assert outlines.validate(drafted) == []


def test_a_chart_without_data_needed_fails():
    drafted = sample_outline(
        sections=[
            sample_section(
                figures=[
                    {
                        "name": "latency",
                        "kind": "chart",
                        "shows": "p95 by version",
                        "data_needed": "",
                    }
                ]
            )
        ]
    )
    errors = outlines.validate(drafted)
    assert any("data_needed" in item for item in errors)


def test_a_diagram_may_have_empty_data_needed():
    drafted = sample_outline(
        sections=[
            sample_section(
                figures=[
                    {
                        "name": "control-loop",
                        "kind": "diagram",
                        "shows": "the exits",
                        "data_needed": "",
                    }
                ]
            )
        ]
    )
    assert outlines.validate(drafted) == []


def test_a_section_with_fewer_than_two_key_questions_fails():
    drafted = sample_outline(sections=[sample_section(key_questions=["only one"])])
    errors = outlines.validate(drafted)
    assert any("at least two" in item for item in errors)


def test_sections_must_be_objects():
    drafted = sample_outline(sections=["just a heading"])
    errors = outlines.validate(drafted)
    assert any("SECTIONS MUST BE OBJECTS" in item for item in errors)


def make_run(work, turns, **kwargs):
    kwargs.setdefault("brain", None)
    kwargs.setdefault("log", lambda *a: None)
    return paper.Run(
        topic="a topic",
        work_dir=work,
        turns=turns,
        state=paper.State.load_or_new(work, "a topic"),
        **kwargs,
    )


def test_the_judge_loop_escalates_on_a_repeated_signature(work, turns):
    class Stubborn(turns):
        def judge_outline(self, drafted, note=""):
            self.asked.append(("judge_outline", note))
            return {
                "passed": False,
                "score": 0.4,
                "blocking_issues": [
                    {
                        "section": "s1",
                        "rule": "completeness",
                        "description": "no limitations section",
                    }
                ],
                "actionable_changes": ["add a limitations section"],
            }

    run = make_run(work, Stubborn())
    paper.prior_art(run)
    with pytest.raises(paper.RunFailed, match="not converging"):
        paper.do_outline(run)
    judged = [item for item in run.turns.asked if item[0] == "judge_outline"]
    assert len(judged) == 2


def test_passed_wins_over_a_low_score(work, turns):
    class Generous(turns):
        def judge_outline(self, drafted, note=""):
            return {
                "passed": True,
                "score": 0.2,
                "blocking_issues": [
                    {"section": "s1", "rule": "titles", "description": "heading is vague"}
                ],
                "actionable_changes": [],
            }

    run = make_run(work, Generous())
    paper.prior_art(run)
    paper.do_outline(run)
    stamp = json.loads((Path(work) / "outline.approved.json").read_text())
    assert stamp["approved_by"] == "judge"
    assert stamp["sha256"]


def test_approve_writes_markdown_and_stops(work, turns):
    run = make_run(work, turns(), require_approval=True)
    paper.prior_art(run)
    with pytest.raises(paper.AwaitingApproval) as raised:
        paper.do_outline(run)
    assert raised.value.path == Path(work) / "outline.md"
    assert (Path(work) / "outline.md").is_file()
    assert (Path(work) / "outline.json").is_file()
    assert (Path(work) / "outline-judged.json").is_file()
    assert (Path(work) / "outline-verdict.json").is_file()
    assert not (Path(work) / "outline.approved.json").exists()
    assert raised.value.exit_code == 3


def test_resume_after_approve_stamps_the_operator(work, turns):
    run = make_run(work, turns(), require_approval=True)
    paper.prior_art(run)
    with pytest.raises(paper.AwaitingApproval):
        paper.do_outline(run)
    continued = make_run(work, turns(), resume=True)
    meta = paper.do_outline(continued)
    stamp = json.loads((Path(work) / "outline.approved.json").read_text())
    assert stamp["approved_by"] == "operator"
    assert meta["approved_by"] == "operator"


def test_resume_rejudges_an_edited_outline(work, turns):
    class Counting(turns):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.judged = 0

        def judge_outline(self, drafted, note=""):
            self.judged += 1
            return super().judge_outline(drafted, note)

    first = Counting()
    run = make_run(work, first, require_approval=True)
    paper.prior_art(run)
    with pytest.raises(paper.AwaitingApproval):
        paper.do_outline(run)
    assert first.judged == 1

    drafted = json.loads((Path(work) / "outline.json").read_text())
    drafted["title"] = "Edited title"
    (Path(work) / "outline.json").write_text(json.dumps(drafted, indent=2) + "\n")

    second = Counting()
    continued = make_run(work, second, resume=True)
    paper.do_outline(continued)
    assert second.judged == 1
    stamp = json.loads((Path(work) / "outline.approved.json").read_text())
    assert stamp["outline"]["title"] == "Edited title"


def test_without_approve_the_judge_stamps(work, turns):
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.do_outline(run)
    stamp = json.loads((Path(work) / "outline.approved.json").read_text())
    assert stamp["approved_by"] == "judge"


def test_later_phases_read_only_the_approved_outline(work, turns):
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.do_outline(run)
    (Path(work) / "outline.json").write_text(json.dumps({"title": "stale"}) + "\n")
    loaded = paper.approved_outline(run)
    assert loaded["title"] == "On a topic"
    assert loaded["sections"][0]["id"] == "s1"


def test_outline_coverage_fails_when_a_key_question_is_missing():
    import checks  # noqa: PLC0415

    drafted = sample_outline()
    body = "# T\n\n## The problem\n\nA point [1].\n"
    gaps = checks.outline_coverage_gaps(body, drafted)
    assert any("never names" in item for item in gaps)
    score = checks.check(body, ["https://a"], headings=["The problem"], outline=drafted)
    assert "outline_coverage" in score.signature()


def test_outline_coverage_passes_when_questions_are_named():
    import checks  # noqa: PLC0415

    drafted = sample_outline()
    body = (
        "# T\n\n## The problem\n\n"
        "A point about what is the problem [1].\n\n"
        "Another point about why existing approaches fail [1].\n"
    )
    score = checks.check(body, ["https://a"], headings=["The problem"], outline=drafted)
    assert score.passed, score.report()


def test_a_chart_with_no_data_is_skipped(work, turns):
    class Charted(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            drafted = super().outline(topic, prior_art, budget, note, brief)
            drafted["sections"][0]["figures"] = [
                {
                    "name": "latency",
                    "kind": "chart",
                    "shows": "p95",
                    "data_needed": "latency table by version",
                },
                {
                    "name": "control-loop",
                    "kind": "diagram",
                    "shows": "the exits",
                    "data_needed": "",
                },
            ]
            return drafted

    notes = []
    run = make_run(work, Charted(), log=notes.append)
    paper.prior_art(run)
    paper.do_outline(run)
    paper.do_research(run)
    paper.verify(run)
    meta = paper.do_charts(run)
    assert meta["skipped"] == 1
    assert meta["rendered"] == 0
    assert any("no data" in str(item) for item in notes)
    assert not any("not rendered in this phase" in str(item) for item in notes)


def test_a_chart_with_data_is_rendered(work, turns):
    class Charted(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            drafted = super().outline(topic, prior_art, budget, note, brief)
            drafted["sections"][0]["figures"] = [
                {
                    "name": "three-exits",
                    "kind": "chart",
                    "shows": "the three exits",
                    "data_needed": "exit order",
                }
            ]
            return drafted

    notes = []
    run = make_run(work, Charted(), log=notes.append)
    paper.prior_art(run)
    paper.do_outline(run)
    data = run.file("data")
    data.mkdir(parents=True, exist_ok=True)
    (data / "three-exits.json").write_text(
        json.dumps(
            {
                "name": "three-exits",
                "columns": ["exit", "order"],
                "rows": [["done", 1], ["cost", 2], ["max turns", 3]],
                "source": "paper.py",
            }
        ),
        encoding="utf-8",
    )
    meta = paper.do_charts(run)
    assert meta["rendered"] == 1
    assert meta["skipped"] == 0
    png = run.file("charts") / "three-exits.png"
    sidecar = run.file("charts") / "three-exits.json"
    assert png.exists() and png.stat().st_size > 32
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert len(payload["values"]) == 3
    assert payload["values"][0]["y"] == 1


def test_an_invalid_outline_is_retried_with_the_validator_text(work, turns):
    class Flaky(turns):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.tries = 0

        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.tries += 1
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            if self.tries == 1:
                return {"title": "t", "sections": ["a string"]}
            return super().outline(topic, prior_art, budget, note, brief)

    run = make_run(work, Flaky())
    paper.prior_art(run)
    paper.do_outline(run)
    notes = [item[4] for item in run.turns.asked if item[0] == "outline"]
    assert notes[0] == ""
    assert "SECTIONS MUST BE OBJECTS" in notes[1]


def test_doctrine_is_off_by_default(work, turns):
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.do_outline(run)
    paper.do_research(run)
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    paper.assemble(run)
    score = paper.check(run)
    names = [row["name"] for row in score["checks"]]
    assert "doctrine" not in names
    assert "outline_coverage" in names


# -- corpus references ------------------------------------------------------
#
# The pack keys are `knowledge:claim.<subject>.<ULID>` and the model writes the
# bare ULID. An exact-match-only check rejected 21 references that were all real
# keys in suffix form, and the retry note never showed the required shape. That
# run spent $4.44 over five turns and escalated (#302).

KEY_A = "knowledge:claim.loop-engineering.01AAAAAAAAAAAAAAAAAAAAAAAA"
KEY_B = "knowledge:claim.loop-engineering.01BBBBBBBBBBBBBBBBBBBBBBBB"
KEY_C = "second:claim.other-subject.01AAAAAAAAAAAAAAAAAAAAAAAA"


def refs_outline(*refs):
    return sample_outline(sections=[sample_section(corpus_refs=list(refs))])


def test_a_bare_ulid_resolves_to_the_full_key():
    drafted = refs_outline("01AAAAAAAAAAAAAAAAAAAAAAAA")
    assert outlines.validate(drafted, corpus_keys=[KEY_A, KEY_B]) == []
    assert drafted["sections"][0]["corpus_refs"] == [KEY_A]


def test_a_claim_id_without_the_root_resolves_too():
    drafted = refs_outline("claim.loop-engineering.01BBBBBBBBBBBBBBBBBBBBBBBB")
    assert outlines.validate(drafted, corpus_keys=[KEY_A, KEY_B]) == []
    assert drafted["sections"][0]["corpus_refs"] == [KEY_B]


def test_a_full_key_is_left_alone():
    drafted = refs_outline(KEY_A)
    assert outlines.validate(drafted, corpus_keys=[KEY_A, KEY_B]) == []
    assert drafted["sections"][0]["corpus_refs"] == [KEY_A]


def test_an_ambiguous_suffix_is_rejected_and_names_every_candidate():
    """Two brains can carry the same claim id. Guessing picks the wrong one."""
    drafted = refs_outline("01AAAAAAAAAAAAAAAAAAAAAAAA")
    errors = outlines.validate(drafted, corpus_keys=[KEY_A, KEY_C])
    assert len(errors) == 1
    assert "matches 2 keys" in errors[0]
    assert KEY_A in errors[0]
    assert KEY_C in errors[0]
    assert drafted["sections"][0]["corpus_refs"] == ["01AAAAAAAAAAAAAAAAAAAAAAAA"]


def test_an_unknown_key_names_the_shape_and_the_closest_match():
    drafted = refs_outline("knowledge:claim.loop-engineering.01AAAAAAAAAAAAAAAAAAAAAAAB")
    errors = outlines.validate(drafted, corpus_keys=[KEY_A])
    assert len(errors) == 1
    assert "knowledge:claim.<subject>.<ULID>" in errors[0]
    assert KEY_A in errors[0]


def test_an_unknown_key_with_no_near_match_says_so():
    drafted = refs_outline("made up")
    errors = outlines.validate(drafted, corpus_keys=[KEY_A])
    assert "The pack has no key like it." in errors[0]


def test_a_partial_ulid_does_not_match_the_middle_of_a_key():
    """A suffix only counts on a segment boundary, or a short id collides."""
    assert outlines.resolve_ref("AAAAAAA", [KEY_A]) == (None, [])


def test_a_reference_that_is_not_a_string_is_reported():
    drafted = refs_outline(17)
    errors = outlines.validate(drafted, corpus_keys=[KEY_A])
    assert "unknown key 17" in errors[0]


def test_the_resume_path_validates_against_the_pack(tmp_path, monkeypatch):
    """Resume used to call validate with no keys, so it was silently weaker."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "corpus").mkdir()
    (work / "corpus" / "brain-pack.json").write_text(json.dumps({"keys": [KEY_A]}))
    drafted = refs_outline("01AAAAAAAAAAAAAAAAAAAAAAAA")
    (work / "outline.json").write_text(json.dumps(drafted))
    (work / "outline-judged.json").write_text(json.dumps({"passed": True}))

    run = paper.Run(topic="a topic", work_dir=work, turns=object(), state=paper.State())
    monkeypatch.setattr(paper, "_finish_outline", lambda run, drafted: {"ok": True})
    assert paper.do_outline(run) == {"ok": True}
    saved = json.loads((work / "outline.json").read_text())
    assert saved["sections"][0]["corpus_refs"] == [KEY_A]


def test_the_resume_path_rejects_an_unknown_key(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "corpus").mkdir()
    (work / "corpus" / "brain-pack.json").write_text(json.dumps({"keys": [KEY_A]}))
    (work / "outline.json").write_text(json.dumps(refs_outline("made up")))
    (work / "outline-judged.json").write_text(json.dumps({"passed": True}))

    run = paper.Run(topic="a topic", work_dir=work, turns=object(), state=paper.State())
    with pytest.raises(paper.RunFailed, match="unknown key"):
        paper.do_outline(run)


# -- the judge loop revises, it does not re-draft ---------------------------
#
# Two live runs escalated at the outline judge, six rounds, zero convergence.
# The failing rows changed between rounds rather than shrinking, because the
# outliner was handed the topic and a list of complaints about an outline it
# could not see, and answered by writing a different one (#327).


class NotingTurns:
    """A `Turns` that records the note each outline round receives."""

    def __init__(self, verdicts):
        self.notes: list[str] = []
        self.verdicts = list(verdicts)
        self.round = 0

    def outline(self, topic, prior_art, budget=None, note="", brief=""):
        self.notes.append(note)
        self.round += 1
        return sample_outline(
            sections=[sample_section(sid="s1", heading=f"Draft {self.round}")],
            word_target_total=400,
        )

    plan = outline

    def judge_outline(self, drafted, note=""):
        return self.verdicts.pop(0) if self.verdicts else {"passed": True, "score": 1.0}


def failing_verdict(rule):
    return {
        "passed": False,
        "score": 0.5,
        "blocking_issues": [{"section": "s1", "rule": rule, "description": f"{rule} is wrong"}],
        "actionable_changes": [f"s1.claims_to_support[0]: fix the {rule}"],
    }


def test_a_later_round_is_handed_the_outline_it_must_revise(work, monkeypatch):
    turns = NotingTurns([failing_verdict("corpus_fit"), {"passed": True, "score": 1.0}])
    run = paper.Run(topic="a topic", work_dir=work, turns=turns, state=paper.State())
    paper._judge_loop(run, turns.outline("a topic", ""))

    assert len(turns.notes) >= 2, "the judge must have forced a second round"
    revision = turns.notes[-1]
    assert "This is the outline you are revising" in revision
    assert '"heading": "Draft 1"' in revision, "the outliner never saw the outline it must fix"
    assert "fix the corpus_fit" in revision, "the actionable change must survive too"


def test_the_first_round_is_not_a_revision(work):
    """Nothing exists to revise yet. A note there would be a lie."""
    turns = NotingTurns([{"passed": True, "score": 1.0}])
    run = paper.Run(topic="a topic", work_dir=work, turns=turns, state=paper.State())
    paper._judge_loop(run, turns.outline("a topic", ""))
    assert "This is the outline you are revising" not in turns.notes[0]


def test_the_outline_judge_rounds_read_the_environment(monkeypatch):
    """Every other budget in this port is a flag. This one was a bare 3."""
    import importlib  # noqa: PLC0415

    monkeypatch.setenv("SOL3_OUTLINE_JUDGE_ROUNDS", "7")
    reloaded = importlib.reload(paper)
    try:
        assert reloaded.OUTLINE_JUDGE_ROUNDS == 7
    finally:
        monkeypatch.delenv("SOL3_OUTLINE_JUDGE_ROUNDS")
        importlib.reload(paper)


def test_the_default_round_count_is_unchanged():
    assert paper.OUTLINE_JUDGE_ROUNDS == 3


def test_the_loop_honours_a_raised_round_count(work, monkeypatch):
    """Each round must fail a different row, or the stall detector stops first.

    That guard is correct and separate: a repeated signature is not progress
    however large the budget is.
    """
    verdicts = [failing_verdict(rule) for rule in ("corpus_fit", "depth", "redundancy", "voice")]
    turns = NotingTurns([*verdicts, {"passed": True, "score": 1.0}])
    monkeypatch.setattr(paper, "OUTLINE_JUDGE_ROUNDS", 5)
    run = paper.Run(topic="a topic", work_dir=work, turns=turns, state=paper.State())
    paper._judge_loop(run, turns.outline("a topic", ""))
    assert turns.round >= 5, "a raised budget must buy more revision rounds"
