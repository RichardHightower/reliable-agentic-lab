"""One source-number registry for a whole run.

`_claims_for_writer` numbered claims 1..N inside each section, restarting at 1
every time, and `paper._numbered` renumbered globally by URL at assembly. The
section text kept its local numbers, so section two wrote `[1]` meaning its
own first source while the bibliography's `[1]` was section one's. Every
deterministic row passed: `cited` saw a marker, `grounded` saw a number that
matched a local `number` field, and nothing compared the two passes.

This port researches section by section, so it learns its sources as it goes.
Rebuilding a numbered bibliography at the end recreates the same bug from the
other side. The registry is therefore append-only: a source keeps the number
it was first given, for the life of the run and across a resume.

The Deep Agents port assigns its numbers before the writer sees a claim
(`stages.py:559`). This is that idea, shaped for a loop that discovers sources
late. Copied, not imported, per `CLAUDE.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

FILE = "citations.json"


def _path(work_dir) -> Path:
    return Path(work_dir) / ".harness" / FILE


def load(work_dir) -> dict[str, int]:
    """The url-to-number map this run has already committed to."""
    path = _path(work_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A registry that cannot be read is not a registry that may be
        # rebuilt. Renumbering silently changes what a written section cites.
        raise RuntimeError(
            f"{path} is unreadable. Every section already written cites numbers "
            "from it. Repair the file or start a fresh work directory."
        ) from None
    return {str(url): int(number) for url, number in (payload.get("sources") or {}).items()}


def register(work_dir, urls) -> dict[str, int]:
    """Give every url a number, reusing the one it already has.

    Append-only by construction: `max` of the numbers in hand, plus one, for
    each url the registry has not seen. A url already numbered keeps its
    number, whatever order this section met it in.
    """
    known = load(work_dir)
    next_number = max(known.values(), default=0) + 1
    for url in urls:
        url = str(url or "")
        if not url or url in known:
            continue
        known[url] = next_number
        next_number += 1
    path = _path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"sources": known}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return known


def bibliography(work_dir) -> list[dict]:
    """The reference list, in number order. Empty when nothing was registered."""
    known = load(work_dir)
    return [
        {"url": url, "number": number}
        for url, number in sorted(known.items(), key=lambda item: item[1])
    ]


def demo() -> None:
    import tempfile  # noqa: PLC0415

    work = Path(tempfile.mkdtemp())
    first = register(work, ["https://a.invalid", "https://b.invalid"])
    assert first == {"https://a.invalid": 1, "https://b.invalid": 2}, first
    # Section two meets them in the other order and finds one more.
    second = register(work, ["https://b.invalid", "https://c.invalid", "https://a.invalid"])
    assert second["https://a.invalid"] == 1, second
    assert second["https://b.invalid"] == 2, second
    assert second["https://c.invalid"] == 3, second
    # A resume reads the same map off disk.
    assert load(work) == second
    assert [row["number"] for row in bibliography(work)] == [1, 2, 3]
    print("citations: ok")


if __name__ == "__main__":
    demo()
