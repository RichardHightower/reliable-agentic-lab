"""The phases. Python owns the order, the budget, and the exits."""

from __future__ import annotations

import json
from pathlib import Path

import diagrams
import paper
import pytest
from turns import Escalate, TurnFailed


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


def test_section_instruction_uses_the_outline_word_target():
    with_target = paper._section_instruction({"word_target": 400})
    assert "400" in with_target
    assert "words of section body" in with_target
    assert "Unpack every bound claim" in paper._section_instruction({"heading": "The approach"})
    assert "fix the thing" in paper._section_instruction({"word_target": 400}, "fix the thing")


def test_strip_policy_leak_scrubs_a_host_and_a_retrieval_phrase():
    """#452 #465 #412: a judge's own note, or Python's `policy_leak` report,
    can name the offending host or phrase while explaining what to fix. The
    writer must not see either."""
    note = "policy_leak: search host or retrieval narration in: 'hosted on arxiv.org'"
    scrubbed = paper._strip_policy_leak(note, ("arxiv.org",))
    assert "arxiv.org" not in scrubbed
    assert paper._strip_policy_leak("no host here", ("arxiv.org",)) == "no host here"

    phrase_note = "Section s1 still names its preprint search."
    assert "preprint search" not in paper._strip_policy_leak(phrase_note, ())


@pytest.fixture
def no_renderer(monkeypatch):
    """A run must survive a machine with no diagram renderer."""
    monkeypatch.setattr(diagrams, "available", lambda: False)


# -- the phases -------------------------------------------------------------


def test_prior_art_is_skipped_when_the_brain_is_absent(work, turns):
    run = make_run(work, turns())
    meta = paper.prior_art(run)
    assert meta["hits"] == 0
    assert meta["corpus_thin"] is True
    assert "No second brain" in (Path(work) / "corpus" / "brain-pack.md").read_text()


def test_prior_art_reads_the_brain_when_it_is_there(work, turns):
    brain = Path(__file__).resolve().parent / "fixtures" / "brain"
    run = make_run(work, turns(), brain=brain, brains=[brain])
    meta = paper.prior_art(run)
    assert meta["hits"] >= 1
    text = (Path(work) / "corpus" / "brain-pack.md").read_text()
    assert "Not verified" in text, "prior art is context, never evidence"


def test_a_plan_with_no_questions_stops_the_run(work, turns):
    class Empty(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            return {
                "title": "t",
                "audience": "a",
                "thesis": "t",
                "word_target_total": 400,
                "sections": [],
            }

    run = make_run(work, Empty())
    paper.prior_art(run)
    with pytest.raises(paper.RunFailed, match="sections must be a non-empty array"):
        paper.plan(run)


def test_research_with_no_claims_stops_the_run(work, turns):
    run = make_run(work, turns(claims=[]))
    paper.prior_art(run)
    paper.plan(run)
    with pytest.raises(paper.RunFailed, match="nothing to write a paper from"):
        paper.do_research(run)


def test_a_claim_carries_the_section_it_serves(work, turns):
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.plan(run)
    paper.do_research(run)
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    assert claims[0]["section"] == "s1"
    assert claims[0]["status"] == "unverified", "a claim starts unverified"


# -- verification -----------------------------------------------------------


def prepared_plan(work, turns_obj, **kwargs):
    """A run with prior art and a plan, ready for the research phase."""
    run = make_run(work, turns_obj, **kwargs)
    paper.prior_art(run)
    paper.plan(run)
    return run


def prepared(work, turns_obj):
    run = make_run(work, turns_obj)
    paper.prior_art(run)
    paper.plan(run)
    paper.do_research(run)
    return run


def test_the_verifier_is_never_handed_the_researchers_source(work, turns):
    """Two models reading one page agree by construction."""
    recorder = turns()
    run = prepared(work, recorder)
    paper.verify(run)
    asked = [args for args in recorder.asked if args[0] == "verify"]
    assert asked, "the verifier never ran"
    for _, claim in asked:
        assert "https://example.invalid/doc" not in claim
        assert claim == "A thing is true."


def test_support_from_both_sides_is_verified(work, turns):
    run = prepared(work, turns(verdict="supports"))
    assert paper.verify(run) == {"verified": 1}


def test_a_contradiction_with_quotes_on_both_sides_is_disputed(work, turns):
    """Both hold a source, so the paper names the disagreement."""
    run = prepared(work, turns(verdict="contradicts"))
    assert paper.verify(run) == {"disputed": 1}


def test_a_contradiction_with_no_researcher_quote_drops_the_claim(work, turns):
    claims = [
        {"text": "A thing is true.", "source_url": "https://example.invalid/doc", "quote": ""}
    ]
    run = prepared(work, turns(verdict="contradicts", claims=claims))
    assert paper.verify(run) == {"contradicted": 1}


def test_an_unclear_verdict_is_unverified(work, turns):
    run = prepared(work, turns(verdict="unclear"))
    assert paper.verify(run) == {"unverified": 1}


def test_a_verifier_that_fails_leaves_the_claim_unverified(work, turns):
    """Fail open, never fail silent. A weaker sentence, not a wrong one."""

    class Broken(turns):
        def verify(self, claim):
            raise TurnFailed("the verifier is down")

    run = prepared(work, Broken())
    assert paper.verify(run) == {"unverified": 1}
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    assert "unavailable" in claims[0]["verifier_excerpt"]


# -- attribution moved to the live path: see test_sections.py. `paper.verify`
# is dead code no `LINEAR` or `CYCLE` stage calls; #471's checks live in
# `sections.run_section`, where a real run actually records claims.


def test_do_sections_carries_the_study_object_into_claims_json(work, turns, monkeypatch):
    """The SDK schema equivalent of #471's ledger round trip: `study` is
    unused until #478, and only has to survive to `claims.json`."""
    import sections

    approved = {"title": "T", "sections": [{"id": "s1", "heading": "One"}]}
    monkeypatch.setattr(paper, "approved_outline", lambda run: approved)
    monkeypatch.setattr(sections, "run_section", lambda run, section: {"section": section["id"]})

    knowledge = Path(work) / "knowledge" / "s1"
    knowledge.mkdir(parents=True)
    (knowledge / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "s1-f1",
                        "claim": "The trial enrolled 120 adults.",
                        "quote": "",
                        "answers_question": "q",
                        "study": {"design": "RCT", "n": 120},
                        "source": {"kind": "web", "url_or_path": "https://a.invalid"},
                    }
                ],
                "coverage_gaps": [],
            }
        ),
        encoding="utf-8",
    )

    run = paper.Run(
        topic="t",
        work_dir=work,
        turns=turns(root=work),
        state=paper.State.load_or_new(work, "t"),
    )
    paper.do_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    assert claims[0]["study"] == {"design": "RCT", "n": 120}


