"""Research state that outlives the paper.

A white paper is a rendering of the evidence, not the evidence itself. When the
run finishes, the claims are the thing worth keeping: you can extend them, argue
with them, or write a second paper from them.

The record shape matches what the second brain already stores under
`loop_eng_2nd_brain/knowledge/research/`, so `research-ingest` can pull a run in
later with no conversion step. Three record types and one edge:

    SourceDocument   something that was actually retrieved, with its hash
    Claim            one assertion, with a truth_state
    Finding          a group of claims, linked by `asserts`

The important rule is arithmetic, not judgment. A claim is `corroborated` only
when two distinct source ids each pass `attributed()`, the check that the text
`metadata.fetch_record` retrieved for that source actually backs the claim.
Two URLs in one reply are not two attributed bindings until each is checked.
One attributed source is `single_source`, and the paper has to say so out
loud. That check is in `corroborate()`, and no model gets a vote on it. #471
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# The three truth states a claim can hold. There is no fourth, and none of them
# means "the model felt good about it".
PROPOSED = "proposed"
SINGLE_SOURCE = "single_source"
CORROBORATED = "corroborated"
CONTRADICTED = "contradicted"

TRUTH_STATES = (PROPOSED, SINGLE_SOURCE, CORROBORATED, CONTRADICTED)

# Two independent sources is the bar for corroborated. Not two queries against
# the same page, and not the same vendor twice.
CORROBORATION_MIN = 2

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
SLUG_STRIP = re.compile(r"[^a-z0-9]+")

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def slug(text: str, limit: int = 60) -> str:
    """A filesystem-safe, URL-safe name. Deterministic, so a rerun overwrites."""
    out = SLUG_STRIP.sub("-", text.lower()).strip("-")
    return out[:limit].rstrip("-") or "untitled"


def new_id() -> str:
    """A sortable 26-character id, the shape the second brain already uses.

    Time-ordered so a directory listing reads in capture order. The random tail
    comes from os.urandom rather than `random`, because two records created in
    the same millisecond must not collide.
    """
    stamp = int(time.time() * 1000)
    head = ""
    for _ in range(10):
        head = _CROCKFORD[stamp % 32] + head
        stamp //= 32
    tail = "".join(_CROCKFORD[byte % 32] for byte in os.urandom(16))
    return head + tail


def source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _yaml_scalar(value) -> str:
    """Quote only what needs quoting. This writes YAML, it does not parse it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or re.search(r'[:#\[\]{}",\n]|^\s|\s$', text):
        return json.dumps(text)
    return text


