"""This folder is standalone. Copy it somewhere else and it runs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = r"^from loops|^import loops|^from solutions|^import solutions|from \.\."

SKILLS = ROOT / "skills"

# One house style, published once. Cards cite it rather than each keeping its
# own copy of the rules. #453 #466.
STYLE_URL = "https://github.com/RichardHightower/reliable-agentic-lab/wiki/Sol-3-White-Paper-Style"


def test_no_shared_engine_imports():
    """CLAUDE.md forbids a shared library. Duplication is the point, because a
    five hour audience should not have to learn an abstraction first."""
    out = subprocess.run(
        ["grep", "-rnE", FORBIDDEN, "--include=*.py",
         "--exclude-dir=.venv", "--exclude-dir=.cache", "--exclude-dir=work", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hits = [line for line in out.stdout.split("\n") if line and "/tests/" not in line]
    assert not hits, "\n".join(hits)


def test_every_module_imports_with_no_sdk():
    """No deepagents, no langchain, no key, no network."""
    names = sorted(path.stem for path in ROOT.glob("*.py") if path.stem not in ("__init__",))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import importlib\n"
        f"for name in {names!r}: importlib.import_module(name)\n"
        "assert 'deepagents' not in sys.modules\n"
        "assert 'langchain' not in sys.modules\n"
        "print('ok')"
    )
    out = subprocess.run(
        ["python3", "-c", code], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_the_check_scripts_pass_their_own_assertions():
    """`task checks` runs these. A demo that drifts from the code is worse than
    no demo."""
    for module in ("evidence", "paper_check", "publish", "diagrams", "mcp_tools", "charts"):
        out = subprocess.run(
            ["python3", f"{module}.py", "--demo"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert out.returncode == 0, f"{module}: {out.stderr}"
        assert "passed" in out.stdout, module


def test_the_folder_carries_its_own_theme():
    """It copies the theme rather than reaching up two levels, or it is not
    standalone."""
    assert (ROOT / "themes" / "spillwave-light.yaml").exists()
    assert (ROOT / "themes" / "mermaid.json").exists()


def test_every_model_facing_role_has_a_skill():
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)

    for name, role in roleplan.plan(None, "paper").items():
        if name == "orchestrator":
            continue
        assert (ROOT / "skills" / name / "SKILL.md").exists(), name
        assert role.purpose


def test_the_writer_card_forbids_second_person():
    """P2's catch-up with the SDK: the no-second-person rule and the
    never-write-about-the-run line each appear once, not twice."""
    body = (ROOT / "skills" / "writer" / "SKILL.md").read_text(encoding="utf-8")
    assert body.lower().count("second person") == 1
    assert body.lower().count("narration of the run") == 1


def test_the_writer_card_teaches_the_term_marker():
    """The Glossary has no producer without this: the writer must be told
    the TERM marker syntax, once."""
    body = (ROOT / "skills" / "writer" / "SKILL.md").read_text(encoding="utf-8")
    assert body.count("TERM:") == 1


# -- P8, cards cite the house style page -------------------------------------


def test_both_writer_cards_cite_the_style_page():
    """#453 #466: the writer follows one house style, published once on the
    wiki. This port's half of the pair; the SDK card carries the other half
    of the same test."""
    card = (SKILLS / "writer" / "SKILL.md").read_text(encoding="utf-8")
    assert STYLE_URL in card


@pytest.mark.parametrize("name", ["reviewer", "section_judge", "outline_judge"])
def test_every_judge_card_cites_the_style_page(name):
    """The reviewer, the section judge, and the outline judge all grade
    against the page named here, not a private copy of the rules."""
    card = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    assert STYLE_URL in card


def test_the_voice_row_does_not_repeat_a_python_row():
    """`voice` stops re-reporting a row Python already fails: a contraction,
    a Latin abbreviation, second person, a marketing verb, a policy leak, or
    an em dash. Naming one again duplicates a mechanical check."""
    card = (SKILLS / "reviewer" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^\|\s*`voice`\s*\|(.*)\|\s*$", card, re.M)
    assert match, "no `voice` row in reviewer/SKILL.md"
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
    """`paper_check.__doc__` names every row `check()` appends and every row
    `skills/reviewer/SKILL.md` grades, matching the house style page's
    ownership table."""
    import paper_check  # noqa: PLC0415

    src = Path(paper_check.__file__).read_text(encoding="utf-8")
    body = src.split("def check(", 1)[1].split("\ndef _ledger_blob(", 1)[0]
    belt_rows = set(re.findall(r'Check\(\s*"([a-zA-Z_]\w*)"', body))
    assert belt_rows, "no Check(\"name\" calls found in paper_check.check()"
    doc = paper_check.__doc__ or ""
    missing_belt = sorted(row for row in belt_rows if row not in doc)
    assert not missing_belt, f"docstring omits belt row(s): {missing_belt}"

    card = (SKILLS / "reviewer" / "SKILL.md").read_text(encoding="utf-8")
    judge_rows = set(re.findall(r"^\|\s*`(\w+)`\s*\|", card, re.M))
    assert judge_rows, "no judge rows found in reviewer/SKILL.md"
    missing_judge = sorted(row for row in judge_rows if row not in doc)
    assert not missing_judge, f"docstring omits judge row(s): {missing_judge}"


# -- P13, docs cite rows and constants that exist ----------------------------

# A bare backticked name, `like_this`, never `a/path.py` or `--a-flag`: the
# dot, the slash, and the dash all fall outside this pattern, so a filename
# or a CLI flag quoted for readability is never mistaken for a row name.
_BARE_IDENTIFIER = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")

# SPEC.md, DESIGN_DOC.md, and AGENTS.md all carry one house-style section,
# cited from the same check module and the same source_policy.py. #467 #480.
STYLE_DOCS = ("SPEC.md", "DESIGN_DOC.md", "AGENTS.md")
STYLE_SECTION = "## House style and the evidence contract"


@pytest.mark.parametrize("name", STYLE_DOCS)
def test_both_specs_name_the_evidence_contract(name):
    """#480: SPEC.md, DESIGN_DOC.md, and AGENTS.md name only rows and
    constants that `paper_check.py`, `sections.py`, and `source_policy.py`
    actually carry. The Agent SDK copy runs the same check against its own
    two files."""
    haystack = (ROOT / "paper_check.py").read_text(encoding="utf-8")
    haystack += (ROOT / "sections.py").read_text(encoding="utf-8")
    haystack += (ROOT / "source_policy.py").read_text(encoding="utf-8")

    text = (ROOT / name).read_text(encoding="utf-8")
    assert STYLE_SECTION in text, f"{name} has no {STYLE_SECTION!r} section"
    assert STYLE_URL in text
    section = text.split(STYLE_SECTION, 1)[1].split("\n## ", 1)[0]
    cited = _BARE_IDENTIFIER.findall(section)
    assert cited, f"{name} names no row or constant to verify"
    unknown = sorted(
        name_ for name_ in set(cited) if not re.search(rf"\b{re.escape(name_)}\b", haystack)
    )
    assert not unknown, (
        f"{name} names {unknown}, absent from paper_check.py/sections.py/source_policy.py"
    )
