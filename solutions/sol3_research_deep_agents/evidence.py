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
when two distinct source ids support it. One source is `single_source`, and the
paper has to say so out loud. That check is in `corroborate()`, it is four lines,
and no model gets a vote on it.
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
    # First-retrieval position. Persisted because reference numbers come from
    # it, and a resumed run that reloads in a different order renumbers the
    # whole bibliography. The ledger assigns it.
    seq: int = 0

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
                "captured_at": self.captured_at,
                "seq": self.seq,
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
                "links": [{"rel": "asserts", "target": cid} for cid in self.claim_ids],
            }
        )
        return f"{head}\n\n{self.summary or self.question}\n"


def corroborate(claim: Claim, *, contradicted: bool = False) -> Claim:
    """Set the truth state from the source count. No model call.

    Distinct source ids, not source count. Asking the same page twice is one
    source, and a loop that cannot tell the difference will report every claim
    as corroborated by lunchtime.
    """
    if contradicted:
        claim.truth_state = CONTRADICTED
    elif len(set(claim.source_ids)) >= CORROBORATION_MIN:
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
        """
        if not self.root.is_dir():
            return self
        for path in sorted(self.root.glob("*.md")):
            fields, body = parse_front_matter(path.read_text(encoding="utf-8"))
            kind = fields.get("type")
            body = body.strip()
            if kind == "SourceDocument":
                self.add_source(
                    SourceDocument(
                        title=fields.get("title", ""),
                        url=fields.get("url", ""),
                        subject="",
                        vendor=fields.get("vendor", ""),
                        body=body,
                        id=fields["id"],
                        captured_at=fields.get("captured_at", ""),
                        seq=int(fields.get("seq", 0)),
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
                        id=fields["id"],
                    )
                )
        self.sources = dict(
            sorted(self.sources.items(), key=lambda item: (item[1].seq or 10**6, item[0]))
        )
        return self


def demo() -> None:
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

    claim.source_ids = [one.id, two.id]
    corroborate(claim)
    assert claim.truth_state == CORROBORATED

    corroborate(claim, contradicted=True)
    assert claim.truth_state == CONTRADICTED
    assert not claim.usable, "a contradicted claim never reaches the paper"

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