def test_a_contradicted_claim_never_reaches_the_writer(work, turns, no_renderer):
    claims = [{"text": "A thing is true.", "source_url": "https://e.invalid/d", "quote": ""}]
    run = prepared(work, turns(verdict="contradicts", claims=claims))
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    paper.assemble(run)
    assert "A thing is true." not in (Path(work) / "paper.md").read_text()


def test_assemble_rewrites_a_finding_id_marker_to_its_reference_number(
    work, turns, no_renderer
):
    """The writer cites the id it holds. The reference list is numbered."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    cited = next(c for c in claims if c.get("source_url"))
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    section.write_text(
        f"A thing is true [{cited['id']}].\n", encoding="utf-8"
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert f"[{cited['id']}]" not in body, "the finding id survived assembly"
    assert "A thing is true [1]." in body


def test_assemble_keeps_a_marker_it_cannot_resolve(work, turns, no_renderer):
    """Deleting an evidence marker to pass a check loses the trace."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    section.write_text("A thing is true [fm-q9-99].\n", encoding="utf-8")
    paper.assemble(run)
    assert "[fm-q9-99]" in (Path(work) / "paper.md").read_text()


def test_the_paper_gate_honours_the_hosts_the_librarian_admitted(work, turns, no_renderer):
    """`arxiv.org` was admitted for the run and the paper gate rejected it.

    The gate read the seed list, which the librarian's admissions never reach.
    The first paper this port assembled cited the MAST paper through arxiv and
    failed `hosts` for it. A `corpus:` reference has no host and is exempt.
    """
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    paper.assemble(run)
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    for claim in claims:
        claim["source_url"] = "https://arxiv.org/abs/2503.13657"
    (Path(work) / "claims.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")
    run.enforce_research_policy = True
    run.allowed_domains = ("arxiv.org",)
    score = paper.check(run)
    hosts = next(row for row in score["checks"] if row["name"] == "hosts")
    assert hosts["passed"], hosts


def test_assembly_writes_the_section_heading_the_writer_left_out(work, turns, no_renderer):
    """Two of three writers headed their section with its key questions and
    never wrote the outline heading, so `outline_coverage` could not find the
    section. Assembly owns the heading now. One the writer did write is kept,
    not doubled.
    """
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    outline = json.loads((Path(work) / "outline.approved.json").read_text())
    outline = outline.get("outline", outline)
    heading = outline["sections"][0]["heading"]
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    section.write_text("### A key question?\n\nBody text [1].\n", encoding="utf-8")
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert body.count(f"## {heading}") == 1, body
    section.write_text(f"## {heading}\n\nBody text [1].\n", encoding="utf-8")
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert body.count(f"## {heading}") == 1, "the heading was doubled"
    # A writer that wrote it at the wrong level. The paper had two H1s and
    # `outline_coverage` could not find the section under `## `.
    section.write_text(f"# {heading}\n\nBody text [1].\n", encoding="utf-8")
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert body.count(f"## {heading}") == 1, body
    assert f"\n# {heading}" not in body, "the writer's H1 survived"
    # A writer that headed its sub-sections `## ` put them at the section's
    # level. Every row that reads by level then saw the section end at its
    # first sub-heading. Assembly demotes them.
    section.write_text(f"## {heading}\n\n## A sub-point\n\nBody text [1].\n", encoding="utf-8")
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert "\n### A sub-point\n" in body, body
    assert "\n## A sub-point\n" not in body


