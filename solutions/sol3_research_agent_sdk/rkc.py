"""Write the run's research as an RKC knowledge bundle.

A deep-research run that leaves behind only a finished paper has thrown away
the expensive part. The claims, the quotes, the sources, and which claims did
not survive verification are what a later run reuses and what a reader audits.

RKC already owns those nouns, so this port does not invent a citation model.
Eight types and twelve relations, all of them registered:

    ResearchArea --has_subject--> Subject --has_task--> ResearchTask
    ResearchTask --ingested_from--> SourceDocument
                 --asks-->          ResearchQuestion
                 --produced-->      Finding
    Finding --answers--> ResearchQuestion
            --asserts--> Claim --evidenced_by--> Evidence

A contradicted claim is written too, with `status: rejected`. The record of what
the run checked and threw out is worth more than the record of what it kept,
because the next run does not have to spend the budget rediscovering it.

The id rules are copied here rather than imported. This folder is standalone,
and the plugin may not be installed on the machine that runs it.

    python3 rkc.py --demo
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AUTHOR = "sol3-research-agent-sdk"

TYPE_SLUGS = {
    "ResearchArea": "area",
    "Subject": "subject",
    "ResearchTask": "task",
    "SourceDocument": "source",
    "ResearchQuestion": "question",
    "Claim": "claim",
    "Evidence": "evidence",
    "Finding": "finding",
}

FOLDER_FOR = {
    "ResearchArea": "areas",
    "Subject": "subjects",
    "ResearchTask": "tasks",
    "SourceDocument": "sources",
    "ResearchQuestion": "questions",
    "Claim": "claims",
    "Evidence": "evidence",
    "Finding": "findings",
}

# Crockford base32, which drops I, L, O, and U so a ULID cannot be misread.
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# How a verification verdict becomes a record. `rejected` is not a deletion.
STATUS_FOR = {
    "verified": ("accepted", 0.9),
    "disputed": ("reviewed", 0.5),
    "unverified": ("draft", 0.3),
    "contradicted": ("rejected", 0.1),
}

VALIDATOR = (
    Path.home() / ".claude/plugins/marketplaces/rkc-plugin-marketplace/scripts/rkc_validate.py"
)


def _encode(n: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(CROCKFORD[n & 31])
        n >>= 5
    return "".join(reversed(chars))


def ulid() -> str:
    return _encode(int(time.time() * 1000), 10) + _encode(int.from_bytes(os.urandom(10), "big"), 16)


def slug(text: str, limit: int = 64) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (text or "unsorted").lower()).strip("-") or "unsorted"
    if len(normalized) <= limit:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[: limit - 9].rstrip('-')}-{digest}"


def make_id(type_name: str, subject: str) -> str:
    return f"{TYPE_SLUGS[type_name]}.{slug(subject)}.{ulid()}"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_value(value) -> str:
    """Emit one front-matter value.

    A hand-rolled emitter, because this folder must run with no PyYAML. It
    covers the shapes written below and nothing else, and it quotes every string
    so a title with a colon cannot break the document.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_value(item) for item in value) + "]"
    return json.dumps(str(value))


def write_node(root: Path, node_type: str, fields: dict, body: str) -> Path:
    """Write one OKF concept file. Returns its path."""
    folder = Path(root) / "research" / FOLDER_FOR[node_type]
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"type: {node_type}"]
    links = fields.pop("links", None)
    locator = fields.pop("locator", None)
    for key, value in fields.items():
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_yaml_value(value)}")
    if locator:
        lines.append("locator:")
        for key, value in locator.items():
            lines.append(f"  {key}: {_yaml_value(value)}")
    if links:
        lines.append("links:")
        for link in links:
            lines.append(f"  - rel: {link['rel']}")
            lines.append(f"    target: {link['target']}")
    lines += ["---", "", body.rstrip(), ""]
    path = folder / f"{fields['id']}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _claim_kind(text: str) -> str:
    """Which of the validator's five kinds this claim is.

    Crude and deliberately so. A number in the sentence makes it numeric, which
    is the kind most worth re-checking when it goes stale.
    """
    return "numeric" if re.search(r"\d", text or "") else "factual"


