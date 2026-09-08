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
    """The url-to-number map this run has already committed to.

    Every key must be a url a reader can open, the same rule `register` holds
    a new one to, checked again here because a saved file can be hand-edited.
    """
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
    raw = payload.get("sources") or {}
    out: dict[str, int] = {}
    for url, number in raw.items():
        # `register` never writes anything else, so a key here that is not a
        # url a reader can open is a hand-edited file, not a run's own history.
        if not str(url).lower().startswith(("http://", "https://")):
            raise RuntimeError(
                f"{path} gives {url!r} a citation number. The registry may hold "
                "only public URLs. Repair the file or start a fresh work "
                "directory."
            )
        # A bool is an int in Python, and a float coerces without complaint.
        # Either one in this file means the map was written by something other
        # than `register`, and a wrong number is worse than a missing one.
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise RuntimeError(
                f"{path} gives {url!r} the number {number!r}. A citation number "
                "is a positive integer. Repair the file or start a fresh work "
                "directory."
            )
        out[str(url)] = number
    if len(set(out.values())) != len(out):
        raise RuntimeError(
            f"{path} gives one number to two sources. Every section already "
            "written cites from it. Repair the file or start a fresh run."
        )
    return out


def register(work_dir, urls) -> dict[str, int]:
    """Give every url a number, reusing the one it already has.

    Append-only by construction: `max` of the numbers in hand, plus one, for
    each url the registry has not seen. A url already numbered keeps its
    number, whatever order this section met it in.

    A number here is a promise that the paper will print the url beside it, so
    only something a reader can open may take one. `corpus:knowledge:claim.x`
    took number 1 in run 21 and was published as a bibliography entry. The
    locator now either finds the public copy or drops the finding, so a
    non-http url arriving here is a hole in that pass, not a citation.
    """
    known = load(work_dir)
    next_number = max(known.values(), default=0) + 1
    for url in urls:
        url = str(url or "")
        if not url:
            continue
        if not url.lower().startswith(("http://", "https://")):
            raise RuntimeError(
                f"{url!r} is not a url a reader can open, so it may not take a "
                "citation number. The locator should have found its public copy "
                "or dropped the finding before the section reached the writer."
            )
        if url in known:
            continue
        known[url] = next_number
        next_number += 1
    path = _path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic. A half-written registry on a kill is a run whose written sections
    # cite numbers the file no longer agrees with.
    temp = path.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps({"sources": known}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temp.replace(path)
    return known


def bibliography(work_dir) -> list[dict]:
    """The reference list, in number order. Empty when nothing was registered."""
    known = load(work_dir)
    return [
        {"url": url, "number": number}
        for url, number in sorted(known.items(), key=lambda item: item[1])
    ]


def render_reference(ref: dict) -> str:
    """One reference line: "Authors (year). Title. Venue. URL."

    Every field is optional and falls back field by field, down to the bare
    URL when nothing else came back. `ref` is the dict `paper._numbered`
    builds, carrying whatever `metadata.fetch_record` found. #470

    `paper.assemble` does not call this yet; it still writes
    `f"{ref['number']}. {ref['url']}"` at the seam P3 will convert. This
    function is complete now so E2 never has to touch `assemble` to land it.
    """
    url = str(ref.get("url") or "").strip()
    authors = [str(a).strip() for a in (ref.get("authors") or []) if str(a).strip()]
    year = str(ref.get("year") or "").strip()
    title = str(ref.get("title") or "").strip()
    venue = str(ref.get("venue") or "").strip()

    lead = ", ".join(authors)
    if year:
        lead = f"{lead} ({year})" if lead else f"({year})"

    parts = [part for part in (lead, title, venue) if part]
    if not parts:
        return url
    text = ". ".join(parts)
    if not text.endswith("."):
        text += "."
    return f"{text} {url}" if url else text


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

    # render_reference falls back field by field to the bare URL.
    assert render_reference({"url": "https://a.invalid"}) == "https://a.invalid"
    assert render_reference({"url": "https://a.invalid", "title": "A Study"}) == (
        "A Study. https://a.invalid"
    )
    full = render_reference(
        {
            "url": "https://a.invalid",
            "title": "A Study",
            "authors": ["Jane Doe", "John Smith"],
            "year": "2020",
            "venue": "Journal of Things",
        }
    )
    assert full == "Jane Doe, John Smith (2020). A Study. Journal of Things. https://a.invalid", full
    print("citations: ok")


if __name__ == "__main__":
    demo()
