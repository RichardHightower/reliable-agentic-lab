"""The documentation is checked, because prose is where the fence drifted.

`roleplan.plan` already refuses a reader that gains a write tool.
`roles.agent_definitions` already raises when an agent file's `tools` disagree
with the table. Neither of them reads a sentence.

So the skill table said the planner held `Write` and the diagrammer held
`Bash`, months after the code removed both, and the writer's own description
named a path the hook denies. A reader following those files copies a fence
the code does not have. These tests are the check that was missing.
"""

from __future__ import annotations

import re
from pathlib import Path

import load_agents
import pytest
import roleplan
import roles

FOLDER = Path(__file__).resolve().parents[1]
SKILL = FOLDER / "plugin" / "skills" / "research-loop" / "SKILL.md"
AGENTS = FOLDER / "plugin" / "agents"

# One house style, published once. Cards cite it rather than each keeping its
# own copy of the rules. #453 #466.
STYLE_URL = "https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style"

CAST = roleplan.plan(None, "research")

# A row is `| name | holds | writes |`.
ROW = re.compile(r"^\|\s*(\w[\w -]*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$", re.M)

# A path a description names as its own: `plan.json`, `paper.md`, `diagrams/`,
# `sections/**`. "Writes nothing" names none, which is the whole point: the
# wrong descriptions did not use a stronger verb, they named a target.
PATH = re.compile(r"\b[\w.-]+\.(?:md|json|png|mmd|puml)\b|\b\w+/(?:\*\*|\w*)")


def skill_rows() -> dict[str, tuple[str, str]]:
    """The cast table out of SKILL.md, as {role: (holds, writes)}."""
    text = SKILL.read_text(encoding="utf-8")
    body = text.split("## The cast", 1)[1].split("##", 1)[0]
    rows = {}
    for name, holds, writes in ROW.findall(body):
        if name.lower() in ("role", "---"):
            continue
        rows[name] = (holds, writes)
    return rows


def test_the_skill_names_the_same_cast_as_the_table():
    assert set(skill_rows()) == set(CAST)


@pytest.mark.parametrize("name", sorted(CAST))
def test_the_skill_writes_column_matches_can_write(name):
    """ "nothing" in the doc means `can_write` is false, and the reverse."""
    _, writes = skill_rows()[name]
    says_nothing = writes.strip().lower() == "nothing"
    assert says_nothing != CAST[name].can_write, f"{name}: doc says {writes!r}"


@pytest.mark.parametrize("name", sorted(CAST))
def test_the_skill_names_every_path_the_role_may_write(name):
    _, writes = skill_rows()[name]
    for allowed in CAST[name].allow:
        assert allowed in writes, f"{name} may write {allowed}, the doc omits it"


def test_the_skill_does_not_promise_a_path_the_hook_denies():
    """`paper.md` is assembly's, and the hook refuses the writer that path."""
    _, writes = skill_rows()["writer"]
    assert "sections/**" in writes
    assert "paper.md" not in writes


def test_no_role_in_the_skill_table_holds_a_shell():
    """Documentation that ships the sledgehammer is the same failure one layer
    up from shipping it."""
    for name, (holds, _) in skill_rows().items():
        assert "Bash" not in holds, f"{name} is documented with a shell"


def test_the_skill_says_it_is_not_loaded():
    """It is on disk as the specification. It is not a runnable action here."""
    assert "not loaded as a runnable skill" in SKILL.read_text(encoding="utf-8")


# -- the agent front matter -------------------------------------------------


@pytest.mark.parametrize(
    "name", sorted(n for n in CAST if n != "orchestrator" and not CAST[n].can_write)
)
def test_a_reader_description_never_names_a_path(name):
    """A model follows the description. The hook then refuses, and the run pays
    for a refusal its own prompt caused.

    "Writes nothing" is the correct wording and names no path. The descriptions
    that were wrong did not use a stronger verb, they named a target.
    """
    described = load_agents.agent_files()[roles.agent_name(name)]["description"]
    assert PATH.findall(described) == [], f"{name} describes a path it cannot write"