def render_front_matter(fields: dict) -> str:
    """Write front matter the second brain can read back.

    `links` is the only nested key, and it is always a list of
    `{rel, target}` maps. Keeping the writer this narrow is deliberate: a
    general YAML emitter here would be a second, worse yaml library.
    """
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if key == "links":
            if not value:
                continue
            lines.append("links:")
            for link in value:
                lines.append(f"  - rel: {_yaml_scalar(link['rel'])}")
                lines.append(f"    target: {_yaml_scalar(link['target'])}")
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            lines.append(f"{key}: [{', '.join(_yaml_scalar(item) for item in value)}]")
            continue
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Read back what `render_front_matter` wrote. Round-trip, not general YAML."""
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    fields: dict = {}
    links: list[dict] = []
    pending: dict = {}
    for raw in match.group(1).split("\n"):
        if raw.startswith("    ") and pending is not None:
            key, _, value = raw.strip().partition(": ")
            pending[key] = _load_scalar(value)
            continue
        if raw.startswith("  - "):
            if pending:
                links.append(pending)
            key, _, value = raw[4:].partition(": ")
            pending = {key: _load_scalar(value)}
            continue
        if pending:
            links.append(pending)
            pending = {}
        if raw.strip() == "links:":
            continue
        key, sep, value = raw.partition(": ")
        if not sep:
            continue
        fields[key.strip()] = _load_scalar(value)
    if pending:
        links.append(pending)
    if links:
        fields["links"] = links
    return fields, match.group(2)


def _load_scalar(value: str):  # noqa: PLR0911  (one return per YAML scalar type)
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_load_scalar(part) for part in _split_list(inner)] if inner else []
    if value.startswith('"'):
        return json.loads(value)
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _split_list(inner: str) -> list[str]:
    parts, depth, current = [], 0, ""
    quoted = False
    for char in inner:
        if char == '"':
            quoted = not quoted
        if char == "," and not quoted and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current)
    return parts


@dataclass
class SourceDocument:
    """Something the loop actually retrieved. The hash proves it did."""

    title: str
    url: str
    subject: str
    vendor: str = ""
    body: str = ""
    id: str = ""
    captured_at: str = ""
    # The corpus key this source was cross-referenced from, when the locator
    # found the public page for something a second brain already held. Empty
    # for everything the run retrieved off the web. `record_findings` reads it
    # to admit a host no allowlist ever named, so it has to survive a resume.
    located_from: str = ""
    # First-retrieval position. Persisted because reference numbers come from
    # it, and a resumed run that reloads in a different order renumbers the
    # whole bibliography. The ledger assigns it.
    seq: int = 0
    # What `metadata.fetch_record` found on the actual page, never the model's
    # word. `title` above is already replaced with the fetched title when one
    # came back; these three are additional fields the model never supplied.
    authors: list[str] = field(default_factory=list)
    year: str = ""
    venue: str = ""
    # `title_mismatch: ...` or a fetch-failure message. The writer never reads
    # a SourceDocument, only `stages.claim_brief`'s numbers, so this is safe
    # to carry all the way to the report without leaking into the paper. #470
    note: str = ""
    # The abstract or page text `metadata.fetch_record` retrieved, independent
    # of anything the model said. `attributed()` searches this text, never
    # `body`, for its needle: `body` is the researcher's own quote for this
    # binding, the needle itself, and searching a source's own text for
    # its own text proves nothing. Empty means the fetch failed or returned
    # no text; a claim bound to this source then keeps its binding
    # unattributed rather than dropped. #471
    text: str = ""
    # What kind of source this is, from `source_policy.tier_for()` reading
    # `metadata.fetch_record`'s raw publication-type fields. No model. `""`
    # for a source retrieved before this ticket, or one nothing here could
    # classify past `tier_for`'s own `other` default. #473
    tier: str = ""

    def __post_init__(self) -> None:
        self.id = self.id or f"source.{slug(self.subject, 40)}.{new_id()}"
        self.captured_at = self.captured_at or date.today().isoformat()

    def to_markdown(self) -> str:
        head = render_front_matter(
            {
                "type": "SourceDocument",
                "id": self.id,
                "title": self.title,
                "status": "draft",
                "verified": False,
                "generated": True,
                "vendor": self.vendor,
                "source_kind": "deep_research",
                "source_hash": source_hash(self.body or self.url),
                "url": self.url,
                "located_from": self.located_from or None,
                "captured_at": self.captured_at,
                "seq": self.seq,
                "authors": self.authors,
                "year": self.year or None,
                "venue": self.venue or None,
                "note": self.note or None,
                "fetched_text": self.text or None,
                "tier": self.tier or None,
            }
        )
        return f"{head}\n\n{self.body or self.url}\n"


@dataclass
class Claim:
    """One assertion, with the sources that back it and nothing else."""

    text: str
    subject: str
    source_ids: list[str] = field(default_factory=list)
    truth_state: str = PROPOSED
    confidence: float = 0.5
    important: bool = False
    note: str = ""
    # Whether a verifier took a second, independent look. Distinct from the
    # truth state, which only counts sources. Two URLs inside one search answer
    # are two sources and one look, and a reader is entitled to know which
    # claims nobody went back and checked.
    cross_checked: bool = False
    # The subset of `source_ids` that passed `attributed()`, or that a real
    # independent verifier turn confirmed directly (`apply_verification`'s
    # `agreed` branch). `corroborate()` counts this, not `source_ids`, which
    # is the fix for #471: two URLs in one researcher reply are two sources
    # and zero attributed bindings until each is actually checked against the
    # text `metadata.fetch_record` retrieved for it.
    attributed_source_ids: list[str] = field(default_factory=list)
    # Population, design, and sample size, when the researcher reported one.
    # Unused until #478's study table; carried here only so it survives a
    # ledger round trip. #471
    study: dict = field(default_factory=dict)
    # Whether this claim rests only on a review, a preprint, or a
    # compilation, with no primary study to follow to. #473. A dedicated
    # field, not `note`: `apply_verification` overwrites `note` on
    # `disagreed` and `not_found`, and the verifier runs right after the
    # follow pass, so a text marker in `note` was gone before the writer
    # ever saw it. `apply_verification` never touches this field.
    secondary: bool = False
    id: str = ""
    as_of: str = ""

    def __post_init__(self) -> None:
        self.id = self.id or f"claim.{slug(self.subject, 40)}.{new_id()}"
        self.as_of = self.as_of or date.today().isoformat()

    @property
    def cited(self) -> bool:
        return bool(self.source_ids)

    @property
    def usable(self) -> bool:
        """May this claim reach the paper at all?

        A contradicted claim may not. An uncited one may not. A single-source
        claim may, and `paper_check` makes sure it carries its caveat.
        """
        return self.cited and self.truth_state != CONTRADICTED

    def to_markdown(self) -> str:
        head = render_front_matter(
            {
                "type": "Claim",
                "id": self.id,
                "title": self.text[:80],
                "status": "draft",
                "verified": self.truth_state == CORROBORATED,
                "generated": True,
                "confidence": round(self.confidence, 2),
                "as_of": self.as_of,
                "truth_state": self.truth_state,
                "important": self.important,
                "cross_checked": self.cross_checked,
                "attributed_source_ids": self.attributed_source_ids,
                "secondary": self.secondary,
                "study": json.dumps(self.study, sort_keys=True) if self.study else None,
                "links": [{"rel": "sourced_from", "target": sid} for sid in self.source_ids],
            }
        )
        body = self.text if not self.note else f"{self.text}\n\n> {self.note}"
        return f"{head}\n\n{body}\n"


@dataclass
class Finding:
    """A group of claims that answer one research question."""

    question: str
    subject: str
    claim_ids: list[str] = field(default_factory=list)
    summary: str = ""
    # A claim `record_findings` refused because its text was about the search,
    # not the topic: "no source was found", not a fact. Recorded here instead
    # of silently dropped, so a reader can see what this question still lacks
    # rather than a paper claiming the absence of evidence as evidence. #469
    gaps: list[str] = field(default_factory=list)
    id: str = ""

    def __post_init__(self) -> None:
        self.id = self.id or f"finding.{slug(self.subject, 40)}.{new_id()}"

    def to_markdown(self) -> str:
        head = render_front_matter(
            {
                "type": "Finding",
                "id": self.id,
                "title": self.question[:80],
                "status": "draft",
                "verified": False,
                "generated": True,
                "gaps": self.gaps,
                "links": [{"rel": "asserts", "target": cid} for cid in self.claim_ids],
            }
        )
        return f"{head}\n\n{self.summary or self.question}\n"


_NUMBER = re.compile(r"\d[\d,.]*\d|\d")


def _numbers(text: str) -> set[str]:
    return {token.replace(",", "") for token in _NUMBER.findall(text or "")}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def attributed(claim: Claim, source_text: str, *, quote: str = "") -> bool:
    """Does the text #470 fetched for a source actually back this claim?

    `quote` is the researcher's own excerpt for this specific binding
    (`SourceDocument.body`, set from that source's own entry in the
    researcher's reply), not a `"..."` substring pulled out of `claim.text`:
    a DA claim rarely carries an embedded quote, and the real one the
    researcher gave sat unused. That quote must appear in `source_text`, or
    every one of the claim's numbers must -- one shared number out of
    several is not enough: a source that only says "a 12 week study" does
    not back "creatine adds 1.2 kg over 12 weeks" merely because 12 appears
    in both. Neither a quote nor a number is not a failure: a purely
    qualitative claim carries nothing this cheap, model-free check can
    contradict, and dropping it here would be inventing evidence of a
    mismatch that was never checked. That claim's binding is only as good as
    whatever verified it elsewhere. #471
    """
    quote = (quote or "").strip()
    numbers = _numbers(claim.text)
    if not quote and not numbers:
        return True
    normalized_source = _normalize(source_text)
    if quote and _normalize(quote) in normalized_source:
        return True
    return bool(numbers) and numbers <= _numbers(source_text)


def corroborate(claim: Claim, *, contradicted: bool = False) -> Claim:
    """Set the truth state from attributed sources. No model call.

    Distinct *attributed* source ids, not raw source count. Two URLs a
    researcher lists in one reply are two sources and, until each is checked
    against the text `metadata.fetch_record` retrieved for it, zero attributed
    bindings. #471
    """
    attributed_now = set(claim.attributed_source_ids) & set(claim.source_ids)
    if contradicted:
        claim.truth_state = CONTRADICTED
    elif len(attributed_now) >= CORROBORATION_MIN:
        claim.truth_state = CORROBORATED
    elif claim.source_ids:
        claim.truth_state = SINGLE_SOURCE
    else:
        claim.truth_state = PROPOSED
    return claim


class Ledger:
    """Every record from one run, on disk under `evidence/`."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.sources: dict[str, SourceDocument] = {}
        self.claims: dict[str, Claim] = {}
        self.findings: dict[str, Finding] = {}
        self._by_url: dict[str, SourceDocument] = {}

    def add_source(self, source: SourceDocument) -> SourceDocument:
        """Record a source, or return the one already held for that URL.

        Deduplicating by URL is load bearing, not tidiness. Without it the same
        documentation page retrieved by two questions becomes two source ids,
        and a claim that cites both looks corroborated by two independent
        sources when it stands on one page. It also gives the same URL two
        reference numbers, so `[2]` and `[5]` point at the same thing.

        The first record wins. A later retrieval of the same URL may carry a
        better quote, but rewriting the body would change a hash another record
        already committed to.
        """
        existing = self._by_url.get(source.url)
        if existing is not None:
            return existing
        if not source.seq:
            source.seq = len(self.sources) + 1
        self.sources[source.id] = source
        if source.url:
            self._by_url[source.url] = source
        return source

    def source_for_url(self, url: str) -> SourceDocument | None:
        """The source already admitted for this URL, or `None`.

        `record_findings` checks this before fetching metadata, so a source
        cited by a second question in the same run does not pay for the fetch
        twice. `add_source` already dedupes on write; this is the read side.
        """
        return self._by_url.get(url)

    def add_claim(self, claim: Claim) -> Claim:
        self.claims[claim.id] = claim
        return claim

    def add_finding(self, finding: Finding) -> Finding:
        self.findings[finding.id] = finding
        return finding

    def claim(self, claim_id: str) -> Claim | None:
        return self.claims.get(claim_id)

    def urls_for(self, claim_id: str) -> list[str]:
        claim = self.claims.get(claim_id)
        if claim is None:
            return []
        return [self.sources[sid].url for sid in claim.source_ids if sid in self.sources]

    def important(self) -> list[Claim]:
        return [claim for claim in self.claims.values() if claim.important]

    def unchecked(self) -> list[Claim]:
        """Important claims no verifier looked at a second time."""
        return [claim for claim in self.important() if not claim.cross_checked]

    def unusable(self) -> list[Claim]:
        return [claim for claim in self.claims.values() if not claim.usable]

    def bibliography(self) -> list[SourceDocument]:
        """Every source at least one claim used, in first-retrieval order.

        A source nobody cited does not belong in the references. Listing it
        makes the paper look better researched than it is.

        The order is `self.sources` insertion order, not sorted by id. Two ids
        minted in the same millisecond sort by their random tail, so sorting
        would number the same bibliography differently on every run, and `[3]`
        would point somewhere new each time the paper was rebuilt.
        """
        used = {sid for claim in self.claims.values() for sid in claim.source_ids}
        return [src for sid, src in self.sources.items() if sid in used]

    def write(self) -> list[Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        written = []
        for record in (*self.sources.values(), *self.claims.values(), *self.findings.values()):
            path = self.root / f"{record.id}.md"
            path.write_text(record.to_markdown(), encoding="utf-8")
            written.append(path)
        return written

    def load(self) -> Ledger:
        """Read a previous run's evidence back, so a resume keeps its claims.

        Sources are re-sorted by `seq` at the end. The file listing is sorted by
        id, and two ids minted in the same millisecond sort by their random
        tail, so without this a resume renumbers the references.

        `record_findings` and `apply_verification` only ever write a url a
        reader can open (or one cross-referenced from the cabinet, still
        checked at that call site). A file here with anything else is
        hand-edited, not something this run wrote, and the bibliography must
        not print it.
        """
        if not self.root.is_dir():
            return self
        for path in sorted(self.root.glob("*.md")):
            fields, body = parse_front_matter(path.read_text(encoding="utf-8"))
            kind = fields.get("type")
            body = body.strip()
            if kind == "SourceDocument":
                url = fields.get("url", "")
                if not str(url).lower().startswith(("http://", "https://")):
                    raise RuntimeError(
                        f"{path} gives its source the url {url!r}. The ledger may "
                        "hold only public URLs. Repair the file or start a fresh "
                        "work directory."
                    )
                self.add_source(
                    SourceDocument(
                        title=fields.get("title", ""),
                        url=url,
                        subject="",
                        vendor=fields.get("vendor", ""),
                        body=body,
                        id=fields["id"],
                        captured_at=fields.get("captured_at", ""),
                        located_from=fields.get("located_from", ""),
                        seq=int(fields.get("seq", 0)),
                        authors=list(fields.get("authors") or []),
                        # `_load_scalar` reads a purely numeric front-matter value
                        # back as an int, the same as `seq` above. `year` is a
                        # string field, so put it back.
                        year=str(fields.get("year") or ""),
                        venue=fields.get("venue", "") or "",
                        note=fields.get("note", "") or "",
                        text=fields.get("fetched_text", "") or "",
                        tier=fields.get("tier", "") or "",
                    )
                )
            elif kind == "Claim":
                links = fields.get("links", [])
                self.add_claim(
                    Claim(
                        text=body.split("\n\n>")[0],
                        subject="",
                        source_ids=[ln["target"] for ln in links if ln["rel"] == "sourced_from"],
                        truth_state=fields.get("truth_state", PROPOSED),
                        confidence=float(fields.get("confidence", 0.5)),
                        important=bool(fields.get("important", False)),
                        cross_checked=bool(fields.get("cross_checked", False)),
                        attributed_source_ids=list(fields.get("attributed_source_ids") or []),
                        secondary=bool(fields.get("secondary", False)),
                        study=json.loads(fields["study"]) if fields.get("study") else {},
                        id=fields["id"],
                        as_of=fields.get("as_of", ""),
                    )
                )
            elif kind == "Finding":
                links = fields.get("links", [])
                self.add_finding(
                    Finding(
                        question=fields.get("title", ""),
                        subject="",
                        claim_ids=[ln["target"] for ln in links if ln["rel"] == "asserts"],
                        summary=body,
                        gaps=list(fields.get("gaps") or []),
                        id=fields["id"],
                    )
                )
        self.sources = dict(
            sorted(self.sources.items(), key=lambda item: (item[1].seq or 10**6, item[0]))
        )
        return self


def demo() -> None:  # noqa: PLR0915  (one assertion per rule, deliberately flat)
    """Assertions this module must never stop satisfying."""
    assert slug("SQLAlchemy: nullable DateTime!") == "sqlalchemy-nullable-datetime"
    assert new_id() != new_id()

    one = SourceDocument(title="Docs", url="https://a.example/1", subject="dt", vendor="sqlalchemy")
    two = SourceDocument(title="Spec", url="https://b.example/2", subject="dt", vendor="pep")

    claim = Claim(text="A nullable column stores NULL.", subject="dt", important=True)
    corroborate(claim)
    assert claim.truth_state == PROPOSED, "no source is not single source"
    assert not claim.usable, "an uncited claim never reaches the paper"

    claim.source_ids = [one.id]
    corroborate(claim)
    assert claim.truth_state == SINGLE_SOURCE
    assert claim.usable, "one source is usable, with a caveat"

    # The same source twice is still one source.
    claim.source_ids = [one.id, one.id]
    corroborate(claim)
    assert claim.truth_state == SINGLE_SOURCE, "asking one page twice is one source"

    # #471: two raw source ids are not two attributed bindings. A claim built
    # from two URLs in one search answer stays single-source until each
    # binding is actually checked.
    claim.source_ids = [one.id, two.id]
    corroborate(claim)
    assert claim.truth_state == SINGLE_SOURCE, "two urls in one reply is not corroboration"

    claim.attributed_source_ids = [one.id, two.id]
    corroborate(claim)
    assert claim.truth_state == CORROBORATED

    corroborate(claim, contradicted=True)
    assert claim.truth_state == CONTRADICTED
    assert not claim.usable, "a contradicted claim never reaches the paper"

    # Source count and a second look are different facts. Counting sources does
    # not make one, and a claim built from two URLs in a single search answer is
    # two sources and one look.
    corroborate(claim)
    assert claim.truth_state == CORROBORATED

    # attributed(): the researcher's own quote for this binding
    # (`SourceDocument.body`), never a `"..."` substring pulled out of
    # `claim.text`, is the needle. Missing from the source text loses the
    # check; found passes it; nothing to check passes by default. #471
    quoted = Claim(text="The paper reports a marked reduction in error rate.", subject="dt")
    assert not attributed(
        quoted, "The paper found no significant change.", quote="a marked reduction in error rate"
    )
    assert attributed(
        quoted, 'Results show "a marked reduction in error rate" overall.', quote="a marked reduction in error rate"
    )
    # Every one of the claim's numbers must appear, not just one: a source
    # that only says "a 12 week study" does not back "creatine adds 1.2 kg
    # over 12 weeks" merely because 12 appears in both. #471
    numeric = Claim(text="The cohort included 214 participants.", subject="dt")
    assert attributed(numeric, "Of the 214 participants enrolled, most completed the study.")
    assert not attributed(numeric, "The cohort included far fewer participants than planned.")
    dosage = Claim(text="Creatine adds 1.2 kg of lean mass over 12 weeks.", subject="dt")
    assert not attributed(dosage, "This was a 12 week study of resistance-trained adults.")
    assert attributed(dosage, "Over 12 weeks, creatine added 1.2 kg of lean mass on average.")
    plain = Claim(text="Creatine is widely studied.", subject="dt")
    assert attributed(plain, "This page is about something else entirely.")
    assert claim.cross_checked is False
    fields, _ = parse_front_matter(claim.to_markdown())
    assert fields["cross_checked"] is False
    claim.cross_checked = True
    fields, _ = parse_front_matter(claim.to_markdown())
    assert fields["cross_checked"] is True

    # Front matter round-trips, links included.
    corroborate(claim)
    fields, body = parse_front_matter(claim.to_markdown())
    assert fields["type"] == "Claim"
    assert fields["id"] == claim.id
    assert fields["truth_state"] == CORROBORATED
    assert fields["important"] is True
    assert [link["target"] for link in fields["links"]] == [one.id, two.id]
    assert body.strip().startswith("A nullable column")

    # The same URL twice is one source, with one reference number.
    ledger = Ledger("/nonexistent")
    again = SourceDocument(title="Docs, again", url=one.url, subject="dt")
    assert ledger.add_source(one) is one
    assert ledger.add_source(again) is one, "one URL is one source"
    assert len(ledger.sources) == 1
    assert ledger.source_for_url(one.url) is one
    assert ledger.source_for_url("https://never-added.example") is None

    # Metadata fields round-trip through the ledger, note included. #470
    meta = SourceDocument(
        title="Fetched Title",
        url="https://meta.example/paper",
        subject="dt",
        authors=["Jane Doe", "John Smith"],
        year="2021",
        venue="Journal of Things",
        note="title_mismatch: model said 'X'; the record says 'Fetched Title'",
    )
    fields, _ = parse_front_matter(meta.to_markdown())
    assert fields["authors"] == ["Jane Doe", "John Smith"], fields
    # A purely numeric front-matter value reads back as an int, same as `seq`.
    assert str(fields["year"]) == "2021", fields
    assert fields["venue"] == "Journal of Things", fields
    assert fields["note"].startswith("title_mismatch:"), fields
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        meta_ledger = Ledger(tmp)
        meta_ledger.add_source(meta)
        meta_ledger.write()
        reloaded = Ledger(tmp).load().source_for_url(meta.url)
        assert reloaded.authors == meta.authors, reloaded
        assert reloaded.year == meta.year, reloaded
        assert reloaded.venue == meta.venue, reloaded
        assert reloaded.note == meta.note, reloaded
        assert reloaded.text == "", reloaded

    # Fetched page text round-trips too, and a `study` object survives a
    # claim's round trip through the ledger, unused until #478. #471
    with tempfile.TemporaryDirectory() as tmp:
        texty = SourceDocument(
            title="A Study",
            url="https://text.example/paper",
            subject="dt",
            text="This trial enrolled 214 participants over 12 weeks.",
        )
        studied = Claim(
            text="The trial enrolled 214 participants.",
            subject="dt",
            source_ids=[texty.id],
            attributed_source_ids=[texty.id],
            study={"design": "RCT", "n": 214, "weeks": 12},
        )
        study_ledger = Ledger(tmp)
        study_ledger.add_source(texty)
        study_ledger.add_claim(studied)
        study_ledger.write()
        reloaded_ledger = Ledger(tmp).load()
        assert reloaded_ledger.source_for_url(texty.url).text == texty.text
        reloaded_claim = reloaded_ledger.claim(studied.id)
        assert reloaded_claim.study == studied.study, reloaded_claim.study
        assert reloaded_claim.attributed_source_ids == [texty.id]

    # A source nobody cited stays out of the bibliography.
    ledger.add_source(two)
    ledger.add_source(SourceDocument(title="Unused", url="https://c.example", subject="dt"))
    ledger.add_claim(claim)
    assert [src.id for src in ledger.bibliography()] == [one.id, two.id], (
        "the bibliography keeps retrieval order, so reference numbers are stable"
    )
    assert (one.seq, two.seq) == (1, 2), "the ledger numbers sources as it takes them"

    # That order survives a round trip through disk, or a resume renumbers.
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        ledger.root = Path(tmp)
        ledger.write()
        again = Ledger(tmp).load()
        assert [src.url for src in again.sources.values()] == [
            src.url for src in ledger.sources.values()
        ], "reloading must not reorder the bibliography"

    print("evidence: all demo assertions passed")


if __name__ == "__main__":
    demo()
