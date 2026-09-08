"""Reference metadata comes from the record, not the model. #470

A source's title, authors, year, and venue are what the page says, never what
the writer typed. `fetch_record(url, backend)` resolves:

    PubMed or PMC id   E-utilities `esummary`
    arXiv id           the arXiv API
    DOI                Crossref
    anything else      `citation_title`, `citation_author`, `citation_date`
                        meta tags, then `<title>`

One attempt, a 10 second timeout, no retry. A failed or timed-out fetch keeps
the model's title and writes a note; it never raises and never blocks the run.

The same fetch also keeps whatever abstract or summary the record carried:
for PubMed or PMC, a second call to efetch (`rettype=abstract`), since
esummary itself almost never carries one; for arXiv, its own summary field;
for a DOI, the Crossref abstract when present; else the page's meta
description or its first text block. Capped at `TEXT_CAP` characters. #471's
`attributed()` reads this text, never the model's own quote, to check a
claim against the source it names. A failed efetch keeps esummary's title,
authors, and year and notes the miss; it never drops what esummary already
gave.

The offline switch: when `backend` is the fixture backend (`backend.name ==
"fixture"`), this reads a recorded reply under `fixtures/metadata/` and never
touches the network. Every other backend resolves for real. No new CLI flag,
no new environment variable: the caller passes whatever backend the run
already holds (`Paper.backend`).

The fetch also keeps the record's own raw publication-type fields, never
interpreted here: PubMed and PMC's `pubtype` list (esummary), arXiv's
`category`, and Crossref's `type`. #473's `source_policy.tier_for()` reads
these to decide what kind of source this is, a review, a preprint, a
position stand, a primary trial, without a model turn. A page fetched
through `citation_title` meta tags carries none of these, so it tiers
`other` by default.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE / "fixtures" / "metadata"
TIMEOUT_S = 10.0
# A sensible size for an abstract or a page's opening text. Big enough to hold
# a real abstract, small enough that the ledger's front matter stays readable.
TEXT_CAP = 4000

_PUBMED = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)
# The old host (ncbi.nlm.nih.gov/pmc/articles/...) and the canonical one PMC
# moved to (pmc.ncbi.nlm.nih.gov/articles/...) both still resolve.
_PMC = re.compile(r"(?:ncbi\.nlm\.nih\.gov/pmc/articles|pmc\.ncbi\.nlm\.nih\.gov/articles)/pmc(\d+)", re.I)
_ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})", re.I)
_DOI = re.compile(r"doi\.org/(10\.[^\s?#]+)", re.I)


def _fixture_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return FIXTURE_DIR / f"{digest}.json"


def _is_fixture(backend) -> bool:
    return getattr(backend, "name", "") == "fixture"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def title_mismatch(model_title: str, fetched_title: str) -> bool:
    """More than a third of the two titles' combined tokens disagree."""
    model_tokens, fetched_tokens = _tokens(model_title), _tokens(fetched_title)
    universe = model_tokens | fetched_tokens
    if not universe:
        return False
    return len(model_tokens ^ fetched_tokens) / len(universe) > 1 / 3


def _get(url: str) -> bytes:
    import httpx  # noqa: PLC0415  lazy, already a dependency of research.py

    response = httpx.get(url, timeout=TIMEOUT_S, headers={"User-Agent": "sol3-research-da/1.0"})
    response.raise_for_status()
    return response.content


def _efetch_abstract(db: str, uid: str) -> str:
    """The plain-text abstract, from efetch, not the rare esummary field.

    `rettype=abstract&retmode=text` returns a formatted citation line, a
    blank line, the abstract itself, then a trailing `PMID:` (or similar)
    footer line, each block separated by a blank line. The citation and the
    footer are not the abstract; everything between them is.
    """
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db={db}&id={uid}&rettype=abstract&retmode=text"
    )
    text = _get(url).decode("utf-8", errors="replace")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) < 2:
        return " ".join(paragraphs[0].split()) if paragraphs else ""
    body = paragraphs[1:]
    if body[-1].lower().startswith(("pmid", "doi", "pmcid", "©")):
        body = body[:-1]
    return " ".join(" ".join(p.split()) for p in body)


def _from_pubmed(pubmed_id: str) -> dict:
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&id={pubmed_id}&retmode=json"
    )
    payload = json.loads(_get(url))
    result = (payload.get("result") or {}).get(pubmed_id) or {}
    authors = [a.get("name", "") for a in result.get("authors") or [] if a.get("name")]
    record = {
        "title": result.get("title") or "",
        "authors": authors,
        "year": str(result.get("pubdate") or "")[:4],
        "venue": result.get("fulljournalname") or result.get("source") or "",
        # esummary does not normally carry an abstract; efetch below usually
        # does. This is the fallback when efetch itself fails.
        "text": result.get("abstract") or "",
        # Raw, uninterpreted. #473's `source_policy.tier_for()` maps these
        # strings; `metadata.py` never decides what a "Practice Guideline" or
        # a "Randomized Controlled Trial" means.
        "pubtype": list(result.get("pubtype") or []),
    }
    try:
        abstract = _efetch_abstract("pubmed", pubmed_id)
        if abstract:
            record["text"] = abstract
    except Exception as exc:  # noqa: BLE001  the abstract is a bonus; esummary's fields still stand
        record["note"] = f"efetch abstract failed: {exc}"
    return record