def test_a_term_marker_is_harvested_and_stripped(work, turns, no_renderer):
    """The writer's `TERM` marker never reaches the reader, and its term
    reaches the glossary assembly writes."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    text = section.read_text(encoding="utf-8")
    section.write_text(
        text + "\n<!-- TERM: orchestrator: the process that sequences roles -->\n",
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert "TERM" not in body
    assert "**orchestrator.** the process that sequences roles" in body


def test_assemble_writes_a_glossary_before_references(work, turns, no_renderer):
    """Heading order: the last prose section, then Glossary, then References.
    The writer is denied both trailing headings."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    outline = json.loads((Path(work) / "outline.approved.json").read_text())
    outline = outline.get("outline", outline)
    heading = outline["sections"][0]["heading"]
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    text = section.read_text(encoding="utf-8")
    section.write_text(
        text + "\n<!-- TERM: orchestrator: the process that sequences roles -->\n",
        encoding="utf-8",
    )
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    section_at = body.index(f"## {heading}")
    glossary_at = body.index("## Glossary")
    references_at = body.index("## References")
    assert section_at < glossary_at < references_at, body


def test_no_glossary_heading_when_no_term_was_captured(work, turns, no_renderer):
    """No marker, no section. A Glossary with zero entries is not written."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert "## Glossary" not in body


def test_a_failed_rewrite_keeps_the_stamped_section_it_was_replacing(work, turns, no_renderer):
    """`write_sections` unlinked the draft and called the writer with no copy kept.

    A kill during the rewrite cost three stamped sections twice in one evening.
    #353 closed this in `run_section`. This is the other path.
    """
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    section = sorted((Path(work) / "sections").glob("*.md"))[0]
    section.write_text("The stamped draft [1].\n", encoding="utf-8")

    class Down(type(run.turns)):
        def write(self, section, claims, figures, notes, path=""):
            raise TurnFailed("the writer is down")

    run.turns = Down(root=work)
    paper.write_sections(run)
    assert section.read_text() == "The stamped draft [1].\n", "the draft was lost"

    class Ceiling(type(run.turns)):
        def write(self, section, claims, figures, notes, path=""):
            raise Escalate("the runtime hit its ceiling")

    run.turns = Ceiling(root=work)
    with pytest.raises(Escalate):
        paper.write_sections(run)
    assert section.read_text() == "The stamped draft [1].\n", "the draft was lost on Escalate"


# -- #476: the sections_sha guard, and the claims that reach the diagrammer --


def _diagram_ready(work, run):
    """An outline with one figure, one section, one ledger claim, and the
    section's body on disk: enough for `paper.diagram` to commission from,
    without paying for research, write, or a real render."""
    outline = {
        "title": "T",
        "sections": [
            {
                "id": "s1",
                "heading": "One",
                "figures": [{"kind": "diagram", "name": "f1", "shows": "the loop"}],
            }
        ],
    }
    run.write_json(
        "paper_ledger.json",
        {
            "entries": [
                {
                    "section_id": "s1",
                    "claims": [
                        {"claim": "Creatine increased fat-free mass.", "ref": "1", "confidence": 0.5}
                    ],
                }
            ]
        },
    )
    sections_dir = Path(work) / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    (sections_dir / "s1.md").write_text("Body text.\n", encoding="utf-8")
    return outline


def test_the_diagrammer_receives_the_bound_claims_of_its_section(work, turns, monkeypatch):
    run = make_run(work, turns())
    outline = _diagram_ready(work, run)
    monkeypatch.setattr(paper, "approved_outline", lambda r: outline)

    calls = []

    def fake_draw(turns_obj, *, name, concept, section, topic, out_dir, theme, claims=None):
        calls.append(list(claims or []))
        return diagrams.Figure(name=name, section=section, path=f"diagrams/{name}_imagen.png")

    monkeypatch.setattr(paper.diagrams, "draw", fake_draw)
    paper.diagram(run)
    assert calls == [["Creatine increased fat-free mass."]]


def test_a_second_write_attempt_does_not_recommission_a_figure(work, turns, monkeypatch):
    """#476's `sections_sha` guard: one diagrammer turn across two calls to
    `paper.diagram`, when the section files have not changed between them."""
    run = make_run(work, turns())
    outline = _diagram_ready(work, run)
    monkeypatch.setattr(paper, "approved_outline", lambda r: outline)

    calls = []

    def fake_draw(turns_obj, *, name, concept, section, topic, out_dir, theme, claims=None):
        calls.append(name)
        return diagrams.Figure(name=name, section=section, path=f"diagrams/{name}_imagen.png")

    monkeypatch.setattr(paper.diagrams, "draw", fake_draw)
    paper.diagram(run)
    assert len(calls) == 1
    paper.diagram(run)
    assert len(calls) == 1, "an unchanged sections_sha must not recommission a figure"


def test_a_changed_section_recommissions_its_figure(work, turns, monkeypatch):
    """The `sections_sha` guard is not a permanent skip."""
    run = make_run(work, turns())
    outline = _diagram_ready(work, run)
    monkeypatch.setattr(paper, "approved_outline", lambda r: outline)

    calls = []

    def fake_draw(turns_obj, *, name, concept, section, topic, out_dir, theme, claims=None):
        calls.append(name)
        return diagrams.Figure(name=name, section=section, path=f"diagrams/{name}_imagen.png")

    monkeypatch.setattr(paper.diagrams, "draw", fake_draw)
    paper.diagram(run)
    assert len(calls) == 1

    (Path(work) / "sections" / "s1.md").write_text(
        "Body text, rewritten.\n", encoding="utf-8"
    )
    paper.diagram(run)
    assert len(calls) == 2, "a changed section must recommission its figure"


# -- the whole run ----------------------------------------------------------


def test_a_full_run_passes_and_writes_a_paper(work, turns, no_renderer):
    run = make_run(work, turns())
    result = paper.run_paper(run)
    assert result["gate"] == "pass", result["report"]
    body = (Path(work) / "paper.md").read_text()
    assert "## References" in body
    assert "https://example.invalid/doc" in body
    assert result["knowledge"]["claims"] == 1


def test_a_fixture_paper_clears_the_word_floor(work, no_renderer):
    """The offline twin unpacks claims so task demo is a paper, not a brief."""
    import checks  # noqa: PLC0415
    import research  # noqa: PLC0415
    import turns as t  # noqa: PLC0415

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "research.json"
    run = paper.Run(
        topic="loop engineering exit criteria",
        work_dir=work,
        turns=t.OfflineTurns(backend=research.FixtureBackend(fixture)),
        state=paper.State.load_or_new(work, "loop engineering exit criteria"),
        brain=None,
        log=lambda *a: None,
    )
    paper.run_paper(run)
    body = (Path(work) / "paper.md").read_text()
    assert checks.word_count(body) >= checks.MIN_WORDS
    score = checks.check(
        body,
        ["https://example.invalid/doc"],
        min_words=checks.MIN_WORDS,
        min_section_words=checks.MIN_SECTION_WORDS,
    )
    assert "length" not in score.signature(), score.report()
    assert "has_body" not in score.signature(), score.report()


def test_the_knowledge_bundle_survives_an_escalation(work, turns, no_renderer):
    """A run that escalated still found sources. Throwing them away is waste."""
    run = make_run(work, turns(done=False))
    result = paper.run_paper(run)
    assert result["gate"] == "escalate"
    assert (Path(work) / "knowledge" / "research" / "claims").exists()
    assert result["knowledge"]["claims"] == 1


def test_a_stall_escalates_before_the_iteration_budget(work, turns, no_renderer):
    """Watching a loop fail identically twice more buys a bill, not a paper."""
    run = make_run(work, turns(done=False), max_iterations=9)
    result = paper.run_paper(run)
    assert result["gate"] == "escalate"
    assert "not converging" in result["reason"]
    assert run.state.iteration == 2, "it should stop on the second identical failure"


def test_the_judge_can_refuse_a_green_rubric(work, turns, no_renderer):
    """`done` false on passing checks is not agreement, and it is not a pass."""
    run = make_run(work, turns(done=False))
    result = paper.run_paper(run)
    assert json.loads((Path(work) / "check.json").read_text())["passed"]
    assert result["gate"] == "escalate"


def test_the_retry_hands_the_writer_only_the_current_issues(work, turns, no_renderer):
    """Every complaint it ever received produces over-correction, not progress."""
    recorder = turns(done=False)
    run = make_run(work, recorder, max_iterations=2)

    class Noisy(type(recorder)):
        def review(self, paper_body, report):
            self.asked.append(("review", report))
            return {
                "done": False,
                "summary": "",
                "issues": [{"severity": "major", "section": "s1", "description": "fix the thing"}],
            }

    run.turns = Noisy(done=False)
    paper.run_paper(run)
    notes = [args[2] for args in run.turns.asked if args[0] == "write"]
    assert "fix the thing" not in notes[0], "the first attempt has no judge issues yet"
    assert "words of section body" in notes[0]
    assert "fix the thing" in notes[1]
    assert "FINAL ATTEMPT" in notes[1], "the last attempt narrows the ask"


def test_the_retry_note_names_no_allowlist_host(work, turns, no_renderer):
    """A judge's own note can quote a `policy_leak` failure's host back at
    the writer while explaining what to fix. #452 #465 #412: the retry note
    the next write attempt receives must not repeat it."""
    recorder = turns(done=False)
    run = make_run(work, recorder, max_iterations=2)

    class Noisy(type(recorder)):
        def review(self, paper_body, report):
            self.asked.append(("review", report))
            return {
                "done": False,
                "summary": "",
                "issues": [
                    {
                        "severity": "major",
                        "section": "s1",
                        "description": "remove the mention of docs.langchain.com",
                    }
                ],
            }

    run.turns = Noisy(done=False)
    paper.run_paper(run)
    notes = [args[2] for args in run.turns.asked if args[0] == "write"]
    assert "docs.langchain.com" not in notes[1], notes[1]


# -- resume -----------------------------------------------------------------


def test_a_finished_phase_is_not_rerun(work, turns, no_renderer):
    recorder = turns()
    paper.run_paper(make_run(work, recorder))
    first = len([a for a in recorder.asked if a[0] == "research"])

    again = turns()
    paper.run_paper(make_run(work, again))
    assert [a for a in again.asked if a[0] == "research"] == []
    assert first >= 1


def test_deleting_one_output_reruns_only_that_phase(work, turns, no_renderer):
    paper.run_paper(make_run(work, turns()))
    (Path(work) / "claims.json").unlink()
    findings = Path(work) / "knowledge" / "s1" / "findings.json"
    if findings.exists():
        findings.unlink()
    section = Path(work) / "sections" / "s1.md"
    if section.exists():
        section.unlink()

    again = turns()
    paper.run_paper(make_run(work, again))
    kinds = {a[0] for a in again.asked}
    assert "research" in kinds
    assert "outline" not in kinds


def test_the_state_file_records_every_phase(work, turns, no_renderer):
    paper.run_paper(make_run(work, turns()))
    state = json.loads(paper.State.path(work).read_text())
    assert state["phases"]["sections"]["status"] == "complete"
    assert state["phases"]["knowledge"]["valid"] is True
    assert state["slug"] == "a-topic"


def test_every_turn_flushes_the_state_and_appends_a_turn_row(work, turns):
    """A ten-minute phase looked dead because state only landed on a boundary."""
    run = make_run(work, turns())
    run.state.phase = "outline"
    run.spend(0.42, role="outliner", elapsed_s=612.0, events=9)

    state = json.loads(paper.State.path(work).read_text())
    assert state["phase"] == "outline"
    assert state["role"] == "outliner"
    assert state["turns"] == 1
    assert state["last_turn"]["elapsed_s"] == 612.0

    rows = [
        json.loads(line)
        for line in (Path(work) / ".harness" / "turns.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["role"] == "outliner"
    assert rows[0]["phase"] == "outline"
    assert rows[0]["usd"] == 0.42
    assert rows[0]["total_usd"] == 0.42


def test_a_turn_with_no_cost_logs_null_not_zero(work, turns):
    """A zero reads as a free turn and hides a missing cost path (#303)."""
    run = make_run(work, turns())
    run.spend(None, role="outliner")
    row = json.loads((Path(work) / ".harness" / "turns.jsonl").read_text().splitlines()[0])
    assert row["usd"] is None
    assert run.state.total_usd == 0.0


def test_the_turn_log_is_append_only(work, turns):
    run = make_run(work, turns())
    for _ in range(3):
        run.spend(0.1, role="researcher")
    rows = (Path(work) / ".harness" / "turns.jsonl").read_text().splitlines()
    assert [json.loads(row)["turn"] for row in rows] == [1, 2, 3]


def test_a_run_killed_mid_phase_names_the_phase_it_died_in(work, turns, no_renderer):
    """The report must not name the last phase that finished cleanly."""

    def die(run):
        raise RuntimeError("killed")

    original = [entry for entry in paper.LINEAR]
    patched = [
        (number, name, output, die if name == "outline" else phase)
        for number, name, output, phase in original
    ]
    paper.LINEAR[:] = patched
    try:
        with pytest.raises(RuntimeError, match="killed"):
            paper.run_paper(make_run(work, turns()))
    finally:
        paper.LINEAR[:] = original

    state = json.loads(paper.State.path(work).read_text())
    assert state["phase"] == "outline"
    assert state["phases"]["outline"]["status"] == "failed"
    assert state["query_timeout_s"] >= 900


def test_the_state_write_is_atomic(work, turns):
    """A kill between the open and the write must leave the previous state."""
    state = paper.State.load_or_new(work, "a topic")
    state.save(work)
    first = paper.State.path(work).read_text()
    state.total_usd = 9.0
    state.save(work)
    assert paper.State.path(work).read_text() != first
    assert not list(Path(work).joinpath(".harness").glob("*.tmp.*"))


# -- publishing -------------------------------------------------------------


def test_publishing_is_off_by_default(work, turns, no_renderer, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("it published without being asked")

    monkeypatch.setattr(paper.publisher, "publish", boom)
    assert paper.run_paper(make_run(work, turns()))["gist"] is None


def test_a_failed_paper_is_never_published(work, turns, no_renderer, monkeypatch):
    """The one bug here you cannot take back."""

    def boom(*args, **kwargs):
        raise AssertionError("it published a paper that did not pass")

    monkeypatch.setattr(paper.publisher, "publish", boom)
    run = make_run(work, turns(done=False), should_publish=True)
    result = paper.run_paper(run)
    assert result["gate"] == "escalate"
    assert result["gist"] is None
    assert run.state.phases["publish"]["status"] == "skipped"


def test_a_passing_paper_is_published_when_asked(work, turns, no_renderer, monkeypatch):
    monkeypatch.setattr(
        paper.publisher, "publish", lambda *a, **k: {"url": "https://gist.github.com/u/abc"}
    )
    result = paper.run_paper(make_run(work, turns(), should_publish=True))
    assert result["gist"]["url"].endswith("abc")


# -- assembly ---------------------------------------------------------------


def test_references_are_numbered_in_reading_order(work, turns):
    planned = {
        "sections": [
            {"id": "a", "heading": "A", "goal": "g"},
            {"id": "b", "heading": "B", "goal": "g"},
        ]
    }
    claims = [
        {"id": "2", "section": "b", "source_url": "https://second", "status": "verified"},
        {"id": "1", "section": "a", "source_url": "https://first", "status": "verified"},
    ]
    usable, references = paper._numbered(claims, planned)
    assert [r["url"] for r in references] == ["https://first", "https://second"]
    assert {c["id"]: c["number"] for c in usable} == {"1": 1, "2": 2}


def test_two_claims_from_one_page_share_a_number(work):
    planned = {"sections": [{"id": "a", "heading": "A", "goal": "g"}]}
    claims = [
        {"id": "1", "section": "a", "source_url": "https://one", "status": "verified"},
        {"id": "2", "section": "a", "source_url": "https://one", "status": "verified"},
    ]
    usable, references = paper._numbered(claims, planned)
    assert len(references) == 1
    assert {c["number"] for c in usable} == {1}


# -- budget ceilings --------------------------------------------------------


def test_the_plan_is_held_to_a_question_budget(work, turns):
    """Every question is a research turn and a verify turn. An uncapped plan is
    an uncapped bill, and the planner has no idea what a turn costs."""

    class Ambitious(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            drafted = super().outline(topic, prior_art, budget, note, brief)
            return drafted

    run = make_run(work, Ambitious(), max_questions=3, max_diagrams=2)
    paper.prior_art(run)
    paper.plan(run)
    asked = next(args for args in run.turns.asked if args[0] == "outline")
    assert asked[3] == {"questions": 3, "diagrams": 2, "claims": 40, "words": 2000}


def test_truncation_never_leaves_a_heading_with_nothing_under_it(work, turns):
    """The outliner is told the budget so Python does not silently drop sections."""
    run = make_run(work, turns(), max_questions=2)
    paper.prior_art(run)
    paper.plan(run)
    approved = paper.approved_outline(run)
    assert approved["sections"]
    assert all(len(s["key_questions"]) >= 2 for s in approved["sections"])


def test_research_stops_when_the_money_runs_out(work, turns):
    """The gate runs once per attempt. This loop can spend the budget several
    times over before the gate ever sees it."""

    class Costly(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            drafted = super().outline(topic, prior_art, budget, note, brief)
            drafted["sections"][0]["key_questions"] = [f"q{i}" for i in range(5)]
            return drafted

    run = make_run(work, Costly(), max_usd=1.0)
    paper.prior_art(run)
    paper.plan(run)
    run.state.total_usd = 1.5
    with pytest.raises(paper.RunFailed, match="cost budget spent"):
        paper.do_research(run)
    assert json.loads((Path(work) / "sources.json").read_text())["stopped"] == "cost budget spent"
    assert [a for a in run.turns.asked if a[0] == "research"] == [], "it spent nothing more"


def test_verification_that_runs_out_of_money_leaves_claims_unverified(work, turns):
    """Marking the rest verified because the money ran out is the lie."""
    run = prepared(work, turns())
    run.max_usd = 1.0
    run.state.total_usd = 1.5
    counts = paper.verify(run)
    assert counts["unverified"] == 1
    assert "cost budget spent" in counts["stopped"]
    claim = json.loads((Path(work) / "claims.json").read_text())["claims"][0]
    assert "not checked" in claim["verifier_excerpt"]


# -- the writer's own write -------------------------------------------------


def test_the_writer_is_told_where_to_write(work, turns, no_renderer):
    recorder = turns()
    run = make_run(work, recorder)
    paper.run_paper(run)
    paths = [args[3] for args in recorder.asked if args[0] == "write"]
    assert paths == ["sections/s1.md"]


def test_the_file_the_writer_wrote_is_preferred(work, turns, no_renderer):
    """A long section that round-trips through a message is the one that comes
    back truncated."""
    recorder = turns(root=work)
    run = make_run(work, recorder)
    meta_before = Path(work) / "sections" / "s1.md"
    paper.run_paper(run)
    assert meta_before.exists()
    assert run.state.phases["write"]["status"] == "complete"
    assert "The problem" in meta_before.read_text()


def test_a_writer_that_only_answered_still_produces_a_section(work, turns, no_renderer):
    """The fallback is what keeps one forgetful turn from emptying the paper."""
    run = make_run(work, turns(root=None))
    paper.run_paper(run)
    assert (Path(work) / "sections" / "s1.md").read_text().strip()
    assert run.state.phases["write"]["status"] == "complete"


def test_the_abstract_turn_runs_after_the_last_section(work, turns, no_renderer):
    """P7, #472. The abstract is written from the assembled body, so its
    turn cannot run until every section is stamped."""
    recorder = turns()
    run = make_run(work, recorder)
    paper.run_paper(run)
    calls = [args[0] for args in recorder.asked if args[0] in ("write", "write_abstract")]
    assert calls, "the writer never ran"
    assert calls[-1] == "write_abstract"
    assert calls.count("write") >= 1


def test_the_abstract_turn_is_not_repeated_when_the_body_is_unchanged(work, turns, no_renderer):
    """One extra writer turn per run, not one per retry attempt."""
    recorder = turns()
    run = make_run(work, recorder)
    paper.run_paper(run)
    abstract_calls = [args for args in recorder.asked if args[0] == "write_abstract"]
    assert len(abstract_calls) == 1
    paper.write_abstract(run)
    assert [args for args in recorder.asked if args[0] == "write_abstract"] == abstract_calls, (
        "an unchanged body spent a second turn"
    )


def test_assemble_prefers_the_written_abstract_over_the_thesis_line(work, turns, no_renderer):
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    paper.write_abstract(run)
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    assert "A recorded abstract." in body
    assert "An abstract." not in body


def test_the_abstract_gets_the_same_cleanup_pass_as_a_section(work, turns, no_renderer):
    """A finding-id marker in the abstract resolves to its reference number,
    the same way `_resolve_markers` already treats a section body: the
    abstract runs through the same cleanup, not a verbatim insert."""
    run = prepared(work, turns())
    paper.verify(run)
    paper.diagram(run)
    paper.write_sections(run)
    claims = json.loads((Path(work) / "claims.json").read_text())["claims"]
    cited = next(c for c in claims if c.get("source_url"))
    run.turns.write_abstract = lambda body, ledger=None: f"The result holds [{cited['id']}]."
    paper.write_abstract(run)
    paper.assemble(run)
    body = (Path(work) / "paper.md").read_text()
    abstract = body.split("## Abstract", 1)[1].split("##", 1)[0]
    assert f"[{cited['id']}]" not in abstract, "the finding id survived assembly"
    assert "[1]" in abstract


def test_a_stale_section_from_a_previous_plan_is_removed(work, turns, no_renderer):
    run = make_run(work, turns())
    paper.prior_art(run)
    paper.plan(run)
    paper.do_research(run)
    paper.verify(run)
    paper.diagram(run)
    stale = Path(work) / "sections" / "gone.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("a heading nobody plans any more")
    paper.write_sections(run)
    paper.assemble(run)
    assert "nobody plans any more" not in (Path(work) / "paper.md").read_text()


def test_the_planner_is_told_what_it_can_afford(work, turns, no_renderer):
    """A planner asked without a budget returns a plan the run cannot pay for,
    and truncation turns it into two sections and five orphaned headings."""
    recorder = turns()
    run = make_run(work, recorder, max_questions=5, max_diagrams=2)
    paper.prior_art(run)
    paper.plan(run)
    budget = next(args[3] for args in recorder.asked if args[0] == "outline")
    assert budget == {"questions": 5, "diagrams": 2, "claims": 40, "words": 2000}


# -- the verification budget ------------------------------------------------


def test_every_claim_is_verified_when_they_fit():
    claims = [{"id": str(i), "text": "plain"} for i in range(5)]
    assert paper.to_verify(claims, 24) == claims


def test_a_claim_with_a_number_gets_the_budget_first():
    """Four good questions produced a hundred and eleven claims on one live run.
    A claim with a version or a date is the one that goes stale."""
    claims = [
        {"id": "a", "text": "the parser is reentrant"},
        {"id": "b", "text": "the feature landed in version 2.0"},
        {"id": "c", "text": "the default is unbounded"},
        {"id": "d", "text": "the spec was ratified in 2024"},
    ]
    assert [c["id"] for c in paper.to_verify(claims, 2)] == ["b", "d"]


def test_the_sampler_keeps_document_order():
    """An early section must not be starved by a late one full of versions."""
    claims = [
        {"id": "a", "text": "version 1"},
        {"id": "b", "text": "plain"},
        {"id": "c", "text": "version 2"},
    ]
    assert [c["id"] for c in paper.to_verify(claims, 3)] == ["a", "b", "c"]
    assert [c["id"] for c in paper.to_verify(claims, 2)] == ["a", "c"]


def test_a_claim_past_the_budget_is_unverified_not_dropped(work, turns):
    """The writer softens it and the bundle records that nobody checked it."""
    many = [
        {"text": f"claim {i} with no digits", "source_url": "https://e.invalid/d", "quote": "q"}
        for i in range(4)
    ]
    run = prepared(work, turns(claims=many))
    run.max_claims = 2
    counts = paper.verify(run)
    assert counts["past_budget"] == 2
    assert counts["verified"] == 2
    checked = [a for a in run.turns.asked if a[0] == "verify"]
    assert len(checked) == 2, "it must not pay for the claims it skipped"
    unchecked = [
        c
        for c in json.loads((Path(work) / "claims.json").read_text())["claims"]
        if "past the" in c["verifier_excerpt"]
    ]
    assert len(unchecked) == 2


def test_a_run_that_spent_its_budget_researching_escalates_before_writing(work, turns, no_renderer):
    """Entering the cycle with no money spends three attempts producing an empty
    paper and then reports a stall, for a run that never started."""
    run = make_run(work, turns(), max_usd=1.0)
    paper.prior_art(run)
    paper.plan(run)
    paper.do_research(run)
    paper.verify(run)
    paper.diagram(run)
    run.state.total_usd = 2.0
    with pytest.raises(paper.RunFailed, match="No budget was left to write"):
        paper.run_paper(run)
    assert run.state.phases["write"]["status"] == "escalated"
    assert run.state.iteration == 0, "it must not burn an attempt"


# -- assembly hygiene -------------------------------------------------------


def test_a_reference_list_a_section_wrote_for_itself_is_removed(work, turns, no_renderer):
    """Two "References" headings in one paper is the visible symptom. The cause
    is a writer doing the harness's job, and an instruction is not a mechanism."""

    class Overreaching(turns):
        def write(self, section, claims, figures, notes, path=""):
            self.asked.append(("write", section["id"], notes, path))
            return "## The problem\n\nA point [1].\n\nThis section answers: what is a topic [1].\n\nThis section answers: why does a topic fail [1].\n\n## References\n\n1. https://stray"

    run = make_run(work, Overreaching())
    paper.run_paper(run)
    body = (Path(work) / "paper.md").read_text()
    assert body.count("## References") == 1
    assert "https://stray" not in body


def test_a_needs_source_flag_leaves_the_paper_and_lands_in_the_manifest(work, turns, no_renderer):
    """Leaving it in ships the author's margin notes. Dropping it silently loses
    the one place the writer said it could not trace something."""

    class Flagging(turns):
        def write(self, section, claims, figures, notes, path=""):
            self.asked.append(("write", section["id"], notes, path))
            return "## The problem\n\nA point [1]. This section answers: what is a topic [1]. This section answers: why does a topic fail [1]. <!-- NEEDS-SOURCE: the version -->"

    run = make_run(work, Flagging())
    paper.run_paper(run)
    assert "NEEDS-SOURCE" not in (Path(work) / "paper.md").read_text()
    flags = json.loads((Path(work) / "unresolved.json").read_text())["flags"]
    assert flags == [{"section": "s1", "flag": "the version"}]


def test_the_manifest_is_written_even_when_there_is_nothing_in_it(work, turns, no_renderer):
    """A reader has to tell "no flags" from "this run never looked"."""
    paper.run_paper(make_run(work, turns()))
    assert json.loads((Path(work) / "unresolved.json").read_text()) == {"flags": []}


# -- retrying the failing unit ----------------------------------------------


def test_a_planner_that_fails_once_gets_the_gates_complaint(work, turns, no_renderer):
    """One malformed answer used to kill a run before it had a plan."""

    class Flaky(turns):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.tries = 0

        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.tries += 1
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            if self.tries == 1:
                raise TurnFailed("research-outliner returned no JSON object")
            return super().outline(topic, prior_art, budget, note, brief)

    run = make_run(work, Flaky())
    paper.prior_art(run)
    assert paper.plan(run)["questions"] == 2
    notes = [args[4] for args in run.turns.asked if args[0] == "outline"]
    assert notes[0] == "", "the first attempt has nothing to react to"
    assert "no JSON object" in notes[1], "the second is told what failed"


def test_a_planner_that_fails_twice_escalates_on_the_stall(work, turns):
    """Two identical failures are not converging, and the reason says so."""

    class Broken(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            raise TurnFailed("research-outliner returned no JSON object")

    run = make_run(work, Broken())
    paper.prior_art(run)
    with pytest.raises(paper.RunFailed, match="not converging"):
        paper.plan(run)
    assert len([a for a in run.turns.asked if a[0] == "outline"]) == 2


def test_a_runtime_ceiling_is_not_retried(work, turns):
    """Retrying a ceiling spends the rest of the budget rediscovering it."""

    class Capped(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            raise Escalate("max turns")

    run = make_run(work, Capped())
    paper.prior_art(run)
    with pytest.raises(Escalate):
        paper.plan(run)
    assert len([a for a in run.turns.asked if a[0] == "outline"]) == 1


def test_one_bad_question_does_not_kill_the_research_phase(work, turns, no_renderer):
    """A thinner paper, and a record of why. Not a dead run."""

    class Partial(turns):
        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            drafted = super().outline(topic, prior_art, budget, note, brief)
            drafted["sections"][0]["key_questions"] = ["good", "bad"]
            return drafted

        def research(self, question, note=""):
            if question == "bad":
                self.asked.append(("research", question, note))
                raise TurnFailed("research-researcher returned no JSON object")
            return super().research(question, note)

    run = make_run(work, Partial())
    paper.prior_art(run)
    paper.plan(run)
    meta = paper.do_research(run)
    assert meta["failed"] == 1
    assert meta["claims"] == 1
    recorded = json.loads((Path(work) / "sources.json").read_text())["failed"]
    assert recorded[0]["id"] == "s1-q2"
    assert "no JSON object" in recorded[0]["reason"]


def test_a_failing_question_is_retried_once_before_it_is_recorded(work, turns):
    tries = []

    class Flaky(turns):
        def research(self, question, note=""):
            self.asked.append(("research", question, note))
            tries.append(note)
            raise TurnFailed("no JSON")

    run = prepared_plan(work, Flaky())
    with pytest.raises(paper.RunFailed):
        paper.do_research(run)
    assert len(tries) == 4
    assert tries[0] == "" and "no JSON" in tries[1]


def test_a_retry_does_not_run_when_the_budget_is_spent(work, turns):
    """A retry must consult the ceiling before it spends."""

    class Flaky(turns):
        def research(self, question, note=""):
            self.asked.append(("research", question, note))
            run.state.total_usd = 99.0
            raise TurnFailed("no JSON")

    run = prepared_plan(work, Flaky(), max_usd=1.0)
    with pytest.raises(paper.RunFailed):
        paper.do_research(run)
    assert len([a for a in run.turns.asked if a[0] == "research"]) == 1