def test_the_writer_description_names_only_what_it_may_write():
    """It said "Writes under sections/ and paper.md" while the hook denied
    `paper.md`."""
    described = load_agents.agent_files()["research-writer"]["description"]
    claimed, _, disclaimed = described.partition("Assembly owns")
    assert "sections/" in claimed
    assert PATH.findall(claimed) == ["sections/"], claimed
    assert "paper.md" in disclaimed, "say who does own it"


@pytest.mark.parametrize("name", sorted(n for n in CAST if n != "orchestrator"))
def test_every_agent_file_declares_the_tools_the_table_grants(name):
    """`agent_definitions` raises on this too. Asserting it here names the file
    rather than failing inside an SDK call."""
    declared = load_agents.agent_files()[roles.agent_name(name)]["tools"]
    assert sorted(declared) == sorted(CAST[name].tools)


def test_setup_creates_a_local_venv_and_how_to_run_exists():
    """Homebrew Python is PEP 668. pip into system Python is how a live demo
    died. task setup creates .venv in this folder."""
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    how = FOLDER / "HOW_TO_RUN.md"
    assert ".venv" in taskfile
    assert "venv you activated" not in taskfile
    assert how.is_file()
    text = how.read_text(encoding="utf-8")
    assert "venv you activated" not in text
    assert "task setup" in text
    assert "labs/lab3_research" in text


def test_setup_pins_the_local_image_plugin_releases():
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    assert "RENDERER_TAG: 'v0.2.0'" in taskfile
    assert "IMAGE_GEN_TAG: 'v2.1.0'" in taskfile
    assert ".cache/imagen-diagrams" in taskfile
    assert ".cache/image-gen" in taskfile

    how = (FOLDER / "HOW_TO_RUN.md").read_text(encoding="utf-8")
    assert "does not modify Homebrew's\nsystem Python or `~/.claude`" in how
    assert "v0.2.0" in how and "v2.1.0" in how


def test_the_publication_tasks_and_docs_use_arctic_fox():
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    diagrams = (FOLDER / "diagrams.py").read_text(encoding="utf-8")
    how = (FOLDER / "HOW_TO_RUN.md").read_text(encoding="utf-8")
    assert "  pdf:" in taskfile
    assert "  publish-report:" in taskfile
    assert "--theme arctic-fox" in taskfile
    assert 'DEFAULT_THEME = "arctic-fox"' in diagrams
    assert "paper.pdf.json" in how


def test_the_docs_name_only_tasks_that_exist():
    taskfile = (FOLDER / "Taskfile.yml").read_text(encoding="utf-8")
    declared = set(re.findall(r"^  (\w[\w-]*):$", taskfile, re.M))
    for name in ("SPEC.md", "HOW_TO_RUN.md"):
        prose = (FOLDER / name).read_text(encoding="utf-8")
        for named in re.findall(r"task ([a-z][a-z0-9-]*)", prose):
            assert named in declared, f"{name} names `task {named}`, the Taskfile does not"


def test_the_word_floor_in_the_spec_matches_the_code():
    """One floor, not three. The wiki said 2000, 4000, and 6000 (#307).

    `loop.py` profiles set `word_target_total`, which is what the outline
    commissions. `checks.MIN_WORDS` is what the length row enforces, and it is
    the same number for every profile. Nothing tied the sentence to the
    constant, so the two were free to drift.
    """
    import checks  # noqa: PLC0415

    spec = (FOLDER / "SPEC.md").read_text(encoding="utf-8")
    assert f"Length is hard at {checks.MIN_WORDS} words" in spec
    assert "never the check floor" in spec


def test_the_spec_names_the_unresolved_file_the_code_writes():
    """The SPEC names the file the locator's misses land in, and `sections` owns
    the name. A run that drops a cabinet claim writes it to
    `knowledge/<id>/unresolved.json`, and a reader who cannot find that file
    reads the drop as a bug rather than as the record it is.
    """
    import sections  # noqa: PLC0415

    spec = (FOLDER / "SPEC.md").read_text(encoding="utf-8")
    assert f"`knowledge/<id>/{sections.UNRESOLVED_FILE}`" in spec