def _from_pmc(pmc_id: str) -> dict:
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pmc&id={pmc_id}&retmode=json"
    )
    payload = json.loads(_get(url))
    result = (payload.get("result") or {}).get(pmc_id) or {}
    authors = [a.get("name", "") for a in result.get("authors") or [] if a.get("name")]
    record = {
        "title": result.get("title") or "",
        "authors": authors,
        "year": str(result.get("pubdate") or "")[:4],
        "venue": result.get("fulljournalname") or result.get("source") or "",
        "text": result.get("abstract") or "",
        "pubtype": list(result.get("pubtype") or []),
    }
    try:
        abstract = _efetch_abstract("pmc", pmc_id)
        if abstract:
            record["text"] = abstract
    except Exception as exc:  # noqa: BLE001  the abstract is a bonus; esummary's fields still stand
        record["note"] = f"efetch abstract failed: {exc}"
    return record


def _from_arxiv(arxiv_id: str) -> dict:
    payload = _get(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
    root = ElementTree.fromstring(payload)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        return {}
    title = " ".join((entry.findtext("a:title", default="", namespaces=ns) or "").split())
    authors = [
        " ".join((author.findtext("a:name", default="", namespaces=ns) or "").split())
        for author in entry.findall("a:author", ns)
    ]
    published = entry.findtext("a:published", default="", namespaces=ns) or ""
    summary = " ".join((entry.findtext("a:summary", default="", namespaces=ns) or "").split())
    category_el = entry.find("a:category", ns)
    category = (category_el.get("term") or "") if category_el is not None else ""
    return {
        "title": title,
        "authors": [a for a in authors if a],
        "year": published[:4],
        "venue": "arXiv",
        "text": summary,
        "category": category,
    }


def _from_crossref(doi: str) -> dict:
    payload = json.loads(_get(f"https://api.crossref.org/works/{doi}"))
    message = payload.get("message") or {}
    titles = message.get("title") or []
    authors = [
        " ".join(part for part in (a.get("given"), a.get("family")) if part)
        for a in message.get("author") or []
    ]
    year = ""
    for key in ("published-print", "published-online", "issued"):
        parts = (message.get(key) or {}).get("date-parts") or []
        if parts and parts[0]:
            year = str(parts[0][0])
            break
    venue = (message.get("container-title") or [""])[0]
    abstract = re.sub(r"<[^>]+>", " ", message.get("abstract") or "")
    return {
        "title": titles[0] if titles else "",
        "authors": [a for a in authors if a],
        "year": year,
        "venue": venue,
        # Crossref's abstract, when a publisher supplied one, arrives as
        # JATS XML. Strip tags rather than parse a schema nobody asked for.
        "text": " ".join(abstract.split()),
        "crossref_type": str(message.get("type") or ""),
    }


def _from_page(url: str) -> dict:
    html = _get(url).decode("utf-8", errors="replace")

    def meta_all(name: str) -> list[str]:
        pattern = re.compile(
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']', re.I
        )
        return [m.strip() for m in pattern.findall(html) if m.strip()]

    titles = meta_all("citation_title")
    authors = meta_all("citation_author")
    dates = meta_all("citation_date")
    title = titles[0] if titles else ""
    if not title:
        found = re.search(r"<title[^>]*>([^<]*)</title>", html, re.I)
        title = found.group(1).strip() if found else ""
    description = meta_all("description") or meta_all("og:description")
    text = description[0] if description else ""
    if not text:
        # No description meta tag. The first paragraph is a weak substitute
        # for an abstract, but a weak substitute beats an empty one.
        found = re.search(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", found.group(1)) if found else ""
    return {
        "title": title,
        "authors": authors,
        "year": dates[0][:4] if dates else "",
        "venue": "",
        "text": " ".join(text.split()),
    }


def _resolve_live(url: str) -> dict:
    match = _PUBMED.search(url)
    if match:
        return _from_pubmed(match.group(1))
    match = _PMC.search(url)
    if match:
        return _from_pmc(match.group(1))
    match = _ARXIV.search(url)
    if match:
        return _from_arxiv(match.group(1))
    match = _DOI.search(url)
    if match:
        return _from_crossref(match.group(1))
    return _from_page(url)


def fetch_record(url: str, backend, *, model_title: str = "") -> dict:
    """Title, authors, year, and venue for one source url.

    `backend` is the same object the research stage already holds
    (`Paper.backend`). The fixture backend never reaches the network: it
    reads `fixtures/metadata/<sha1-of-url>.json`, or reports the miss. Any
    other backend resolves for real, one attempt, 10 seconds, no retry.

    Returns `{"title", "authors", "year", "venue", "note", "text", "pubtype",
    "category", "crossref_type"}`. `title` is the fetched title, or
    `model_title` when nothing was fetched. `text` is the abstract or page
    text the record carried, capped at `TEXT_CAP` characters, or empty when
    none was found; `attributed()` in `evidence.py` reads it. `pubtype`,
    `category`, and `crossref_type` are the record's own raw
    publication-type fields, empty or `[]` when the source was not resolved
    through that path; #473's `source_policy.tier_for()` is the only thing
    that interprets them. `note` carries a `title_mismatch: ...` message
    when a fetched title disagrees with `model_title` by more than a third
    of their tokens, or a fetch-failure message when the record could not be
    resolved. Never raises.

    Only an `http://` or `https://` url is ever fetched. A `file://` url read
    the caller's disk instead of a page; the scheme is checked here too, so no
    caller can bypass it by skipping its own guard.
    """
    record = {
        "title": model_title,
        "authors": [],
        "year": "",
        "venue": "",
        "note": "",
        "text": "",
        "pubtype": [],
        "category": "",
        "crossref_type": "",
    }
    if not url or not url.lower().startswith(("http://", "https://")):
        if url:
            record["note"] = f"metadata fetch: not an http(s) url: {url}"
        return record
    try:
        if _is_fixture(backend):
            path = _fixture_path(url)
            if not path.exists():
                record["note"] = f"metadata fetch: no recorded reply for {url}"
                return record
            fetched = json.loads(path.read_text(encoding="utf-8"))
        else:
            fetched = _resolve_live(url)
    except Exception as exc:  # noqa: BLE001  any network, parse, or http error keeps the model's title
        record["note"] = f"metadata fetch failed: {exc}"
        return record
    fetched_title = str((fetched or {}).get("title") or "").strip()
    record["authors"] = list((fetched or {}).get("authors") or [])
    record["year"] = str((fetched or {}).get("year") or "")
    record["venue"] = str((fetched or {}).get("venue") or "")
    record["text"] = str((fetched or {}).get("text") or "").strip()[:TEXT_CAP]
    record["pubtype"] = list((fetched or {}).get("pubtype") or [])
    record["category"] = str((fetched or {}).get("category") or "")
    record["crossref_type"] = str((fetched or {}).get("crossref_type") or "")
    if (fetched or {}).get("note"):
        # A partial failure below the title, e.g. efetch failing after
        # esummary succeeded. The record's own fields still stand.
        record["note"] = str(fetched["note"])
    if fetched_title:
        record["title"] = fetched_title
        if model_title and title_mismatch(model_title, fetched_title):
            record["note"] = (
                f"title_mismatch: model said {model_title!r}; the record says {fetched_title!r}"
            )
    return record


def demo() -> None:
    class Fixture:
        name = "fixture"

    class Live:
        name = "perplexity"

    # No recorded reply: the model's title survives, and a note explains why.
    record = fetch_record("https://example.invalid/nothing-recorded", Fixture(), model_title="Kept")
    assert record["title"] == "Kept", record
    assert "no recorded reply" in record["note"], record

    # A timeout on the live path keeps the model's title too, and never raises.
    def _boom(_url: str) -> bytes:
        raise TimeoutError("timed out")

    original = globals()["_get"]
    globals()["_get"] = _boom
    try:
        record = fetch_record("https://docs.example.com/page", Live(), model_title="Original Title")
        assert record["title"] == "Original Title", record
        assert "metadata fetch failed" in record["note"], record
    finally:
        globals()["_get"] = original

    # No url, no crash.
    assert fetch_record("", Fixture())["title"] == ""

    # Text is capped, never grown past TEXT_CAP. #471
    def _long(_url: str) -> bytes:
        long_description = "x" * (TEXT_CAP * 2)
        return (
            f'<html><head><meta name="description" content="{long_description}">'
            "</head><body></body></html>"
        ).encode()

    globals()["_get"] = _long
    try:
        record = fetch_record("https://docs.example.com/long", Live())
        assert len(record["text"]) == TEXT_CAP, len(record["text"])
    finally:
        globals()["_get"] = original

    # The page's meta description is the text, when there is one.
    def _described(_url: str) -> bytes:
        return (
            b'<html><head><meta name="description" content="A page about creatine.">'
            b"</head><body></body></html>"
        )

    globals()["_get"] = _described
    try:
        record = fetch_record("https://docs.example.com/described", Live())
        assert record["text"] == "A page about creatine.", record
    finally:
        globals()["_get"] = original

    # A close title is not a mismatch; a distant one is.
    assert not title_mismatch("A Study of Creatine and Muscle Loss", "A Study of Creatine and Muscle Loss")
    assert title_mismatch(
        "The Interplay Between Physical Activity, Protein Consumption, and Energy Balance",
        "The Interplay Between Physical Activity, Protein Consumption, and Sleep Quality in "
        "Muscle Protein Synthesis",
    )
    print("metadata: ok")


if __name__ == "__main__":
    demo()
