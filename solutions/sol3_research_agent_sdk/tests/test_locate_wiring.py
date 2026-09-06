"""The locator, wired into the section loop.

Every test here drives `paper.do_sections` or `sections.run_section`. A test
that called `locate_cabinet_findings` on its own would stay green when the call
site is reverted, and the call site is the whole point: a cabinet finding that
cannot be located must leave the pipeline before the gap pass, not after the
bibliography is written.

The brain is built with `rkc.write_node`, the same three-node shape
`tests/test_rkc.py` uses for `attach_url`.
"""

from __future__ import annotations

import json
from pathlib import Path

import corpus
import paper
import pytest
import rkc
import sections
from turns import Escalate, TurnFailed

TOPIC = "multi agent failure"

SHARED_HASH = "sha256:" + "a" * 64
MIDDLE_HASH = "sha256:" + "b" * 64
UNTITLED_HASH = "sha256:" + "c" * 64
OFFPACK_HASH = "sha256:" + "d" * 64

SHARED_TITLE = "Why Do Multi-Agent LLM Systems Fail?"
OFFPACK_TITLE = "An Off Pack Source"
MIDDLE_URL = "https://arxiv.org/abs/2307.03172"
FOUND_URL = "https://arxiv.org/abs/2503.13657"
WEB_URL = "https://docs.langchain.com/x"

ALPHA = "knowledge:claim.agent-alpha.01TESTALPHA"
BETA = "knowledge:claim.agent-beta.01TESTBETA0"
MIDDLE = "knowledge:claim.agent-middle.01TESTMID0"
UNTITLED = "knowledge:claim.agent-untitled.01TESTUNT"
OFFPACK = "knowledge:claim.offpack.01TESTOFFPACK"
# Two claims whose ids end in the same ULID. A researcher citing that ULID has
# named both papers and neither.
DUP_ONE = "knowledge:claim.agent-dup-one.01TESTDUPE"
DUP_TWO = "knowledge:claim.agent-dup-two.01TESTDUPE"
DUP_SUFFIX = "01TESTDUPE"

ALPHA_TEXT = "Multi agent systems fail from a specification gap."
BETA_TEXT = "Multi agent systems fail from inter agent misalignment."
MIDDLE_TEXT = "A multi agent prompt loses the middle of its context."
UNTITLED_TEXT = "An untitled source still carries a multi agent claim."
# No topic term in this sentence, so `corpus.pack` scores it zero and the pack
# never carries it. Only the `corpus.resolve` fallback can find it.
OFFPACK_TEXT = "Nothing in this sentence is about the run subject."
DUP_TEXT = "A multi agent duplicate claim."


# -- the brain ---------------------------------------------------------------


def _source(root: Path, node_id: str, title: str, source_hash: str, url: str = "") -> None:
    fields = {
        "id": node_id,
        "title": title,
        "vendor": "arXiv",
        "source_kind": "reference_doc",
        "source_hash": source_hash,
        "captured_at": "2026-01-01T00:00:00Z",
    }
    if url:
        fields["url"] = url
    rkc.write_node(root, "SourceDocument", fields, "Retrieved for the locate check.")


def _claim(root: Path, claim_id: str, text: str, source_hash: str, tag: str) -> None:
    evidence_id = f"evidence.{tag}.01TESTEVIDENCE"
    rkc.write_node(
        root,
        "Evidence",
        {
            "id": evidence_id,
            "title": "A quote",
            "kind": "quote",
            "text": text,
            "source_hash": source_hash,
            "locator": {"variant": "quote", "asset_path": f"research/source-assets/{tag}.md"},
        },
        text,
    )
    rkc.write_node(
        root,
        "Claim",
        {
            "id": claim_id,
            "title": text,
            "description": text,
            "confidence": 0.9,
            "links": [{"rel": "evidenced_by", "target": evidence_id}],
        },
        f"# Claim\n\n{text}",
    )