def test_the_spec_names_every_profile_the_code_has():
    import loop  # noqa: PLC0415

    spec = (FOLDER / "SPEC.md").read_text(encoding="utf-8")
    for name, profile in loop.PROFILES.items():
        assert f"`--profile {name}`" in spec, f"SPEC.md does not name --profile {name}"
        assert str(profile["word_target_total"]) in spec, name


def test_the_writer_card_and_the_grounding_contract_teach_the_term_marker():
    """The Glossary has no producer without this. The writer must be told
    the TERM marker syntax, once, both in its own card and in the grounding
    contract every generating turn receives."""
    card = (FOLDER / "plugin" / "agents" / "research-writer.md").read_text(encoding="utf-8")
    assert card.count("TERM:") == 1
    assert load_agents.GROUNDING.count("TERM:") == 1


# -- P8, cards cite the house style page -------------------------------------


def test_both_writer_cards_cite_the_style_page():
    """#453 #466: the writer follows one house style, published once on the
    wiki. This port's half of the pair; the Deep Agents copy carries the
    other half of the same test."""
    card = (AGENTS / "research-writer.md").read_text(encoding="utf-8")
    assert STYLE_URL in card


@pytest.mark.parametrize(
    "name",
    [
        "research-judge.md",
        "research-section-judge.md",
        "research-outline-judge.md",
        "research-outline-editor.md",
    ],
)
def test_every_judge_card_cites_the_style_page(name):
    """The paper judge, the section judge, and the outline pair all grade or
    repair against the page named here, not a private copy of the rules."""
    card = (AGENTS / name).read_text(encoding="utf-8")
    assert STYLE_URL in card


def test_the_voice_row_does_not_repeat_a_python_row():
    """`voice` stops re-reporting a row Python already fails: a contraction,
    a Latin abbreviation, second person, a marketing verb, a policy leak, or
    an em dash. Naming one again duplicates a mechanical check."""
    card = (AGENTS / "research-judge.md").read_text(encoding="utf-8")
    match = re.search(r"^\|\s*`voice`\s*\|(.*)\|\s*$", card, re.M)
    assert match, "no `voice` row in research-judge.md"
    row = match.group(1).lower()
    banned = (
        "contraction",
        "latin abbreviation",
        "e.g.",
        "i.e.",
        "etc.",
        "second person",
        "marketing",
        "policy leak",
        "em dash",
    )
    hits = [term for term in banned if term in row]
    assert not hits, f"voice row repeats a Python row: {hits}"


def test_the_check_module_docstring_lists_belt_rows_against_judge_rows():
    """`checks.__doc__` names every row `check()` appends and every row
    `research-judge.md` grades, matching the house style page's ownership
    table."""
    import checks  # noqa: PLC0415

    src = Path(checks.__file__).read_text(encoding="utf-8")
    body = src.split("def check(", 1)[1].split("\ndef section_check(", 1)[0]
    belt_rows = set(re.findall(r'Check\(\s*"([a-zA-Z_]\w*)"', body))
    assert belt_rows, "no Check(\"name\" calls found in checks.check()"
    doc = checks.__doc__ or ""
    missing_belt = sorted(row for row in belt_rows if row not in doc)
    assert not missing_belt, f"docstring omits belt row(s): {missing_belt}"

    card = (AGENTS / "research-judge.md").read_text(encoding="utf-8")
    judge_rows = set(re.findall(r"^\|\s*`(\w+)`\s*\|", card, re.M))
    assert judge_rows, "no judge rows found in research-judge.md"
    missing_judge = sorted(row for row in judge_rows if row not in doc)
    assert not missing_judge, f"docstring omits judge row(s): {missing_judge}"


# -- P13, docs cite rows and constants that exist ----------------------------

# One level above this port, next to the other three take-home folders. A
# copy of this folder alone has no sibling `slides/`, so the one test below
# that reads it skips rather than fails outside the monorepo checkout.
FEATURE_MAP = FOLDER.parent.parent / "slides" / "FEATURE-MAP.md"

