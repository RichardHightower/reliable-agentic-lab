"""Read a second brain as a research corpus.

Pure Python. No `rg`, no PyYAML, no SDK. The CI runner and `task test` both
exercise this module on a machine with none of those.

    search(query, roots, subjects=None, limit=20) -> list[Hit]
    pack(topic, roots, dest, limit=40) -> dict
    resolve(key, roots) -> Hit | None

A root is a directory that holds `research/claims`, `research/evidence`,
`research/sources`, and `research/source-assets`. Claims may sit at
`claims/claim.<id>.md` or be sharded as `claims/<subject>/claim.<id>.md`.
A missing root is a note, not an error: an attendee will not have a brain.

The researcher and the verifier hold `corpus_search`. That tool calls
`search` and returns text. It holds no write path. A loop that can edit the
brain can launder its own output into everyone's prior knowledge.

    python3 corpus.py --demo
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
FIXTURE_BRAIN = FOLDER / "tests" / "fixtures" / "brain"
BRAIN_DIR_NAME = "loop_eng_2nd_brain"
DEFAULT_BRAIN = FOLDER.parents[2] / BRAIN_DIR_NAME / "knowledge"

STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}

# Distinct source hashes behind a claim. Copied from rkc_validate.derive_epistemic
# rather than imported: this folder is standalone.
EPISTEMIC = (
    (2, "corroborated"),
    (1, "source_supported"),
    (0, "unsupported"),
)


@dataclass
class Locator:
    asset_path: str = ""
    start_line: int | None = None
    end_line: int | None = None
    variant: str = ""


@dataclass
class Hit:
    key: str
    claim: str
    quote: str
    locator: Locator = field(default_factory=Locator)
    source_title: str = ""
    vendor: str = ""
    source_kind: str = ""
    origin_path: str = ""
    captured_at: str = ""
    subject: str = ""
    confidence: float = 0.0
    as_of: str = ""
    epistemic: str = "unsupported"
    claim_id: str = ""
    root_name: str = ""
    score: int = 0

    def as_dict(self) -> dict:
        payload = asdict(self)
        return payload


def derive_epistemic(source_hashes: list[str]) -> str:
    n = len({h for h in source_hashes if h})
    for threshold, label in EPISTEMIC:
        if n >= threshold:
            return label
    return "unsupported"


def terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (query or "").lower())
    return [w for w in words if w not in STOP and len(w) > 1]


def parse_front_matter(text: str) -> tuple[dict, str]:
    """A small YAML subset: scalars, one nested map, and a list of maps.

    Covers the shapes `rkc.write_node` emits and nothing else. A colon in a
    quoted title is a string, not a new key.
    """
    if not text.startswith("---"):
        return {}, text
    rest = text[3:].lstrip("\n")
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    raw = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    data: dict = {}
    current: dict | None = None
    current_key = ""
    current_list: list | None = None
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") and current_list is not None:
            current = {}
            current_list.append(current)
            item = line[4:]
            key, _, value = item.partition(":")
            if _:
                current[key.strip()] = _scalar(value)
            continue
        if line.startswith("    ") and current is not None:
            key, _, value = line.strip().partition(":")
            if _:
                current[key.strip()] = _scalar(value)
            continue
        if line.startswith("  ") and current_key and current_list is None:
            nested = data.setdefault(current_key, {})
            if not isinstance(nested, dict):
                nested = {}
                data[current_key] = nested
            key, _, value = line.strip().partition(":")
            if _:
                nested[key.strip()] = _scalar(value)
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        current = None
        current_list = None
        current_key = key
        if value == "":
            if key == "links":
                current_list = []
                data[key] = current_list
            else:
                data.setdefault(key, {})
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [_scalar(part) for part in inner.split(",") if part.strip()] if inner else []
        else:
            data[key] = _scalar(value)
        if key == "links":
            current_list = []
            data[key] = current_list
    return data, body


def _scalar(value: str):
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def _unquote(value) -> str:
    if value is None:
        return ""
    return str(value)


_CLAIM_CACHE: dict[str, list[Path]] = {}


def claim_files(root: Path) -> list[Path]:
    """Every claim file under a root, sharded or flat. Cached for the run."""
    key = str(root.resolve())
    cached = _CLAIM_CACHE.get(key)
    if cached is not None:
        return cached
    claims = Path(root) / "research" / "claims"
    if not claims.is_dir():
        _CLAIM_CACHE[key] = []
        return _CLAIM_CACHE[key]
    found = sorted(
        path
        for path in claims.rglob("*")
        if path.is_file() and path.suffix == ".md" and path.name.startswith("claim")
    )
    _CLAIM_CACHE[key] = found
    return found


def clear_cache() -> None:
    _CLAIM_CACHE.clear()


def _subject_of(claim_id: str, rel: str) -> str:
    rest = claim_id.removeprefix("claim.")
    if "." in rest:
        rest = rest.rsplit(".", 1)[0]
    if rest:
        return rest
    parts = Path(rel).parts
    if len(parts) >= 2:
        return parts[-2]
    return ""


def _matches_subjects(claim_id: str, rel: str, subjects: list[str] | None) -> bool:
    if not subjects:
        return True
    stem = Path(rel).name
    bare = claim_id.removeprefix("claim.")
    hay = [claim_id, bare, stem, *Path(rel).parts]
    for pattern in subjects:
        prefixed = pattern if pattern.startswith("claim.") else f"claim.{pattern}"
        for item in hay:
            if fnmatch.fnmatch(item, pattern) or fnmatch.fnmatch(item, prefixed):
                return True
            if fnmatch.fnmatch(item, f"{pattern}*") or fnmatch.fnmatch(item, f"{prefixed}*"):
                return True
    return False


def _root_name(root: Path, used: dict[str, Path]) -> str:
    name = root.name or "brain"
    if name in used and used[name] != root.resolve():
        parent = root.parent.name
        name = f"{parent}-{name}" if parent else f"{name}-{len(used)}"
    used[name] = root.resolve()
    return name


def _score(text: str, query_terms: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in query_terms if term in lowered)


def _links(meta: dict, rel: str) -> list[str]:
    out = []
    for item in meta.get("links") or []:
        if isinstance(item, dict) and item.get("rel") == rel and item.get("target"):
            out.append(str(item["target"]))
    return out


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _find_record(root: Path, folder: str, record_id: str) -> Path | None:
    base = Path(root) / "research" / folder
    if not base.is_dir() or not record_id:
        return None
    direct = base / f"{record_id}.md"
    if direct.is_file():
        return direct
    matches = list(base.rglob(f"{record_id}.md"))
    return matches[0] if matches else None


def _find_source(root: Path, source_hash: str) -> dict:
    if not source_hash:
        return {}
    sources = Path(root) / "research" / "sources"
    if not sources.is_dir():
        return {}
    needle = source_hash
    for path in sources.rglob("source*.md"):
        text = _read(path)
        if needle not in text:
            continue
        meta, _ = parse_front_matter(text)
        if _unquote(meta.get("source_hash")) == needle or needle in text:
            return meta
    return {}


def _hit_from_claim(root: Path, root_name: str, path: Path, query_terms: list[str]) -> Hit | None:
    text = _read(path)
    if not text:
        return None
    scored = _score(text, query_terms) if query_terms else 0
    meta, body = parse_front_matter(text)
    claim_id = _unquote(meta.get("id") or path.stem)
    claim_text = _unquote(meta.get("description") or meta.get("title") or "")
    if not claim_text:
        claim_text = next(
            (line.lstrip("# ").strip() for line in body.splitlines() if line.strip()),
            body.strip()[:240],
        )
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else path.name
    subject = _unquote(meta.get("subject")) or _subject_of(claim_id, rel)

    quote = ""
    locator = Locator()
    source_hashes: list[str] = []
    source_meta: dict = {}
    for evidence_id in _links(meta, "evidenced_by"):
        evidence_path = _find_record(root, "evidence", evidence_id)
        if evidence_path is None:
            continue
        evidence_meta, evidence_body = parse_front_matter(_read(evidence_path))
        quote = _unquote(evidence_meta.get("text") or evidence_body.strip())
        loc = evidence_meta.get("locator") or {}
        if isinstance(loc, dict):
            locator = Locator(
                asset_path=_unquote(loc.get("asset_path") or evidence_meta.get("asset_path")),
                start_line=loc.get("start_line") if isinstance(loc.get("start_line"), int) else None,
                end_line=loc.get("end_line") if isinstance(loc.get("end_line"), int) else None,
                variant=_unquote(loc.get("variant")),
            )
        source_hash = _unquote(evidence_meta.get("source_hash"))
        if source_hash:
            source_hashes.append(source_hash)
            if not source_meta:
                source_meta = _find_source(root, source_hash)
        break

    if not source_hashes:
        source_hash = _unquote(meta.get("source_hash"))
        if source_hash:
            source_hashes.append(source_hash)
            source_meta = _find_source(root, source_hash)

    confidence = meta.get("confidence")
    try:
        confidence_f = float(confidence)
    except (TypeError, ValueError):
        confidence_f = 0.0

    return Hit(
        key=f"{root_name}:{claim_id}",
        claim=claim_text.strip(),
        quote=quote.strip(),
        locator=locator,
        source_title=_unquote(source_meta.get("title")),
        vendor=_unquote(source_meta.get("vendor")),
        source_kind=_unquote(source_meta.get("source_kind")),
        origin_path=_unquote(source_meta.get("asset_path") or locator.asset_path),
        captured_at=_unquote(source_meta.get("captured_at")),
        subject=subject,
        confidence=confidence_f,
        as_of=_unquote(meta.get("as_of")),
        epistemic=derive_epistemic(source_hashes),
        claim_id=claim_id,
        root_name=root_name,
        score=scored,
    )


def search(
    query: str,
    roots: list[Path | str],
    subjects: list[str] | None = None,
    limit: int = 20,
) -> list[Hit]:
    """Rank claim files by distinct query terms, then by confidence."""
    query_terms = terms(query)
    used: dict[str, Path] = {}
    ranked: list[tuple[int, float, Hit]] = []
    for raw in roots:
        root = Path(raw)
        if not root.exists():
            continue
        name = _root_name(root, used)
        for path in claim_files(root):
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = path.name
            claim_id = path.stem
            if not _matches_subjects(claim_id, rel, subjects):
                continue
            text = _read(path)
            scored = _score(text, query_terms) if query_terms else 0
            if query_terms and scored == 0:
                continue
            hit = _hit_from_claim(root, name, path, query_terms)
            if hit is None:
                continue
            ranked.append((hit.score, hit.confidence, hit))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2].key))
    return [row[2] for row in ranked[: max(0, int(limit))]]


def resolve(key: str, roots: list[Path | str]) -> Hit | None:
    """Look up one corpus reference key (`<root-name>:<claim-id>`)."""
    if ":" not in key:
        return None
    root_name, claim_id = key.split(":", 1)
    used: dict[str, Path] = {}
    for raw in roots:
        root = Path(raw)
        if not root.exists():
            continue
        name = _root_name(root, used)
        if name != root_name:
            continue
        for path in claim_files(root):
            if path.stem == claim_id or path.name.startswith(claim_id):
                return _hit_from_claim(root, name, path, [])
            text = _read(path)
            meta, _ = parse_front_matter(text)
            if _unquote(meta.get("id")) == claim_id:
                return _hit_from_claim(root, name, path, [])
    return None


def format_hits(hits: list[Hit]) -> str:
    """The tool return: key, claim, quote, source line. No write path."""
    if not hits:
        return "No corpus hits."
    blocks = []
    for hit in hits:
        source = hit.source_title or hit.origin_path or "unrecorded source"
        loc = ""
        if hit.locator.asset_path:
            loc = f" ({hit.locator.asset_path}"
            if hit.locator.start_line is not None:
                loc += f":{hit.locator.start_line}"
                if hit.locator.end_line is not None:
                    loc += f"-{hit.locator.end_line}"
            loc += ")"
        blocks.append(
            f"- `{hit.key}` [{hit.epistemic}]\n"
            f"  Claim: {hit.claim}\n"
            f"  Quote: {hit.quote or '(no evidence quote)'}\n"
            f"  Source: {source}{loc}"
            + (f" ({hit.vendor})" if hit.vendor else "")
        )
    return "\n".join(blocks)


def pack(
    topic: str,
    roots: list[Path | str],
    dest: Path | str,
    *,
    limit: int = 40,
    subjects: list[str] | None = None,
) -> dict:
    """Write `brain-pack.md` and `brain-pack.json` under dest.

    The pack is prior conclusions and vocabulary, not verified fact. A missing
    root is recorded as a note. Fewer than ten hits sets `corpus_thin`.
    """
    dest_dir = Path(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    existing: list[Path] = []
    for raw in roots:
        root = Path(raw)
        if not root.exists():
            notes.append(f"missing root: {root}")
            continue
        existing.append(root)

    hits = search(topic, existing, subjects=subjects, limit=limit) if existing else []
    by_subject: dict[str, int] = {}
    for hit in hits:
        by_subject[hit.subject or "unsorted"] = by_subject.get(hit.subject or "unsorted", 0) + 1

    payload = {
        "topic": topic,
        "roots": [str(path) for path in existing],
        "missing": notes,
        "corpus_thin": len(hits) < 10,
        "subjects": by_subject,
        "hits": [hit.as_dict() for hit in hits],
        "keys": [hit.key for hit in hits],
    }
    (dest_dir / "brain-pack.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )

    lines = [
        f"# Corpus pack on {topic}",
        "",
        "Read for terminology and for what was already concluded. Not verified.",
        "Each entry is a prior claim from a configured brain. Cite it by the",
        "corpus reference key if a section will use it.",
        "",
    ]
    if notes:
        lines += ["## Notes", ""]
        lines += [f"- {note}" for note in notes]
        lines.append("")
    if not existing:
        lines.append("No second brain was found. Planned from the topic alone.")
        lines.append("")
    elif not hits:
        lines.append("Nothing in the brain matched this topic.")
        lines.append("")
    else:
        lines += ["## Coverage", ""]
        for subject, count in sorted(by_subject.items()):
            lines.append(f"- {subject}: {count}")
        lines += ["", "## Claims", ""]
        for hit in hits:
            lines += [
                f"### `{hit.key}`",
                "",
                f"**Claim.** {hit.claim}",
                "",
                f"**Quote.** {hit.quote or '(none)'}",
                "",
                f"**Source.** {hit.source_title or 'unrecorded'}"
                + (f" ({hit.vendor})" if hit.vendor else "")
                + (f", {hit.source_kind}" if hit.source_kind else ""),
                "",
                f"**Epistemic.** {hit.epistemic}  **Confidence.** {hit.confidence}",
                "",
            ]
    (dest_dir / "brain-pack.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def _git_toplevel(start: Path) -> Path | None:
    """The checkout `start` lives in, or None. Never raises."""
    import subprocess  # noqa: PLC0415  (only this probe needs it)

    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    line = (out.stdout or "").strip()
    return Path(line) if out.returncode == 0 and line else None


def brain_candidates(
    extra: list[Path | str] | None = None,
    env: str | None = None,
) -> list[dict]:
    """Every place this port looks for a brain, in order, with what it found.

    The default brain is a sibling of the primary checkout. A clone, a
    worktree, or a scratchpad has no such sibling, so the pack came back empty
    and the run failed outline rubric rows that cannot pass against an empty
    pack. It spent $1.07 finding that out. The candidate list is what makes the
    absence readable before the first paid query.

    Read only. A brain is prior art from another repository, and this never
    invents one inside the clone.
    """
    found: list[dict] = []
    seen: set[str] = set()

    def add(source: str, path: Path) -> None:
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        found.append({"source": source, "path": str(path), "exists": path.is_dir()})

    for item in extra or []:
        add("--brain", Path(item))
    for part in (env or "").split(":"):
        part = part.strip()
        if part:
            add("RESEARCH_BRAINS", Path(part))
    add("sibling of this folder", DEFAULT_BRAIN)
    toplevel = _git_toplevel(FOLDER)
    if toplevel is not None:
        add("sibling of the git top level", toplevel.parent / BRAIN_DIR_NAME / "knowledge")
    return found


def default_roots(
    extra: list[Path | str] | None = None,
    env: str | None = None,
) -> list[Path]:
    """`--brain` paths, then `RESEARCH_BRAINS`, then the discovered defaults.

    An explicit path is honored whether or not it exists, because a typo the
    operator can see beats a silent fall back to a different corpus. A default
    is used only when it is really there.
    """
    candidates = brain_candidates(extra, env)
    asked = [row for row in candidates if row["source"] in ("--brain", "RESEARCH_BRAINS")]
    if asked:
        return [Path(row["path"]) for row in asked]
    usable = [Path(row["path"]) for row in candidates if row["exists"]]
    return usable or [DEFAULT_BRAIN]


def demo() -> int:
    """Assert against the committed fixture brain. No network, no SDK."""
    import tempfile  # noqa: PLC0415  (demo-only)

    clear_cache()
    root = FIXTURE_BRAIN
    assert root.is_dir(), f"fixture brain missing at {root}"
    claims = claim_files(root)
    assert len(claims) >= 50, f"need fifty fixture claims, have {len(claims)}"

    sharded = [p for p in claims if "harness-ch03" in p.as_posix()]
    flat = [p for p in claims if p.parent.name == "claims"]
    assert sharded, "the shard walk has to see claims/harness-ch03/"
    assert flat, "the flat walk has to see claims/claim.seminar-*.md"

    hits = search("exit criteria loop done cost", [root], limit=5)
    assert hits, "exit-criteria query should hit the seminar claims"
    assert hits[0].quote, "a hit has to carry the evidence quote"
    assert hits[0].source_title, "a hit has to resolve the source title"
    assert hits[0].key.startswith(root.name + ":")
    assert resolve(hits[0].key, [root]) is not None

    scoped = search("budget", [root], subjects=["harness-ch03"], limit=20)
    assert scoped, "subject filter should keep harness-ch03"
    assert all("harness-ch03" in (h.subject + h.claim_id + h.key) for h in scoped)

    with tempfile.TemporaryDirectory() as tmp:
        missing = pack("anything", [root / "does-not-exist"], Path(tmp) / "missing")
        assert missing["corpus_thin"] is True
        assert missing["hits"] == []
        note = (Path(tmp) / "missing" / "brain-pack.md").read_text(encoding="utf-8")
        assert "No second brain" in note or "missing root" in note

        packed = pack("exit criteria", [root], Path(tmp) / "ok", limit=40)
        assert packed["keys"]
        assert (Path(tmp) / "ok" / "brain-pack.md").is_file()
        assert (Path(tmp) / "ok" / "brain-pack.json").is_file()
    print(
        f"corpus: ok ({len(claims)} claims, {len(hits)} exit hits, "
        f"{len(scoped)} harness-ch03 hits)."
    )
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(demo() if "--demo" in sys.argv else 0)
