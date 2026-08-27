"""Every generated file must match what the generator would write.

`scripts/build_labs.py` is the single source for the lab tree and the solution
tree. A hand edit to any file it owns is drift, and by Saturday the four tools
disagree. These tests read the tree and compare it to the generator. They write
nothing, so running them cannot repair the drift they find. Run
`python scripts/build_labs.py` for that.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from solutions import roleplan

ROOT = Path(__file__).resolve().parents[2]


def _load_generator():
    """Import `scripts/build_labs.py` by path. It is a script, not a package."""
    spec = importlib.util.spec_from_file_location("build_labs", ROOT / "scripts" / "build_labs.py")
    module = importlib.util.module_from_spec(spec)
    # `@dataclass` looks the module up in sys.modules, so register it first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bl = _load_generator()


def _drift(expected: dict[Path, str]) -> list[str]:
    """Return one line per file that is missing or does not match."""
    out = []
    for path, text in expected.items():
        rel = path.relative_to(ROOT)
        if not path.is_file():
            out.append(f"{rel}: missing")
        elif path.read_text(encoding="utf-8") != text:
            out.append(f"{rel}: does not match the generator")
    return out


def test_every_generated_lab_file_matches_the_generator():
    expected: dict[Path, str] = {}
    for lab in bl.LABS_SPEC:
        folder = bl.LABS / lab.slug
        expected[folder / "README.md"] = bl.readme_for(lab)
        expected[folder / "FALL-BEHIND.md"] = bl.fall_behind_for(lab)
        expected[folder / "ARCHITECTURE.md"] = bl.architecture_for(lab)
        expected[folder / "TROUBLESHOOTING.md"] = bl.troubleshooting_for(lab)
        for tool_key in bl.TOOLS:
            expected[folder / "prompts" / f"{tool_key}.md"] = bl.prompt_for(lab, tool_key)
    assert _drift(expected) == []


def test_every_lab_stub_is_either_the_stub_or_the_answer():
    """`done-m<n>` carries the filled answer in the lab folder, so accept both.

    What this rules out is a third body: a hand edit that is neither.
    """
    wrong = []
    for lab in bl.LABS_SPEC:
        path = bl.LABS / lab.slug / lab.stub_file
        body = path.read_text(encoding="utf-8")
        if body not in (lab.stub_body, lab.solved_body):
            wrong.append(str(path.relative_to(ROOT)))
    assert wrong == []


def test_every_generated_solution_file_matches_the_generator():
    expected: dict[Path, str] = {}
    for lab in bl.LABS_SPEC:
        for tool_key, suffix in bl.VARIANTS.items():
            folder = bl.SOLUTIONS / f"{lab.sol_slug}{suffix}"
            expected[folder / lab.stub_file] = lab.solved_body
            expected[folder / "SPEC.md"] = bl.spec_for(lab, tool_key)
            expected[folder / "Taskfile.yml"] = bl.SOLUTION_TASKFILE
    assert _drift(expected) == []


def test_every_generated_port_matches_the_generator():
    expected: dict[Path, str] = {}
    for lab in bl.LABS_SPEC:
        for runtime_key in bl.RUNTIMES:
            folder = bl.SOLUTIONS / f"{lab.sol_slug}_{runtime_key}"
            expected[folder / lab.stub_file] = bl.port_for(lab, runtime_key)
            expected[folder / "SPEC.md"] = bl.port_spec_for(lab, runtime_key)
            expected[folder / "Taskfile.yml"] = bl.SOLUTION_TASKFILE
    assert _drift(expected) == []


def test_the_generator_and_the_role_table_agree_on_the_casts():
    """`build_labs.py` renders the cast into each SPEC. `roleplan.py` owns it.

    Two copies of one list is how a spec starts describing a loop that no
    longer exists.
    """
    assert bl.ROLE_CASTS == roleplan.LOOPS


def test_a_solution_is_never_a_stub():
    """A solution folder holding an unfilled body is the one failure that would
    ship silently: the tree looks complete and the answer key is empty."""
    for lab in bl.LABS_SPEC:
        assert lab.solved_body, f"{lab.slug} has no solved_body"
        assert "NotImplementedError" not in lab.solved_body, f"{lab.slug} answer is still a stub"


def test_every_root_shim_is_a_copy_of_the_original():
    original = (bl.LABS / "_root.py").read_text(encoding="utf-8")
    expected = {bl.LABS / lab.slug / "_root.py": original for lab in bl.LABS_SPEC}
    for lab in bl.LABS_SPEC:
        for suffix in bl.VARIANTS.values():
            expected[bl.SOLUTIONS / f"{lab.sol_slug}{suffix}" / "_root.py"] = original
        for runtime_key in bl.RUNTIMES:
            expected[bl.SOLUTIONS / f"{lab.sol_slug}_{runtime_key}" / "_root.py"] = original
    assert _drift(expected) == []


def test_a_solution_slug_matches_its_lab():
    for lab in bl.LABS_SPEC:
        assert lab.slug.startswith("lab")
        assert lab.sol_slug == lab.slug.replace("lab", "sol", 1)