# A bare backticked name, `like_this`, never `a/path.py` or `--a-flag`: the
# dot, the slash, and the dash all fall outside this pattern, so a filename
# or a CLI flag quoted for readability is never mistaken for a row name.
_BARE_IDENTIFIER = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")

# A name that only appears inside a comment or a docstring is not a row
# definition, so it must not satisfy the check below. Regex, not
# `tokenize`: a `#` inside a string literal could still be swallowed.
# ponytail: upgrade to `tokenize` if that ever produces a false negative.
_DOCSTRING = re.compile(r'("""|\'\'\')[\s\S]*?\1')
_COMMENT = re.compile(r"#.*")


def _code_only(src: str) -> str:
    return _COMMENT.sub("", _DOCSTRING.sub("", src))


def _row_haystack() -> str:
    import checks  # noqa: PLC0415

    src = Path(checks.__file__).read_text(encoding="utf-8")
    src += (FOLDER / "source_policy.py").read_text(encoding="utf-8")
    return _code_only(src)


def _unknown_names(cited: set[str], haystack: str) -> list[str]:
    return sorted(name for name in cited if not re.search(rf"\b{re.escape(name)}\b", haystack))


# SPEC.md, HOW_TO_RUN.md, and DESIGN_DOC.md all carry one house-style
# section, cited from the same check module and the same source_policy.py.
# DESIGN_DOC.md numbers its copy of the heading; the others do not. #467
# #480.
STYLE_DOCS = ("SPEC.md", "HOW_TO_RUN.md", "DESIGN_DOC.md")
STYLE_SECTION = re.compile(r"^## (?:\d+\.\s*)?House style and the evidence contract\n", re.M)


def _style_section_text(text: str, label: str) -> str:
    match = STYLE_SECTION.search(text)
    assert match, f"{label} has no House style and the evidence contract section"
    return text[match.end() :].split("\n## ", 1)[0]


def test_feature_map_module_three_names_the_style():
    """#467: a reader of Module 3 finds house style, glossary, and CTA named,
    not only a citation row, and every backticked name there is a real row
    or constant, not drift. The judge inserted `totally_fake_row` into the
    FEATURE-MAP paragraphs and this test is the one that now catches it."""
    if not FEATURE_MAP.is_file():
        pytest.skip("slides/FEATURE-MAP.md sits one level above a standalone copy")
    text = FEATURE_MAP.read_text(encoding="utf-8")
    module_three = "\n".join(line for line in text.splitlines() if "| 3 |" in line)
    assert "house style" in module_three.lower(), module_three
    assert "glossary" in module_three.lower(), module_three
    assert "cta" in module_three.lower(), module_three
    assert STYLE_URL in text

    tail = text.split("Module 4 is the same graph with nobody at the keyboard.", 1)[-1]
    cited = set(_BARE_IDENTIFIER.findall(module_three + "\n" + tail))
    assert cited, "FEATURE-MAP Module 3 names no row or constant to verify"
    unknown = _unknown_names(cited, _row_haystack())
    assert not unknown, f"FEATURE-MAP names {unknown}, absent from checks.py/source_policy.py"


@pytest.mark.parametrize("name", STYLE_DOCS)
def test_both_specs_name_the_evidence_contract(name):
    """#480: SPEC.md, HOW_TO_RUN.md, and DESIGN_DOC.md name only rows and
    constants that `checks.py` and `source_policy.py` actually define, a
    comment or a docstring mention excluded. The Deep Agents copy runs the
    same check against its own three files."""
    haystack = _row_haystack()

    text = (FOLDER / name).read_text(encoding="utf-8")
    assert STYLE_URL in text
    section = _style_section_text(text, name)
    cited = set(_BARE_IDENTIFIER.findall(section))
    assert cited, f"{name} names no row or constant to verify"
    unknown = _unknown_names(cited, haystack)
    assert not unknown, f"{name} names {unknown}, absent from checks.py/source_policy.py"
