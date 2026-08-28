"""Guard: the shared loops/ engine stays gone.

This is a five-hour seminar. A shared loop library is how the last design
leaked. Duplicate code into labs/ and solutions/ instead.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Historical plans, this test, and CLAUDE.md may mention the name. Nothing else
# may import the package or keep the directory.
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".work", "docs"}


def test_loops_directory_is_gone() -> None:
    assert not (ROOT / "loops").exists(), (
        "loops/ is back. Delete it. Copy any needed file into the lab or "
        "solution folder that uses it. See CLAUDE.md."
    )


def test_no_from_loops_imports() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".yml", ".md"}:
            continue
        if SKIP_DIR_NAMES & set(path.parts):
            continue
        if path.name in {"CLAUDE.md", "AGENTS.md"}:
            continue
        if path.name == "test_no_loops_library.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("from loops") or stripped.startswith("import loops"):
                hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
            if "python -m loops" in line:
                hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
    assert hits == [], "shared loops engine leaked:\n" + "\n".join(hits)