def write_bundle(  # noqa: PLR0913, PLR0915  (one pass over eight node types)
    knowledge: Path | str,
    *,
    topic: str,
    area: str,
    plan: dict,
    findings: list[dict],
    claims: list[dict],
) -> dict:
    """Write the whole bundle for one run. Returns a count per type.

    `claims` carry the verdict they came out of phase 3 with. `findings` are one
    per section, each naming the questions it answers and the claims it asserts.
    """
    root = Path(knowledge)
    subject = slug(topic)
    stamp = now()
    today = stamp[:10]

    def base(node_type: str, title: str, **extra) -> dict:
        return {
            "id": make_id(node_type, subject),
            "title": title,
            "status": "draft",
            "verified": False,
            "generated": True,
            "truth_state": "current",
            "author": AUTHOR,
            "timestamp": stamp,
            **extra,
        }

    # Sources first. Everything else points at them.
    assets = root / "research" / "source-assets"
    source_ids: dict[str, str] = {}
    for finding in findings:
        for source in finding.get("sources", []):
            url = source.get("url")
            if not url or url in source_ids:
                continue
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            asset_dir = assets / digest
            asset_dir.mkdir(parents=True, exist_ok=True)
            (asset_dir / "original.md").write_text(
                f"# {source.get('title') or url}\n\n{url}\n\n{finding.get('answer', '')}\n",
                encoding="utf-8",
            )
            fields = base(
                "SourceDocument",
                source.get("title") or url,
                vendor=finding.get("backend", "unknown"),
                source_kind="deep_research",
                source_hash=f"sha256:{digest}",
                asset_path=f"research/source-assets/{digest}/original.md",
                captured_at=stamp,
                ingest_version="1",
            )
            source_ids[url] = fields["id"]
            write_node(root, "SourceDocument", fields, f"Retrieved for: {topic}\n\n{url}")

    question_ids: dict[str, str] = {}
    for question in plan.get("questions", []):
        fields = base("ResearchQuestion", question["text"][:120])
        question_ids[question["id"]] = fields["id"]
        write_node(root, "ResearchQuestion", fields, f"# Research question\n\n{question['text']}")

    claim_ids: dict[str, str] = {}
    evidence_count = 0
    for claim in claims:
        status, confidence = STATUS_FOR.get(claim.get("status", "unverified"), ("draft", 0.3))
        claim_fields = base(
            "Claim",
            claim["text"][:120],
            description=claim["text"],
            status=status,
            verified=status == "accepted",
            claim_kind=_claim_kind(claim["text"]),
            confidence=confidence,
            as_of=today,
        )
        links = []
        if claim.get("quote"):
            digest = hashlib.sha256((claim.get("source_url") or "").encode("utf-8")).hexdigest()
            evidence_fields = base(
                "Evidence",
                f"Quote for: {claim['text'][:80]}",
                status=status,
                kind="quote",
                # `verbatim: false` on purpose. The validator checks a verbatim
                # quote against a byte range in the archived asset. We archive
                # the retrieved answer, not the source page, so the span check
                # would fail on a quote that is perfectly honest.
                verbatim=False,
                text=claim["quote"],
                source_hash=f"sha256:{digest}",
                locator={
                    "variant": "quote",
                    "asset_path": f"research/source-assets/{digest}/original.md",
                },
            )
            write_node(
                root,
                "Evidence",
                evidence_fields,
                f"Quoted from {claim.get('source_url') or 'an unrecorded source'}.",
            )
            links.append({"rel": "evidenced_by", "target": evidence_fields["id"]})
            evidence_count += 1
        if claim.get("status") == "disputed" and claim.get("verifier_url"):
            # `contradicts` on a claim is what makes the validator derive
            # `disputed` rather than `source_supported`. The disagreement is the
            # record, and it must survive in the graph, not only in the prose.
            links.append({"rel": "contradicts", "target": claim_fields["id"]})
        if links:
            claim_fields["links"] = links
        claim_ids[claim["id"]] = claim_fields["id"]
        write_node(root, "Claim", claim_fields, f"# Claim\n\n{claim['text']}")

    finding_ids = []
    for section in plan.get("sections", []):
        section_claims = [c for c in claims if c.get("section") == section["id"]]
        if not section_claims:
            continue
        fields = base(
            "Finding",
            section["heading"],
            description=section["goal"],
            confidence=round(
                sum(
                    STATUS_FOR.get(c.get("status", "unverified"), ("", 0.3))[1]
                    for c in section_claims
                )
                / len(section_claims),
                2,
            ),
            as_of=today,
        )
        links = [
            {"rel": "answers", "target": question_ids[q["id"]]}
            for q in plan.get("questions", [])
            if q.get("section") == section["id"] and q["id"] in question_ids
        ]
        links += [
            {"rel": "asserts", "target": claim_ids[c["id"]]}
            for c in section_claims
            if c["id"] in claim_ids
        ]
        fields["links"] = links
        finding_ids.append(fields["id"])
        write_node(root, "Finding", fields, f"# {section['heading']}\n\n{section['goal']}")

    task_fields = base("ResearchTask", f"White paper run: {topic}", vendor="claude")
    task_fields["links"] = (
        [{"rel": "ingested_from", "target": sid} for sid in source_ids.values()]
        + [{"rel": "asks", "target": qid} for qid in question_ids.values()]
        + [{"rel": "produced", "target": fid} for fid in finding_ids]
    )
    write_node(root, "ResearchTask", task_fields, f"One deep-research run on {topic}.")

    subject_fields = base("Subject", topic[:120])
    subject_fields["links"] = [{"rel": "has_task", "target": task_fields["id"]}]
    write_node(root, "Subject", subject_fields, f"# {topic}\n\nSubject under {area}.")

    area_fields = base("ResearchArea", area)
    area_fields["links"] = [{"rel": "has_subject", "target": subject_fields["id"]}]
    write_node(root, "ResearchArea", area_fields, f"# {area}\n\nTop research area.")

    (root / "index.md").write_text(
        f"---\nokf_version: '0.2'\nbundle: research\n---\n\n# Research bundle\n\n{topic}\n",
        encoding="utf-8",
    )

    return {
        "sources": len(source_ids),
        "questions": len(question_ids),
        "claims": len(claim_ids),
        "evidence": evidence_count,
        "findings": len(finding_ids),
        "subject_id": subject_fields["id"],
    }


