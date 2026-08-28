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