@pytest.fixture
def brain(tmp_path) -> Path:
    """Four sources: one shared by two claims, one published, one untitled, one off pack."""
    root = tmp_path / "knowledge"
    corpus.clear_cache()
    _source(root, "source.shared.01TESTSHARED", SHARED_TITLE, SHARED_HASH)
    _claim(root, ALPHA.split(":", 1)[1], ALPHA_TEXT, SHARED_HASH, "alpha")
    _claim(root, BETA.split(":", 1)[1], BETA_TEXT, SHARED_HASH, "beta")

    _source(root, "source.middle.01TESTMIDDLE", "Lost in the Middle", MIDDLE_HASH, url=MIDDLE_URL)
    _claim(root, MIDDLE.split(":", 1)[1], MIDDLE_TEXT, MIDDLE_HASH, "middle")

    _source(root, "source.untitled.01TESTUNTITLE", "", UNTITLED_HASH)
    _claim(root, UNTITLED.split(":", 1)[1], UNTITLED_TEXT, UNTITLED_HASH, "untitled")

    _source(root, "source.offpack.01TESTOFFPACK", OFFPACK_TITLE, OFFPACK_HASH)
    _claim(root, OFFPACK.split(":", 1)[1], OFFPACK_TEXT, OFFPACK_HASH, "offpack")

    _claim(root, DUP_ONE.split(":", 1)[1], DUP_TEXT, SHARED_HASH, "dupone")
    _claim(root, DUP_TWO.split(":", 1)[1], DUP_TEXT, SHARED_HASH, "duptwo")
    corpus.clear_cache()
    return root


# -- the stub ----------------------------------------------------------------


def cabinet_claim(key: str, text: str) -> dict:
    """What the researcher returns when it answered out of the cabinet."""
    return {"text": text, "source_url": f"corpus:{key}", "quote": text, "origin": "corpus"}


def web_claim(text: str = "The librarian found this on the web.") -> dict:
    return {"text": text, "source_url": WEB_URL, "quote": text}


def make_turns(base, plan, answers=None, root=None, fail=""):
    """A RecordingTurns whose outline is `plan` and whose research cites the cabinet.

    `plan` is `[(section_id, [(question, [claim, ...]), ...]), ...]`. `answers`
    maps a source title to the locator reply. `fail` makes every locate turn
    raise `TurnFailed`.
    """

    class Cabinet(base):
        def __init__(self):
            super().__init__(root=root)
            self.locate_calls: list[tuple] = []
            self.researched: list[str] = []
            self.written_claims: list[dict] = []

        def outline(self, topic, prior_art, budget=None, note="", brief=""):
            self.asked.append(("outline", topic, prior_art, budget, note, brief))
            words = int((budget or {}).get("words") or 400)
            each = max(80, words // len(plan))
            return {
                "title": f"On {topic}",
                "audience": "engineers",
                "thesis": "An abstract.",
                "word_target_total": each * len(plan),
                "sections": [
                    {
                        "id": sid,
                        "heading": f"Part {sid}",
                        "objective": "State it.",
                        "abstract": "This section states the problem.",
                        "key_questions": [question for question, _ in rows],
                        "claims_to_support": ["The problem is structural."],
                        "required_evidence": ["a primary specification"],
                        "word_target": each,
                        "figures": [],
                        "depends_on": [],
                    }
                    for sid, rows in plan
                ],
            }

        def research(self, question, note=""):
            self.asked.append(("research", question, note))
            self.researched.append(question)
            # The gap pass asks again. The cabinet already said what it had.
            if self.researched.count(question) > 1:
                return {"answer": "", "sources": [], "claims": []}
            for _sid, rows in plan:
                for text, claims in rows:
                    if text == question:
                        return {
                            "answer": "An answer.",
                            "sources": [{"url": WEB_URL, "title": "Doc"}],
                            "claims": [dict(claim) for claim in claims],
                        }
            return {"answer": "", "sources": [], "claims": []}

        def locate(self, title, vendor, claim_head):
            self.locate_calls.append((title, vendor, claim_head))
            if fail:
                raise TurnFailed(fail)
            return (answers or {}).get(title) or {"url": "", "supports": False, "excerpt": ""}

        def write(self, section, claims, figures, notes, path=""):
            self.written_claims.extend(claims)
            return super().write(section, claims, figures, notes, path)

    return Cabinet()


def make_run(work, brain_root, turns_obj, **kwargs):
    return paper.Run(
        topic=TOPIC,
        work_dir=work,
        turns=turns_obj,
        state=paper.State.load_or_new(work, TOPIC),
        brain=brain_root,
        log=lambda *a: None,
        **kwargs,
    )


def drive(work, brain_root, turns_obj, **kwargs):
    """prior art, outline, section loop. Escalation is a result, not a crash."""
    run = make_run(work, brain_root, turns_obj, **kwargs)
    paper.prior_art(run)
    paper.plan(run)
    try:
        paper.do_sections(run)
    except (Escalate, paper.RunFailed):
        pass
    return run


def findings_of(work, sid="s1") -> list[dict]:
    path = Path(work) / "knowledge" / sid / "findings.json"
    return json.loads(path.read_text(encoding="utf-8"))["findings"] if path.exists() else []


def unresolved_of(work, sid="s1") -> list[dict]:
    path = Path(work) / "knowledge" / sid / sections.UNRESOLVED_FILE
    return json.loads(path.read_text(encoding="utf-8"))["unresolved"]


def urls_of(findings: list[dict]) -> list[str]:
    return [(f.get("source") or {}).get("url_or_path") or "" for f in findings]


# -- the tests ---------------------------------------------------------------


def test_the_pack_carries_the_keys_the_stub_cites(work, brain, turns):
    """A sanity rail. Every other test reads these keys back out of the loop."""
    run = make_run(work, brain, turns())
    paper.prior_art(run)
    packed = json.loads((Path(work) / "corpus" / "brain-pack.json").read_text(encoding="utf-8"))
    keys = packed["keys"]
    assert ALPHA in keys and BETA in keys and MIDDLE in keys and UNTITLED in keys
    assert DUP_ONE in keys and DUP_TWO in keys
    # The off-pack claim scores zero against the topic, so only the brain has it.
    assert OFFPACK not in keys


def test_a_cabinet_hit_that_already_carries_a_url_is_not_sent_to_the_locator(
    work, brain, turns
):
    stub = make_turns(
        turns,
        [("s1", [("what loses the middle", [cabinet_claim(MIDDLE, MIDDLE_TEXT)]),
                 ("what else is known", [web_claim()])])],
    )
    drive(work, brain, stub)

    assert stub.locate_calls == []
    found = findings_of(work)
    assert MIDDLE_URL in urls_of(found)
    # The reader gets the URL; the audit trail still names the cabinet record.
    assert [f["source"]["located_from"] for f in found if f["source"]["kind"] == "corpus"] == [
        MIDDLE
    ]


def test_a_finding_that_already_holds_an_http_url_is_not_relocated(work, brain, turns):
    """A resumed cabinet finding, and a librarian web finding. Neither costs a turn."""
    resumed = {"text": MIDDLE_TEXT, "source_url": MIDDLE_URL, "quote": "q", "origin": "corpus"}
    stub = make_turns(
        turns,
        [("s1", [("what loses the middle", [resumed]), ("what else is known", [web_claim()])])],
    )
    drive(work, brain, stub)

    assert stub.locate_calls == []
    assert sorted(urls_of(findings_of(work))) == sorted([MIDDLE_URL, WEB_URL])


def test_two_findings_from_one_source_cost_one_locate_turn(work, brain, turns):
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                 ("what fails next", [cabinet_claim(BETA, BETA_TEXT)])])],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert len(stub.locate_calls) == 1, stub.locate_calls
    assert stub.locate_calls[0][0] == SHARED_TITLE

    found = findings_of(work)
    assert urls_of(found) == [FOUND_URL, FOUND_URL], found
    assert [f["source"]["kind"] for f in found] == ["corpus", "corpus"]
    assert [f["source"]["located_from"] for f in found] == [ALPHA, BETA]
    assert [f["origin"] for f in found] == ["corpus", "corpus"]

    # The brain learned it too.
    source = next((brain / "research" / "sources").glob("source.shared*.md"))
    assert f'url: "{FOUND_URL}"' in source.read_text(encoding="utf-8")

    cache = json.loads((Path(work) / sections.LOCATED_FILE).read_text(encoding="utf-8"))
    assert cache[SHARED_HASH]["url"] == FOUND_URL


