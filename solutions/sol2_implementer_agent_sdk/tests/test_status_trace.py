"""#444. A checked-in T001 live trace names the doer, gate, and tests-written flag.

Optional live traces for `--doer sdk` and `--doer deep` land under
`docs/status/` at the repo root, one file per doer. This is a revert test:
strip the doer, gate, or tests-written line from a checked-in trace and this
fails. No trace checked in yet is not a failure; the ticket says absence of
traces does not block merge.

No SDK, no key, no network, no clone.
"""

from __future__ import annotations

from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO_ROOT = FOLDER.parents[1]
STATUS_DIR = REPO_ROOT / "docs" / "status"

REQUIRED_LINES = ("Doer:", "Gate:", "Tests written in code phase:")


def test_live_t001_trace_names_doer_gate_and_tests_written_flag():
    traces = sorted(STATUS_DIR.glob("*-sol2-t001-live-*.md"))
    if not traces:
        return  # optional trace, #444. Absence does not fail the build.
    for trace in traces:
        text = trace.read_text(encoding="utf-8")
        for line in REQUIRED_LINES:
            assert line in text, f"{trace.name} is missing {line!r}"
