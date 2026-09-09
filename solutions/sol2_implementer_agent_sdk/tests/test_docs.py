"""C1 (#442 #428). Docs match the code that shipped.

Four checks, each one a fact a doc could get stale about without any
Python test noticing:

1. The two operator docs name the four post-A9 flags, state.json, and the
   three exit codes, and neither names a CLI as a doer.
2. The module docstring names `task run --`, the task both Taskfiles
   actually expose, not the `task loop:implementer` a folder rename left
   behind.
3. FEATURE-MAP Module 2 rows never name a flag `implementer.py` does not
   accept. Parses `--help`, not the argparse source, so a spelling drift
   would fail this test even if nobody touched the parser.
4. No doc this folder owns, and no session-2 slide note, holds an em dash.
   The house style forbids the character everywhere.

No SDK, no key, no network, no clone.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parents[1]
REPO_ROOT = FOLDER.parents[1]

FLAG_RE = re.compile(r"--[a-z][a-z-]*")


def _help_text() -> str:
    proc = subprocess.run(
        [sys.executable, "implementer.py", "--help"],
        cwd=FOLDER,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def test_how_to_run_and_spec_name_the_shipped_flags_and_no_cli_doer():
    help_text = _help_text()
    for name in ("--resume", "--cleanup", "--planner", "--doer"):
        assert name in help_text, f"implementer.py --help dropped {name}"

    for doc in ("HOW_TO_RUN.md", "SPEC.md"):
        text = (FOLDER / doc).read_text(encoding="utf-8")
        for name in ("--resume", "--cleanup", "--planner"):
            assert name in text, f"{doc} does not name {name}"
        assert "state.json" in text, f"{doc} does not name state.json"
        for code in ("`0`", "`2`", "`1`"):
            assert code in text, f"{doc} does not name exit code {code}"
        # The dropped CLI backend class name itself is covered by
        # test_implementer.py::test_no_source_file_in_this_port_names_clibackend,
        # which greps this whole folder including this doc.
        for cli in ("--doer claude", "--doer codex", "--doer grok", "--doer opencode"):
            assert cli not in text, f"{doc} still names the dropped CLI doer {cli!r}"


def test_module_docstring_names_task_run_not_task_loop_implementer():
    text = (FOLDER / "implementer.py").read_text(encoding="utf-8")
    docstring = text.split('"""', 2)[1]
    assert "task run --" in docstring
    assert "task loop:implementer" not in docstring


def test_feature_map_module_2_rows_name_only_flags_implementer_accepts():
    feature_map = REPO_ROOT / "slides" / "FEATURE-MAP.md"
    if not feature_map.is_file():
        pytest.skip("this check only runs inside the seminar repo checkout")

    help_text = _help_text()
    module_2_flags: set[str] = set()
    for line in feature_map.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3 or cells[2] != "2":
            continue
        module_2_flags.update(FLAG_RE.findall(line))

    missing = sorted(flag for flag in module_2_flags if flag not in help_text)
    assert not missing, f"FEATURE-MAP Module 2 names flags implementer.py does not accept: {missing}"


def test_no_em_dash_in_this_folders_docs_or_session_2_notes():
    em_dash = "\u2014"
    offenders = []
    for doc in FOLDER.glob("*.md"):
        if em_dash in doc.read_text(encoding="utf-8"):
            offenders.append(str(doc))

    notes = REPO_ROOT / "slides" / "session-2-harness-engineering" / "notes.md"
    if notes.is_file() and em_dash in notes.read_text(encoding="utf-8"):
        offenders.append(str(notes))

    assert not offenders, f"em dash found in: {offenders}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