def test_a_second_section_pays_nothing_for_a_source_the_run_located(work, brain, turns):
    stub = make_turns(
        turns,
        [
            ("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                    ("what else is known", [web_claim()])]),
            ("s2", [("what fails next", [cabinet_claim(BETA, BETA_TEXT)]),
                    ("what more is known", [web_claim()])]),
        ],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert len(stub.locate_calls) == 1, stub.locate_calls
    assert FOUND_URL in urls_of(findings_of(work, "s1"))
    assert FOUND_URL in urls_of(findings_of(work, "s2"))


def test_a_source_with_no_title_is_a_miss_that_never_reaches_the_paper(work, brain, turns):
    stub = make_turns(
        turns,
        [("s1", [("what has no title", [cabinet_claim(UNTITLED, UNTITLED_TEXT)]),
                 ("what else is known", [web_claim()])])],
    )
    drive(work, brain, stub)

    # Nothing to search with, so nothing was spent asking.
    assert stub.locate_calls == []

    rows = unresolved_of(work)
    assert [row["reason"] for row in rows] == ["no title to locate"]
    assert rows[0]["key"] == UNTITLED

    assert UNTITLED_TEXT not in [f.get("claim") for f in findings_of(work)]
    assert UNTITLED_TEXT not in [claim.get("text") for claim in stub.written_claims]
    # The question it answered is a gap now, and the gap pass asked again.
    assert stub.researched.count("what has no title") == 2, stub.researched


def test_a_locator_miss_is_recorded_and_the_finding_is_dropped(work, brain, turns):
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={SHARED_TITLE: {"url": "", "supports": False, "excerpt": ""}},
    )
    drive(work, brain, stub)

    assert len(stub.locate_calls) == 1
    assert [row["reason"] for row in unresolved_of(work)] == ["not found"]
    assert ALPHA_TEXT not in [f.get("claim") for f in findings_of(work)]


def test_an_unresolvable_corpus_key_is_a_miss(work, brain, turns):
    stub = make_turns(
        turns,
        [("s1", [("what is missing", [cabinet_claim("knowledge:claim.nope.01TESTNOPE", "x")]),
                 ("what else is known", [web_claim()])])],
    )
    drive(work, brain, stub)

    assert stub.locate_calls == []
    assert [row["reason"] for row in unresolved_of(work)] == ["unresolved corpus key"]


def test_a_suffix_only_one_pack_key_ends_with_resolves(work, brain, turns):
    """A researcher writes the bare ULID. One pack key owns it, so it resolves."""
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim("01TESTALPHA", ALPHA_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert len(stub.locate_calls) == 1, stub.locate_calls
    assert unresolved_of(work) == []
    found = findings_of(work)
    assert FOUND_URL in urls_of(found)
    assert [f["source"]["located_from"] for f in found if f["source"]["kind"] == "corpus"] == [
        ALPHA
    ]


def test_a_suffix_two_pack_keys_share_is_a_miss_not_a_guess(work, brain, turns):
    """`corpus.resolve` would answer with whichever claim file sorted first."""
    stub = make_turns(
        turns,
        [("s1", [("which paper is it", [cabinet_claim(DUP_SUFFIX, DUP_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert stub.locate_calls == []
    rows = unresolved_of(work)
    assert [row["reason"] for row in rows] == [
        f"ambiguous corpus key: {DUP_ONE}, {DUP_TWO}"
    ], rows
    assert DUP_TEXT not in [f.get("claim") for f in findings_of(work)]
    assert DUP_TEXT not in [claim.get("text") for claim in stub.written_claims]


def test_a_key_the_pack_missed_still_resolves_through_the_brain(work, brain, turns):
    """`corpus.pack` keeps what scored against the topic. `corpus.resolve` keeps everything."""
    stub = make_turns(
        turns,
        [("s1", [("what is off pack", [cabinet_claim(OFFPACK, OFFPACK_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={OFFPACK_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert len(stub.locate_calls) == 1, stub.locate_calls
    assert unresolved_of(work) == []
    assert FOUND_URL in urls_of(findings_of(work))


def test_the_pack_answers_before_the_brain_is_searched(work, brain, turns, monkeypatch):
    """The pack is already in memory. Walking every claim file again is the fallback."""
    monkeypatch.setattr(sections.corpus, "resolve", lambda key, roots: None)
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    drive(work, brain, stub)

    assert unresolved_of(work) == []
    assert FOUND_URL in urls_of(findings_of(work))


def test_a_locate_turn_that_fails_is_a_miss_and_the_section_still_stamps(work, brain, turns):
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                 ("what else is known", [web_claim()])])],
        fail="the locator backend refused",
    )
    drive(work, brain, stub)

    assert [row["reason"] for row in unresolved_of(work)] == ["the locator backend refused"]
    ledger = json.loads((Path(work) / "paper_ledger.json").read_text(encoding="utf-8"))
    assert [entry["section_id"] for entry in ledger["entries"]] == ["s1"]


def test_a_spent_budget_locates_nothing(work, brain, turns):
    """The locator is a paid turn. A run with no budget left reports the miss instead."""
    stub = make_turns(
        turns,
        [("s1", [("what fails first", [cabinet_claim(ALPHA, ALPHA_TEXT)]),
                 ("what else is known", [web_claim()])])],
        answers={SHARED_TITLE: {"url": FOUND_URL, "supports": True, "excerpt": "abstract"}},
    )
    run = make_run(work, brain, stub, max_usd=0.0)
    paper.prior_art(run)
    section = {
        "id": "s1",
        "heading": "The problem",
        "objective": "State it.",
        "abstract": "This section states the problem.",
        "key_questions": ["what fails first", "what else is known"],
        "claims_to_support": ["The problem is structural."],
        "required_evidence": ["a spec"],
        "word_target": 80,
        "figures": [],
        "depends_on": [],
    }
    with pytest.raises(Escalate):
        sections.run_section(run, section)

    assert stub.locate_calls == []
    assert [row["reason"] for row in unresolved_of(work)] == ["cost budget spent"]