def validate(knowledge: Path | str) -> tuple[bool, str]:
    """Run the RKC validator when the plugin is installed.

    Absent plugin means no verdict, not a failure. The bundle is readable
    markdown whether or not a schema checker ever sees it, and a run should not
    die because an optional tool is missing.
    """
    if not VALIDATOR.exists():
        return True, "the RKC plugin is not installed. The bundle was not validated."
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(knowledge)],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def demo() -> int:
    """Write a bundle to a scratch directory and validate it."""
    import tempfile  # noqa: PLC0415  (the demo only)

    assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", ulid()), ulid()
    assert slug("Loop Engineering: Exit Criteria!") == "loop-engineering-exit-criteria"
    assert len(slug("x" * 200)) <= 64
    assert _claim_kind("version 2.0 shipped") == "numeric"
    assert _claim_kind("the parser is reentrant") == "factual"
    assert _yaml_value("a: b") == '"a: b"'

    root = Path(tempfile.mkdtemp()) / "knowledge"
    plan = {
        "sections": [{"id": "s1", "heading": "The problem", "goal": "State it."}],
        "questions": [{"id": "q1", "text": "What does the spec require?", "section": "s1"}],
    }
    findings = [
        {
            "answer": "The spec requires a timeout.",
            "backend": "fixture",
            "sources": [{"url": "https://example.invalid/spec", "title": "The spec"}],
        }
    ]
    claims = [
        {
            "id": "c1",
            "text": "The spec requires a timeout of 30 seconds.",
            "source_url": "https://example.invalid/spec",
            "quote": "a timeout of 30 seconds",
            "section": "s1",
            "status": "verified",
        },
        {
            "id": "c2",
            "text": "The default is unbounded.",
            "source_url": "https://example.invalid/spec",
            "quote": "unbounded",
            "section": "s1",
            "status": "contradicted",
        },
    ]
    counts = write_bundle(
        root, topic="spec timeouts", area="protocols", plan=plan, findings=findings, claims=claims
    )
    assert counts == {
        **counts,
        "sources": 1,
        "questions": 1,
        "claims": 2,
        "evidence": 2,
        "findings": 1,
    }, counts

    # A rejected claim is still on disk. Losing it means the next run pays to
    # rediscover the same wrong answer.
    rejected = [
        p
        for p in (root / "research" / "claims").glob("*.md")
        if 'status: "rejected"' in p.read_text()
    ]
    assert len(rejected) == 1, "the contradicted claim was not recorded"

    ok, note = validate(root)
    assert ok, note
    print(f"rkc: ok ({counts['claims']} claims, {counts['evidence']} evidence). {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
